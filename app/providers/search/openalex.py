from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from datetime import date, datetime, timezone
from typing import Any, cast

from app.domain import (
    Affiliation,
    Author,
    Identifier,
    IdentifierType,
    Venue,
    VenueType,
)
from app.domain.provenance import ProvenanceEntry
from app.domain.publication import DocumentType, Publication
from app.domain.search import SearchQuery, SearchRun
from app.normalization import normalize_orcid
from app.providers.openalex import OpenAlexClient, OpenAlexSearchFilters
from app.providers.search.base import JsonObject, ProviderSearchOutput
from app.providers.search.mapping_utils import (
    clean_string,
    deterministic_search_record_id,
    normalize_doi,
    normalize_issn,
    normalize_url,
)

_DOCUMENT_TYPE_MAP = {
    "article": DocumentType.JOURNAL_ARTICLE,
    "journal-article": DocumentType.JOURNAL_ARTICLE,
    "book": DocumentType.BOOK,
    "book-chapter": DocumentType.BOOK_CHAPTER,
    "dissertation": DocumentType.DISSERTATION,
    "report": DocumentType.REPORT,
    "preprint": DocumentType.PREPRINT,
    "dataset": DocumentType.DATASET,
    "review": DocumentType.REVIEW,
    "proceedings-article": DocumentType.CONFERENCE_PAPER,
    "conference-paper": DocumentType.CONFERENCE_PAPER,
}

_VENUE_TYPE_MAP = {
    "journal": VenueType.JOURNAL,
    "conference": VenueType.CONFERENCE,
    "book": VenueType.BOOK,
    "book series": VenueType.BOOK,
    "repository": VenueType.REPOSITORY,
}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _reconstruct_abstract(value: Any) -> str | None:
    if not isinstance(value, dict):
        return None

    positioned_tokens: list[tuple[int, str]] = []
    for token, positions in value.items():
        if (
            not isinstance(token, str)
            or not token.strip()
            or not isinstance(positions, list)
        ):
            return None
        if not all(
            isinstance(position, int)
            and not isinstance(position, bool)
            and position >= 0
            for position in positions
        ):
            return None
        positioned_tokens.extend((position, token) for position in positions)

    # Sorting by token makes collisions independent of JSON object key order.
    occupied: set[int] = set()
    ordered_tokens: list[str] = []
    for position, token in sorted(positioned_tokens):
        if position not in occupied:
            occupied.add(position)
            ordered_tokens.append(token)
    return " ".join(ordered_tokens) or None


def _parse_date(value: Any) -> date | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = date.fromisoformat(value.strip())
    except ValueError:
        return None
    return parsed if len(value.strip()) == 10 else None


def _identifier(
    identifier_type: IdentifierType,
    value: Any,
    *,
    source: str | None = None,
) -> Identifier | None:
    cleaned = clean_string(value)
    if cleaned is None:
        return None
    return Identifier(type=identifier_type, value=cleaned, source=source)


def _doi_value(publication: Publication) -> str | None:
    for identifier in publication.identifiers:
        if identifier.type is IdentifierType.DOI:
            return identifier.value
    return None


