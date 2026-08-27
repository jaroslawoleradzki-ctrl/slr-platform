from __future__ import annotations

import base64
import html
import json
import re
from collections.abc import AsyncIterator, Callable
from datetime import date, datetime, timezone
from typing import Any, cast

from app.domain import Affiliation, Author, Identifier, IdentifierType, Venue
from app.domain.provenance import ProvenanceEntry
from app.domain.publication import DocumentType, Publication
from app.domain.search import SearchQuery, SearchRun
from app.normalization import normalize_orcid
from app.providers.crossref import CrossrefClient, CrossrefSearchFilters
from app.providers.search.base import JsonObject, ProviderSearchOutput
from app.providers.search.mapping_utils import (
    clean_string,
    deterministic_search_record_id,
    normalize_doi,
    normalize_issn,
    normalize_url,
)
from app.rendering.crossref import build_crossref_candidate_queries

_TYPE_MAP = {
    "journal-article": DocumentType.JOURNAL_ARTICLE,
    "proceedings-article": DocumentType.CONFERENCE_PAPER,
    "book": DocumentType.BOOK,
    "monograph": DocumentType.BOOK,
    "book-chapter": DocumentType.BOOK_CHAPTER,
    "book-section": DocumentType.BOOK_CHAPTER,
    "dissertation": DocumentType.DISSERTATION,
    "thesis": DocumentType.DISSERTATION,
    "report": DocumentType.REPORT,
    "posted-content": DocumentType.PREPRINT,
    "preprint": DocumentType.PREPRINT,
    "dataset": DocumentType.DATASET,
    "review": DocumentType.REVIEW,
}


class MalformedCrossrefRecordError(ValueError):
    """A record-local Crossref metadata error that can safely be skipped."""


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _clean_abstract(abstract: str) -> str | None:
    decoded = html.unescape(abstract)
    cleaned = re.sub(r"<[^>]+>", " ", decoded)
    cleaned = " ".join(cleaned.split())
    return cleaned if cleaned else None


def _parse_crossref_date(date_dict: Any) -> tuple[int, date | None] | None:
    if not isinstance(date_dict, dict):
        return None
    date_parts = date_dict.get("date-parts")
    if not isinstance(date_parts, list) or not date_parts:
        return None
    parts = date_parts[0]
    if not isinstance(parts, list) or not parts:
        return None
    if len(parts) > 3:
        return None
    if not all(isinstance(part, int) and not isinstance(part, bool) for part in parts):
        return None

    year = parts[0]
    if not (1000 <= year <= 9999):
        return None

    if len(parts) == 1:
        return year, None
    elif len(parts) == 2:
        month = parts[1]
        if not (1 <= month <= 12):
            return None
        return year, None
    elif len(parts) == 3:
        month = parts[1]
        day = parts[2]
        if not (1 <= month <= 12):
            return None
        try:
            d = date(year, month, day)
            return year, d
        except ValueError:
            return year, None
    return None


