from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from datetime import date, datetime, timezone
from typing import Any, cast

from app.domain import Author, Identifier, IdentifierType, Venue, VenueType
from app.domain.provenance import ProvenanceEntry
from app.domain.publication import DocumentType, Publication
from app.domain.search import SearchQuery, SearchRun
from app.providers.search.base import JsonObject, ProviderSearchOutput
from app.providers.search.mapping_utils import (
    clean_string,
    deterministic_search_record_id,
    normalize_doi,
    normalize_issn,
    normalize_url,
)
from app.providers.semantic_scholar import (
    SemanticScholarClient,
    SemanticScholarSearchFilters,
)

_DOC_TYPE_MAP = {
    "journalarticle": DocumentType.JOURNAL_ARTICLE,
    "journal": DocumentType.JOURNAL_ARTICLE,
    "conference": DocumentType.CONFERENCE_PAPER,
    "proceedings": DocumentType.CONFERENCE_PAPER,
    "book": DocumentType.BOOK,
    "bookchapter": DocumentType.BOOK_CHAPTER,
    "review": DocumentType.REVIEW,
    "thesis": DocumentType.DISSERTATION,
    "dissertation": DocumentType.DISSERTATION,
    "report": DocumentType.REPORT,
    "preprint": DocumentType.PREPRINT,
    "dataset": DocumentType.DATASET,
}

# Canonical fields requested from the paper/search endpoint; keep minimal to
# reduce response size and latency (Semantic Scholar guidance).
_FIELDS = [
    "paperId",
    "title",
    "abstract",
    "authors",
    "year",
    "publicationDate",
    "publicationVenue",
    "venue",
    "publicationTypes",
    "externalIds",
    "url",
]

_TRUNCATION_WARNING = (
    "Semantic Scholar returned only {fetched} of {total} matching records; the "
    "relevance search endpoint caps results at 1000 and no further pages are "
    "available via this endpoint."
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_offset(cursor: str) -> int:
    if cursor == "*":
        return 0
    try:
        offset = int(cursor)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            "semantic_scholar cursor must be an offset integer string or '*'"
        ) from exc
    if offset < 0:
        raise ValueError("semantic_scholar cursor offset must not be negative")
    return offset


def _parse_date(date_str: Any) -> date | None:
    if isinstance(date_str, str):
        s_date = date_str.strip()
        if len(s_date) == 10:
            try:
                return date.fromisoformat(s_date)
            except ValueError:
                return None
    return None