def _map_authors(value: Any) -> list[Author]:
    if not isinstance(value, list):
        return []

    authors: list[Author] = []
    for authorship in value:
        if not isinstance(authorship, dict):
            continue
        raw_author = authorship.get("author")
        if not isinstance(raw_author, dict):
            continue
        display_name = clean_string(raw_author.get("display_name"))
        if display_name is None:
            continue

        identifiers: list[Identifier] = []
        openalex_id = _identifier(
            IdentifierType.OTHER,
            raw_author.get("id"),
            source="openalex",
        )
        if openalex_id is not None:
            identifiers.append(openalex_id)
        orcid = _identifier(
            IdentifierType.ORCID,
            normalize_orcid(raw_author.get("orcid")),
        )
        if orcid is not None:
            identifiers.append(orcid)

        affiliations: list[Affiliation] = []
        institutions = authorship.get("institutions")
        if isinstance(institutions, list):
            for institution in institutions:
                if not isinstance(institution, dict):
                    continue
                institution_name = clean_string(institution.get("display_name"))
                if institution_name is None:
                    continue
                affiliation_identifiers: list[Identifier] = []
                institution_id = _identifier(
                    IdentifierType.OTHER,
                    institution.get("id"),
                    source="openalex",
                )
                if institution_id is not None:
                    affiliation_identifiers.append(institution_id)
                ror = _identifier(
                    IdentifierType.OTHER,
                    institution.get("ror"),
                    source="ror",
                )
                if ror is not None:
                    affiliation_identifiers.append(ror)
                affiliations.append(
                    Affiliation(
                        name=institution_name,
                        identifiers=affiliation_identifiers,
                    )
                )

        authors.append(
            Author(
                display_name=display_name,
                identifiers=identifiers,
                affiliations=affiliations,
            )
        )
    return authors


def _map_venue(value: Any) -> Venue | None:
    if not isinstance(value, dict):
        return None
    source = value.get("source")
    if not isinstance(source, dict):
        return None
    name = clean_string(source.get("display_name"))
    if name is None:
        return None

    venue_type = None
    raw_type = clean_string(source.get("type"))
    if raw_type is not None:
        venue_type = _VENUE_TYPE_MAP.get(raw_type.casefold(), VenueType.OTHER)

    identifiers: list[Identifier] = []
    seen_issns: set[str] = set()
    raw_issns = [source.get("issn_l")]
    if isinstance(source.get("issn"), list):
        raw_issns.extend(source["issn"])
    for raw_issn in raw_issns:
        issn = normalize_issn(raw_issn)
        if issn is not None and issn not in seen_issns:
            seen_issns.add(issn)
            identifiers.append(Identifier(type=IdentifierType.ISSN, value=issn))

    return Venue(name=name, type=venue_type, identifiers=identifiers)


def _collect_urls(work: dict[str, Any]) -> list[str]:
    urls: list[str] = []
    seen: set[str] = set()
    for location_name in ("primary_location", "best_oa_location"):
        location = work.get(location_name)
        if not isinstance(location, dict):
            continue
        for field_name in ("landing_page_url", "pdf_url"):
            url = normalize_url(location.get(field_name))
            if url is not None and url not in seen:
                seen.add(url)
                urls.append(url)
    return urls