class CrossrefProvider:
    name = "crossref"

    def __init__(
        self,
        *,
        client: CrossrefClient | None = None,
        retrieval_clock: Callable[[], datetime] = _utc_now,
        paginate: bool = False,
        max_results: int = 100,
        max_physical_requests_per_call: int = 10,
        filters: CrossrefSearchFilters | None = None,
    ) -> None:
        if max_results < 1:
            raise ValueError("max_results must be at least 1")
        if max_physical_requests_per_call < 1:
            raise ValueError("max_physical_requests_per_call must be at least 1")
        self._client = client
        self._retrieval_clock = retrieval_clock
        self._paginate = paginate
        self._max_results = max_results
        self._max_physical_requests_per_call = max_physical_requests_per_call
        self._filters = filters

    @staticmethod
    def _read_total_count(payload: dict[str, Any]) -> int | None:
        message = payload.get("message")
        if not isinstance(message, dict):
            raise ValueError("Crossref response message must be a JSON object")
        total_results = message.get("total-results")
        if total_results is None:
            return None
        if not isinstance(total_results, int) or isinstance(total_results, bool) or total_results < 0:
            raise ValueError("Crossref message.total-results must be a non-negative integer")
        return total_results

    @staticmethod
    def _read_next_cursor(payload: dict[str, Any]) -> str | None:
        message = payload.get("message")
        if not isinstance(message, dict):
            raise ValueError("Crossref response message must be a JSON object")
        next_cursor = message.get("next-cursor")
        if next_cursor is None:
            return None
        if not isinstance(next_cursor, str) or not next_cursor.strip():
            raise ValueError("Crossref response message.next-cursor must be a non-blank string or null")
        return next_cursor.strip()

    async def search(
        self,
        *,
        search_run: SearchRun,
        search_query: SearchQuery,
        rows: int = 20,
        cursor: str | None = None,
    ) -> list[Publication]:
        """Fetch and map one Crossref page with explicit search provenance."""

        output = await self.search_with_raw(
            search_run=search_run,
            search_query=search_query,
            rows=rows,
            cursor=cursor,
        )
        return output.publications

    async def search_with_raw(
        self,
        *,
        search_run: SearchRun,
        search_query: SearchQuery,
        rows: int = 20,
        cursor: str | None = None,
    ) -> ProviderSearchOutput:
        """Execute a bounded multi-query candidate retrieval plan."""

        client = self._require_client()
        self._validate_search_context(search_run, search_query)
        candidate_queries = build_crossref_candidate_queries(search_query.expression)
        query_index, physical_cursor = self._decode_candidate_cursor(cursor)
        target = self._max_results if self._paginate else rows
        publications: list[Publication] = []
        raw_responses: list[JsonObject] = []
        seen_source_ids: set[str] = set()
        seen_positions: set[tuple[int, str]] = set()
        next_cursor: str | None = None
        candidate_total = 0
        has_candidate_total = False
        raw_count = 0
        mapped_count = 0
        skipped_malformed_count = 0

        while (
            query_index < len(candidate_queries)
            and len(publications) < target
            and len(raw_responses) < self._max_physical_requests_per_call
        ):
            position = (query_index, physical_cursor)
            if position in seen_positions:
                break
            seen_positions.add(position)
            requested_rows = min(rows, target - len(publications))
            payload = await client.search_works(
                candidate_queries[query_index],
                rows=requested_rows,
                cursor=physical_cursor,
                filters=self._filters,
            )
            raw_responses.append(cast(JsonObject, payload))
            page_total = self._read_total_count(payload)
            if page_total is not None and (
                physical_cursor == "*" or (len(candidate_queries) == 1 and not has_candidate_total)
            ):
                candidate_total += page_total
                has_candidate_total = True
            message = payload["message"]
            items = message["items"]
            raw_count += len(items)
            retrieved_at = self._retrieval_clock()
            for work in items:
                try:
                    publication = self._map_record_or_raise_malformed(
                        work,
                        search_run=search_run,
                        search_query=search_query,
                        retrieved_at=retrieved_at,
                    )
                except MalformedCrossrefRecordError:
                    skipped_malformed_count += 1
                    continue
                mapped_count += 1
                source_id = publication.provenance[0].source_record_id
                if source_id not in seen_source_ids:
                    seen_source_ids.add(source_id)
                    publications.append(publication)

            raw_next = self._read_next_cursor(payload)
            query_complete = not items or raw_next is None or raw_next == physical_cursor
            if query_complete:
                query_index += 1
                physical_cursor = "*"
            else:
                assert raw_next is not None
                physical_cursor = raw_next

            if not self._paginate:
                break

        if query_index < len(candidate_queries):
            next_cursor = (
                physical_cursor
                if len(candidate_queries) == 1
                else self._encode_candidate_cursor(query_index, physical_cursor)
            )
        filter_warnings = self._filters.get_warnings() if self._filters else ()
        plan_warnings = [
            f"Crossref candidate plan executed {len(raw_responses)} physical request(s) in this page; canonical validation is required."
        ]
        if next_cursor is not None and len(raw_responses) >= self._max_physical_requests_per_call:
            plan_warnings.append(
                "Crossref candidate-plan request bound was reached; continue with the returned opaque cursor."
            )
        if skipped_malformed_count:
            plan_warnings.append(
                f"{skipped_malformed_count} Crossref record(s) skipped due to missing/malformed title or metadata validation."
            )
        return ProviderSearchOutput(
            publications=publications,
            raw_responses=raw_responses,
            # Totals from multiple free-text queries overlap and cannot be
            # summed into a meaningful candidate-set total.
            total_count=(
                candidate_total
                if len(candidate_queries) == 1 and has_candidate_total
                else None
            ),
            next_cursor=next_cursor,
            has_more=next_cursor is not None,
            warnings=tuple([*filter_warnings, *plan_warnings]),
            is_lossless=False,
            raw_count=raw_count,
            mapped_count=mapped_count,
            skipped_malformed_count=skipped_malformed_count,
        )

    @staticmethod
    def _encode_candidate_cursor(query_index: int, physical_cursor: str) -> str:
        payload = json.dumps([query_index, physical_cursor], separators=(",", ":"))
        return "crossref-plan:" + base64.urlsafe_b64encode(payload.encode()).decode()

    @staticmethod
    def _decode_candidate_cursor(cursor: str | None) -> tuple[int, str]:
        if cursor is None or cursor == "*":
            return 0, "*"
        prefix = "crossref-plan:"
        if not cursor.startswith(prefix):
            # Backwards-compatible physical cursor supplied by older clients.
            return 0, cursor
        try:
            decoded = base64.urlsafe_b64decode(cursor[len(prefix) :]).decode()
            query_index, physical_cursor = json.loads(decoded)
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            raise ValueError("invalid Crossref candidate-plan cursor") from exc
        if not isinstance(query_index, int) or query_index < 0:
            raise ValueError("invalid Crossref candidate query index")
        if not isinstance(physical_cursor, str) or not physical_cursor:
            raise ValueError("invalid Crossref physical cursor")
        return query_index, physical_cursor

    async def _search_paginated_with_raw(
        self,
        *,
        client: CrossrefClient,
        search_run: SearchRun,
        search_query: SearchQuery,
        rows: int,
        cursor: str,
    ) -> ProviderSearchOutput:
        publications: list[Publication] = []
        raw_responses: list[JsonObject] = []
        seen_cursors: set[str] = set()
        total_count: int | None = None
        next_cursor: str | None = None
        while len(publications) < self._max_results:
            payload = await client.search_works(
                search_run.rendered_query,
                rows=min(rows, self._max_results - len(publications)),
                cursor=cursor,
                filters=self._filters,
            )
            raw_responses.append(cast(JsonObject, payload))
            page_total_count = self._read_total_count(payload)
            if total_count is None:
                total_count = page_total_count
            elif page_total_count != total_count:
                raise ValueError("Crossref message.total-results changed during pagination")
            message = payload["message"]
            items = message["items"]
            retrieved_at = self._retrieval_clock()
            for work in items:
                if not isinstance(work, dict):
                    raise ValueError("Crossref work must be a JSON object")
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
            next_cursor = self._read_next_cursor(payload)
            if next_cursor is None or not items:
                next_cursor = None
                break
            if next_cursor == cursor or next_cursor in seen_cursors:
                next_cursor = None
                break
            seen_cursors.add(cursor)
            cursor = next_cursor
        filter_warnings = self._filters.get_warnings() if self._filters else ()
        is_lossless = self._filters.is_lossless if self._filters else True
        return ProviderSearchOutput(
            publications=publications,
            raw_responses=raw_responses,
            total_count=total_count,
            next_cursor=next_cursor,
            has_more=next_cursor is not None,
            warnings=filter_warnings,
            is_lossless=is_lossless,
        )

    async def iterate(
        self,
        *,
        search_run: SearchRun,
        search_query: SearchQuery,
        rows: int = 20,
        limit: int | None = None,
    ) -> AsyncIterator[Publication]:
        """Yield mapped Crossref publications across cursor pages."""
        client = self._require_client()
        self._validate_search_context(search_run, search_query)
        async for work in client.iterate_works(
            search_run.rendered_query,
            rows=rows,
            limit=limit,
            filters=self._filters,
        ):
            yield self._map_work_with_provenance(
                work,
                search_run=search_run,
                search_query=search_query,
                retrieved_at=self._retrieval_clock(),
            )

    def map_work(self, work: dict[str, Any]) -> Publication:
        if not isinstance(work, dict):
            raise TypeError("work must be a dictionary")

        title_list = work.get("title")
        if not isinstance(title_list, list):
            raise MalformedCrossrefRecordError("Crossref work title is missing or not a list")
        title = None
        for t in title_list:
            if isinstance(t, str):
                s_title = t.strip()
                if s_title:
                    title = s_title
                    break
        if title is None:
            raise MalformedCrossrefRecordError("Crossref work must have a non-blank title")

        identifiers = []
        doi = normalize_doi(work.get("DOI"))
        if doi is not None:
            identifiers.append(Identifier(type=IdentifierType.DOI, value=doi))

        authors = []
        author_list = work.get("author")
        if isinstance(author_list, list):
            for a_dict in author_list:
                if isinstance(a_dict, dict):
                    given_name = clean_string(a_dict.get("given"))
                    family_name = clean_string(a_dict.get("family"))
                    parts = []
                    if given_name:
                        parts.append(given_name)
                    if family_name:
                        parts.append(family_name)
                    if parts:
                        display_name = " ".join(parts)
                    else:
                        org_name = clean_string(a_dict.get("name"))
                        if org_name:
                            display_name = org_name
                        else:
                            continue

                    author_identifiers = []
                    orcid = normalize_orcid(a_dict.get("ORCID"))
                    if orcid:
                        author_identifiers.append(Identifier(type=IdentifierType.ORCID, value=orcid))

                    affiliations = []
                    aff_list = a_dict.get("affiliation")
                    if isinstance(aff_list, list):
                        for aff_dict in aff_list:
                            if isinstance(aff_dict, dict):
                                aff_name = clean_string(aff_dict.get("name"))
                                if aff_name:
                                    affiliations.append(Affiliation(name=aff_name))

                    authors.append(
                        Author(
                            display_name=display_name,
                            given_name=given_name,
                            family_name=family_name,
                            identifiers=author_identifiers,
                            affiliations=affiliations,
                        )
                    )

        pub_year = None
        pub_date = None
        for date_field in ["published-print", "published-online", "published", "issued"]:
            res = _parse_crossref_date(work.get(date_field))
            if res is not None:
                pub_year, pub_date = res
                break

        venue = None
        container_titles = work.get("container-title")
        venue_name = None
        if isinstance(container_titles, list):
            for ct in container_titles:
                if isinstance(ct, str):
                    s_ct = ct.strip()
                    if s_ct:
                        venue_name = s_ct
                        break
        if venue_name:
            venue_identifiers = []
            seen_issns: set[str] = set()
            issns = work.get("ISSN")
            if isinstance(issns, list):
                for issn in issns:
                    normalized_issn = normalize_issn(issn)
                    if normalized_issn is not None and normalized_issn not in seen_issns:
                        seen_issns.add(normalized_issn)
                        venue_identifiers.append(
                            Identifier(
                                type=IdentifierType.ISSN,
                                value=normalized_issn,
                            )
                        )
            venue = Venue(name=venue_name, identifiers=venue_identifiers)

        publisher = clean_string(work.get("publisher"))

        type_str = work.get("type")
        doc_type = None
        if isinstance(type_str, str):
            s_type = type_str.strip()
            if s_type:
                doc_type = _TYPE_MAP.get(s_type.casefold(), DocumentType.OTHER)

        language = clean_string(work.get("language"))

        urls = []
        url = normalize_url(work.get("URL"))
        if url is not None:
            urls.append(url)

        abstract = None
        raw_abstract = work.get("abstract")
        if isinstance(raw_abstract, str):
            abstract = _clean_abstract(raw_abstract)

        return Publication(
            title=title,
            abstract=abstract,
            authors=authors,
            publication_year=pub_year,
            publication_date=pub_date,
            identifiers=identifiers,
            venue=venue,
            publisher=publisher,
            document_type=doc_type,
            language=language,
            urls=urls,
        )

    def _map_work_with_provenance(
        self,
        work: dict[str, Any],
        *,
        search_run: SearchRun,
        search_query: SearchQuery,
        retrieved_at: datetime,
    ) -> Publication:
        doi = normalize_doi(work.get("DOI"))
        publication = self.map_work(work)
        if doi is not None:
            source_record_id = doi
        else:
            clean_title = " ".join(publication.title.split()).casefold()
            year_str = str(publication.publication_year) if publication.publication_year else ""
            source_record_id = f"fallback:{clean_title}:{year_str}"

        provenance = ProvenanceEntry(
            source=self.name,
            source_record_id=source_record_id,
            retrieved_at=retrieved_at,
            query_id=search_query.query_id,
            run_id=search_run.run_id,
            rendered_query=search_run.rendered_query,
        )
        return publication.model_copy(
            update={
                "record_id": deterministic_search_record_id(
                    provider=self.name,
                    source_id=source_record_id,
                    doi=doi,
                    title=publication.title,
                    publication_year=publication.publication_year,
                ),
                "provenance": [provenance],
            }
        )

    def _map_record_or_raise_malformed(
        self,
        work: Any,
        *,
        search_run: SearchRun,
        search_query: SearchQuery,
        retrieved_at: datetime,
    ) -> Publication:
        if not isinstance(work, dict):
            raise MalformedCrossrefRecordError("Crossref work must be a JSON object")
        return self._map_work_with_provenance(
            work,
            search_run=search_run,
            search_query=search_query,
            retrieved_at=retrieved_at,
        )

    def _require_client(self) -> CrossrefClient:
        if self._client is None:
            raise RuntimeError("CrossrefProvider requires a client for search operations")
        return self._client

    def _validate_search_context(
        self,
        search_run: SearchRun,
        search_query: SearchQuery,
    ) -> None:
        if search_run.provider.casefold() != self.name:
            raise ValueError("search_run provider must be crossref")
        if search_run.query_id != search_query.query_id:
            raise ValueError("search_run and search_query must have the same query_id")
        if search_run.query_version != search_query.version:
            raise ValueError("search_run query_version must match search_query version")