class SemanticScholarProvider:
    """Map Semantic Scholar Graph API paper responses to canonical publications."""

    name = "semantic_scholar"

    def __init__(
        self,
        *,
        client: SemanticScholarClient | None = None,
        retrieval_clock: Callable[[], datetime] = _utc_now,
        paginate: bool = False,
        max_results: int = 100,
        filters: SemanticScholarSearchFilters | None = None,
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

        client = self._require_client()
        self._validate_search_context(search_run, search_query)
        if self._paginate:
            return await self._search_paginated_with_raw(
                client=client,
                search_run=search_run,
                search_query=search_query,
                per_page=per_page,
                cursor=cursor,
            )

        page = await client.search_papers_page(
            search_run.rendered_query,
            limit=per_page,
            offset=_parse_offset(cursor),
            fields=_FIELDS,
        )
        retrieved_at = self._retrieval_clock()
        publications = [
            self._map_paper_with_provenance(
                paper,
                search_run=search_run,
                search_query=search_query,
                retrieved_at=retrieved_at,
            )
            for paper in page.data
        ]
        next_cursor = (
            str(page.next)
            if page.data and page.next is not None and page.next != page.offset
            else None
        )
        filter_warnings = self._filters.get_warnings() if self._filters else ()
        is_lossless = self._filters.is_lossless if self._filters else True
        warnings = self._truncation_warnings(
            len(publications), page.total, next_cursor
        )
        return ProviderSearchOutput(
            publications=publications,
            raw_responses=[cast(JsonObject, page.payload)],
            total_count=page.total,
            next_cursor=next_cursor,
            has_more=next_cursor is not None,
            warnings=tuple([*filter_warnings, *warnings]),
            is_lossless=is_lossless,
        )

    async def _search_paginated_with_raw(
        self,
        *,
        client: SemanticScholarClient,
        search_run: SearchRun,
        search_query: SearchQuery,
        per_page: int,
        cursor: str,
    ) -> ProviderSearchOutput:
        publications: list[Publication] = []
        raw_responses: list[JsonObject] = []
        seen_offsets: set[int] = set()
        total_count: int | None = None
        current_offset = _parse_offset(cursor)
        next_cursor: str | None = None

        while len(publications) < self._max_results:
            page = await client.search_papers_page(
                search_run.rendered_query,
                limit=min(per_page, self._max_results - len(publications)),
                offset=current_offset,
                fields=_FIELDS,
            )
            raw_responses.append(cast(JsonObject, page.payload))
            page_total_count = page.total
            if total_count is None:
                total_count = page_total_count
            elif page_total_count != total_count:
                raise ValueError("Semantic Scholar total changed during pagination")

            retrieved_at = self._retrieval_clock()
            consumed = 0
            for paper in page.data:
                publications.append(
                    self._map_paper_with_provenance(
                        paper,
                        search_run=search_run,
                        search_query=search_query,
                        retrieved_at=retrieved_at,
                    )
                )
                consumed += 1
                if len(publications) >= self._max_results:
                    break

            if len(publications) >= self._max_results:
                next_cursor = str(current_offset + consumed)
                break

            if page.next is None or not page.data:
                next_cursor = None
                break
            if page.next == current_offset or page.next in seen_offsets:
                next_cursor = None
                break

            seen_offsets.add(current_offset)
            current_offset = page.next
            next_cursor = str(page.next)

        filter_warnings = self._filters.get_warnings() if self._filters else ()
        is_lossless = self._filters.is_lossless if self._filters else True
        truncation_warnings = self._truncation_warnings(
            len(publications), total_count, next_cursor
        )
        return ProviderSearchOutput(
            publications=publications,
            raw_responses=raw_responses,
            total_count=total_count,
            next_cursor=next_cursor,
            has_more=next_cursor is not None,
            warnings=tuple([*filter_warnings, *truncation_warnings]),
            is_lossless=is_lossless,
        )

    def _truncation_warnings(
        self,
        fetched: int,
        total_count: int | None,
        next_cursor: str | None,
    ) -> list[str]:
        if (
            next_cursor is None
            and total_count is not None
            and fetched < total_count
        ):
            return [
                _TRUNCATION_WARNING.format(fetched=fetched, total=total_count)
            ]
        return []

    async def iterate(
        self,
        *,
        search_run: SearchRun,
        search_query: SearchQuery,
        per_page: int = 200,
    ) -> AsyncIterator[Publication]:
        """Yield mapped publications across all offset pages."""

        client = self._require_client()
        self._validate_search_context(search_run, search_query)
        async for paper in client.iterate_papers(
            search_run.rendered_query,
            limit=per_page,
            fields=_FIELDS,
        ):
            yield self._map_paper_with_provenance(
                paper,
                search_run=search_run,
                search_query=search_query,
                retrieved_at=self._retrieval_clock(),
            )

    def map_paper(
        self,
        paper: dict[str, Any],
        *,
        search_run: SearchRun,
        search_query: SearchQuery,
        retrieved_at: datetime,
    ) -> Publication:
        if not isinstance(paper, dict):
            raise TypeError("paper must be a dictionary")

        # 0. Provenance required fields validation
        paper_id = clean_string(paper.get("paperId"))
        if paper_id is None:
            raise ValueError("Semantic Scholar paper must have a valid paperId for provenance")

        # 1. Title
        title = clean_string(paper.get("title"))
        if title is None:
            raise ValueError("Semantic Scholar paper title is missing or blank")

        # 2. Abstract
        abstract = clean_string(paper.get("abstract"))

        # 3. Authors
        authors: list[Author] = []
        author_list = paper.get("authors")
        if isinstance(author_list, list):
            for auth_dict in author_list:
                if isinstance(auth_dict, dict):
                    display_name = clean_string(auth_dict.get("name"))
                    if display_name:
                        authors.append(Author(display_name=display_name))

        # 4. Publication date & year
        year_val = paper.get("year")
        pub_year = None
        if isinstance(year_val, int) and not isinstance(year_val, bool):
            if 1000 <= year_val <= 9999:
                pub_year = year_val

        pub_date = _parse_date(paper.get("publicationDate"))
        if pub_date is not None:
            if pub_year is None:
                pub_year = pub_date.year
            elif pub_year != pub_date.year:
                # If the year of the parsed publicationDate disagrees with the publication_year,
                # the publication_date is cleared to keep the publication_year, preventing Pydantic validation errors.
                pub_date = None

        # 5. Venue
        venue_obj = None
        venue_name = None
        venue_type = None
        venue_identifiers: list[Identifier] = []

        pub_venue = paper.get("publicationVenue")
        if isinstance(pub_venue, dict):
            venue_name = clean_string(pub_venue.get("name"))
            raw_type = clean_string(pub_venue.get("type"))
            if raw_type:
                raw_type_lower = raw_type.lower()
                if raw_type_lower == "journal":
                    venue_type = VenueType.JOURNAL
                elif raw_type_lower == "conference":
                    venue_type = VenueType.CONFERENCE
                elif raw_type_lower == "book":
                    venue_type = VenueType.BOOK
                elif raw_type_lower == "repository":
                    venue_type = VenueType.REPOSITORY
                else:
                    venue_type = VenueType.OTHER

            # ISSN mapping
            seen_issns: set[str] = set()
            issn = normalize_issn(pub_venue.get("issn"))
            if issn:
                venue_identifiers.append(Identifier(type=IdentifierType.ISSN, value=issn))
                seen_issns.add(issn)
            issns = pub_venue.get("issns")
            if isinstance(issns, list):
                for single_issn in issns:
                    normalized_issn = normalize_issn(single_issn)
                    if (
                        normalized_issn is not None
                        and normalized_issn not in seen_issns
                    ):
                        seen_issns.add(normalized_issn)
                        venue_identifiers.append(
                            Identifier(
                                type=IdentifierType.ISSN,
                                value=normalized_issn,
                            )
                        )

        if not venue_name:
            venue_name = clean_string(paper.get("venue"))

        if venue_name:
            venue_obj = Venue(
                name=venue_name,
                type=venue_type,
                identifiers=venue_identifiers,
            )

        # 6. Document Type
        pub_types = paper.get("publicationTypes")
        doc_type = None
        if isinstance(pub_types, list) and pub_types:
            has_non_blank_type = False
            for pt in pub_types:
                if isinstance(pt, str):
                    pt_clean = pt.strip().lower().replace(" ", "").replace("_", "").replace("-", "")
                    if not pt_clean:
                        continue
                    has_non_blank_type = True
                    if pt_clean in _DOC_TYPE_MAP:
                        doc_type = _DOC_TYPE_MAP[pt_clean]
                        break
            if doc_type is None and has_non_blank_type:
                doc_type = DocumentType.OTHER

        # 7. Identifiers
        identifiers: list[Identifier] = []

        # paperId
        identifiers.append(
            Identifier(
                type=IdentifierType.OTHER,
                value=paper_id,
                source=self.name,
            )
        )

        # externalIds
        ext_ids = paper.get("externalIds")
        if isinstance(ext_ids, dict):
            # DOI
            doi = normalize_doi(ext_ids.get("DOI"))
            if doi:
                identifiers.append(
                    Identifier(
                        type=IdentifierType.DOI,
                        value=doi,
                    )
                )
            # PMID / PubMed
            pmid = clean_string(ext_ids.get("PubMed"))
            if pmid:
                identifiers.append(
                    Identifier(
                        type=IdentifierType.PMID,
                        value=pmid,
                    )
                )

        # 8. URL
        urls: list[str] = []
        url = normalize_url(paper.get("url"))
        if url is not None:
            urls.append(url)

        # 9. Provenance
        provenance = [
            ProvenanceEntry(
                source=self.name,
                source_record_id=paper_id,
                retrieved_at=retrieved_at,
                query_id=search_query.query_id,
                run_id=search_run.run_id,
                rendered_query=search_run.rendered_query,
            )
        ]

        return Publication(
            title=title,
            abstract=abstract,
            authors=authors,
            publication_year=pub_year,
            publication_date=pub_date,
            identifiers=identifiers,
            venue=venue_obj,
            document_type=doc_type,
            # The paper/search endpoint does not support requesting `language`.
            # Do not infer it from other metadata when Semantic Scholar omits it.
            language=None,
            urls=urls,
            provenance=provenance,
        )

    def _map_paper_with_provenance(
        self,
        paper: dict[str, Any],
        *,
        search_run: SearchRun,
        search_query: SearchQuery,
        retrieved_at: datetime,
    ) -> Publication:
        publication = self.map_paper(
            paper,
            search_run=search_run,
            search_query=search_query,
            retrieved_at=retrieved_at,
        )
        doi = None
        for identifier in publication.identifiers:
            if identifier.type is IdentifierType.DOI:
                doi = identifier.value
                break
        return publication.model_copy(
            update={
                "record_id": deterministic_search_record_id(
                    provider=self.name,
                    source_id=clean_string(paper.get("paperId")),
                    doi=doi,
                    title=publication.title,
                    publication_year=publication.publication_year,
                ),
            }
        )

    def _require_client(self) -> SemanticScholarClient:
        if self._client is None:
            raise RuntimeError(
                "SemanticScholarProvider requires a client for search operations"
            )
        return self._client

    def _validate_search_context(
        self,
        search_run: SearchRun,
        search_query: SearchQuery,
    ) -> None:
        if search_run.provider.casefold() != self.name:
            raise ValueError("search_run provider must be semantic_scholar")
        if search_run.query_id != search_query.query_id:
            raise ValueError("search_run and search_query must have the same query_id")
        if search_run.query_version != search_query.version:
            raise ValueError(
                "search_run query_version must match search_query version"
            )