class OpenAlexProvider:
    """Map OpenAlex Works responses to canonical publications."""

    name = "openalex"

    def __init__(
        self,
        *,
        client: OpenAlexClient,
        retrieval_clock: Callable[[], datetime] = _utc_now,
        paginate: bool = False,
        max_results: int = 100,
        filters: OpenAlexSearchFilters | None = None,
    ) -> None:
        if max_results < 1:
            raise ValueError("max_results must be at least 1")
        self._client = client
        self._retrieval_clock = retrieval_clock
        self._paginate = paginate
        self._max_results = max_results
        self._filters = filters

    async def search(
        self,
        *,
        search_run: SearchRun,
        search_query: SearchQuery,
        per_page: int = 25,
        cursor: str = "*",
    ) -> list[Publication]:
        """Fetch and map one page using explicit, auditable search context."""

        output = await self.search_with_raw(
            search_run=search_run,
            search_query=search_query,
            per_page=per_page,
            cursor=cursor,
        )
        return output.publications

    async def search_with_raw(
        self,
        *,
        search_run: SearchRun,
        search_query: SearchQuery,
        per_page: int = 25,
        cursor: str = "*",
    ) -> ProviderSearchOutput:
        """Fetch one page once, then expose its mapping and original payload."""

        self._validate_search_context(search_run, search_query)
        if self._paginate:
            return await self._search_paginated_with_raw(
                search_run=search_run,
                search_query=search_query,
                per_page=per_page,
                cursor=cursor,
            )
        payload = await self._client.search_works(
            search_run.rendered_query,
            per_page=per_page,
            cursor=cursor,
            filters=self._filters,
        )

        results = payload.get("results")
        if not isinstance(results, list):
            raise ValueError("OpenAlex response results must be a list")

        retrieved_at = self._retrieval_clock()
        publications: list[Publication] = []
        for work in results:
            if not isinstance(work, dict):
                raise ValueError("OpenAlex work must be a JSON object")
            publications.append(
                self._map_work_with_provenance(
                    work,
                    search_run=search_run,
                    search_query=search_query,
                    retrieved_at=retrieved_at,
                )
            )
        return ProviderSearchOutput(
            publications=publications,
            raw_responses=[cast(JsonObject, payload)],
            total_count=self._read_total_count(payload),
            next_cursor=self._read_next_cursor(payload),
            has_more=self._read_next_cursor(payload) is not None,
        )

    async def _search_paginated_with_raw(
        self,
        *,
        search_run: SearchRun,
        search_query: SearchQuery,
        per_page: int,
        cursor: str,
    ) -> ProviderSearchOutput:
        publications: list[Publication] = []
        raw_responses: list[JsonObject] = []
        seen_cursors: set[str] = set()
        total_count: int | None = None
        next_cursor: str | None = None
        while len(publications) < self._max_results:
            payload = await self._client.search_works(
                search_run.rendered_query,
                per_page=min(per_page, self._max_results - len(publications)),
                cursor=cursor,
                filters=self._filters,
            )
            raw_responses.append(cast(JsonObject, payload))
            page_total_count = self._read_total_count(payload)
            if total_count is None:
                total_count = page_total_count
            elif page_total_count != total_count:
                raise ValueError("OpenAlex meta.count changed during pagination")
            results = payload.get("results")
            if not isinstance(results, list):
                raise ValueError("OpenAlex response results must be a list")
            retrieved_at = self._retrieval_clock()
            for work in results:
                if not isinstance(work, dict):
                    raise ValueError("OpenAlex work must be a JSON object")
                publications.append(
                    self._map_work_with_provenance(
                        work,
                        search_run=search_run,
                        search_query=search_query,
                        retrieved_at=retrieved_at,
                    )
                )
                if len(publications) >= self._max_results:
                    break
            meta = payload.get("meta")
            if not isinstance(meta, dict):
                raise ValueError("OpenAlex response meta must be a JSON object")
            next_cursor = self._read_next_cursor(payload)
            if next_cursor is None or not results:
                break
            if next_cursor == cursor or next_cursor in seen_cursors:
                break
            seen_cursors.add(cursor)
            cursor = next_cursor
        return ProviderSearchOutput(
            publications=publications,
            raw_responses=raw_responses,
            total_count=total_count,
            next_cursor=next_cursor,
            has_more=next_cursor is not None,
        )

    async def iterate(
        self,
        *,
        search_run: SearchRun,
        search_query: SearchQuery,
        per_page: int = 200,
    ) -> AsyncIterator[Publication]:
        """Yield mapped publications across all cursor pages."""

        self._validate_search_context(search_run, search_query)
        async for work in self._client.iterate_works(
            search_run.rendered_query,
            per_page=per_page,
            filters=self._filters,
        ):
            yield self._map_work_with_provenance(
                work,
                search_run=search_run,
                search_query=search_query,
                retrieved_at=self._retrieval_clock(),
            )

    @staticmethod
    def _read_total_count(payload: dict[str, Any]) -> int | None:
        meta = payload.get("meta")
        if not isinstance(meta, dict):
            raise ValueError("OpenAlex response meta must be a JSON object")
        count = meta.get("count")
        if count is None:
            return None
        if not isinstance(count, int) or isinstance(count, bool) or count < 0:
            raise ValueError("OpenAlex meta.count must be a non-negative integer")
        return count

    @staticmethod
    def _read_next_cursor(payload: dict[str, Any]) -> str | None:
        meta = payload.get("meta")
        if not isinstance(meta, dict):
            raise ValueError("OpenAlex response meta must be a JSON object")
        next_cursor = meta.get("next_cursor")
        if next_cursor is None:
            return None
        if not isinstance(next_cursor, str) or not next_cursor.strip():
            raise ValueError(
                "OpenAlex next_cursor must be a non-blank string or null"
            )
        return next_cursor

    def map_work(self, work: dict[str, Any]) -> Publication:
        """Map one OpenAlex work without I/O or search provenance."""

        if not isinstance(work, dict):
            raise TypeError("OpenAlex work must be a dictionary")

        title = clean_string(work.get("title")) or clean_string(
            work.get("display_name")
        )
        if title is None:
            raise ValueError("OpenAlex work title must be a non-blank string")

        identifiers: list[Identifier] = []
        doi_identifier = _identifier(
            IdentifierType.DOI,
            normalize_doi(work.get("doi")),
        )
        if doi_identifier is not None:
            identifiers.append(doi_identifier)

        source_record_id = _identifier(
            IdentifierType.OTHER,
            work.get("id"),
            source=self.name,
        )
        if source_record_id is not None:
            identifiers.append(source_record_id)

        publication_year = work.get("publication_year")
        if (
            not isinstance(publication_year, int)
            or isinstance(publication_year, bool)
            or not 1000 <= publication_year <= 9999
        ):
            publication_year = None

        publication_date = _parse_date(work.get("publication_date"))
        if publication_date is not None:
            if publication_year is None:
                publication_year = publication_date.year
            elif publication_year != publication_date.year:
                publication_date = None

        raw_document_type = clean_string(work.get("type"))
        document_type = None
        if raw_document_type is not None:
            document_type = _DOCUMENT_TYPE_MAP.get(
                raw_document_type.casefold(),
                DocumentType.OTHER,
            )

        language = clean_string(work.get("language"))
        raw_open_access = work.get("open_access")
        open_access = (
            raw_open_access.get("is_oa")
            if isinstance(raw_open_access, dict)
            and isinstance(raw_open_access.get("is_oa"), bool)
            else None
        )

        return Publication(
            title=title,
            abstract=_reconstruct_abstract(work.get("abstract_inverted_index")),
            authors=_map_authors(work.get("authorships")),
            publication_year=publication_year,
            publication_date=publication_date,
            identifiers=identifiers,
            venue=_map_venue(work.get("primary_location")),
            document_type=document_type,
            language=language,
            urls=_collect_urls(work),
            open_access=open_access,
        )

    def _map_work_with_provenance(
        self,
        work: dict[str, Any],
        *,
        search_run: SearchRun,
        search_query: SearchQuery,
        retrieved_at: datetime,
    ) -> Publication:
        source_record_id = work.get("id")
        if not isinstance(source_record_id, str) or not source_record_id.strip():
            raise ValueError("OpenAlex work id must be a non-blank string")

        publication = self.map_work(work)
        return publication.model_copy(
            update={
                "record_id": deterministic_search_record_id(
                    provider=self.name,
                    source_id=source_record_id,
                    doi=_doi_value(publication),
                    title=publication.title,
                    publication_year=publication.publication_year,
                ),
                "provenance": [
                    ProvenanceEntry(
                        source=self.name,
                        source_record_id=source_record_id.strip(),
                        retrieved_at=retrieved_at,
                        query_id=search_query.query_id,
                        run_id=search_run.run_id,
                        rendered_query=search_run.rendered_query,
                    )
                ]
            }
        )

    def _validate_search_context(
        self,
        search_run: SearchRun,
        search_query: SearchQuery,
    ) -> None:
        if search_run.provider.casefold() != self.name:
            raise ValueError("search_run provider must be openalex")
        if search_run.query_id != search_query.query_id:
            raise ValueError("search_run and search_query must have the same query_id")
        if search_run.query_version != search_query.version:
            raise ValueError(
                "search_run query_version must match search_query version"
            )
