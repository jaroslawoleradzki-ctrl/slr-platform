from __future__ import annotations

import html
import re
from collections.abc import AsyncIterator, Callable
from datetime import date, datetime, timezone
from typing import Any

from app.domain import Affiliation, Author, Identifier, IdentifierType, Venue
from app.domain.provenance import ProvenanceEntry
from app.domain.publication import DocumentType, Publication
from app.domain.search import SearchQuery, SearchRun
from app.providers.crossref import CrossrefClient

_TYPE_MAP = {
    "journal-article": DocumentType.JOURNAL_ARTICLE,
    "proceedings-article": DocumentType.CONFERENCE_PAPER,
    "book": DocumentType.BOOK,
    "monograph": DocumentType.BOOK,
    "book-chapter": DocumentType.BOOK_CHAPTER,
    "book-section": DocumentType.BOOK_CHAPTER,
    "dissertation": DocumentType.DISSERTATION,
    "report": DocumentType.REPORT,
    "posted-content": DocumentType.PREPRINT,
    "dataset": DocumentType.DATASET,
}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _clean_str(val: Any) -> str | None:
    if isinstance(val, str):
        s = val.strip()
        return s if s else None
    return None


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
    if not all(
        isinstance(part, int) and not isinstance(part, bool)
        for part in parts
    ):
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
        try:
            d = date(year, month, day)
            return year, d
        except ValueError:
            return None
    return None


class CrossrefProvider:
    name = "crossref"

    def __init__(
        self,
        *,
        client: CrossrefClient | None = None,
        retrieval_clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        self._client = client
        self._retrieval_clock = retrieval_clock

    async def search(
        self,
        *,
        search_run: SearchRun,
        search_query: SearchQuery,
        rows: int = 20,
        cursor: str | None = None,
    ) -> list[Publication]:
        """Fetch and map one Crossref page with explicit search provenance."""
        client = self._require_client()
        self._validate_search_context(search_run, search_query)
        payload = await client.search_works(
            search_run.rendered_query,
            rows=rows,
            cursor=cursor,
        )
        message = payload["message"]
        items = message["items"]
        retrieved_at = self._retrieval_clock()
        return [
            self._map_work_with_provenance(
                work,
                search_run=search_run,
                search_query=search_query,
                retrieved_at=retrieved_at,
            )
            for work in items
        ]

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
            raise ValueError("Crossref work title is missing or not a list")
        title = None
        for t in title_list:
            if isinstance(t, str):
                s_title = t.strip()
                if s_title:
                    title = s_title
                    break
        if title is None:
            raise ValueError("Crossref work must have a non-blank title")

        identifiers = []
        doi = work.get("DOI")
        if isinstance(doi, str):
            doi_val = doi.strip().lower()
            if doi_val:
                identifiers.append(Identifier(type=IdentifierType.DOI, value=doi_val))

        authors = []
        author_list = work.get("author")
        if isinstance(author_list, list):
            for a_dict in author_list:
                if isinstance(a_dict, dict):
                    given_name = _clean_str(a_dict.get("given"))
                    family_name = _clean_str(a_dict.get("family"))
                    parts = []
                    if given_name:
                        parts.append(given_name)
                    if family_name:
                        parts.append(family_name)
                    if not parts:
                        continue
                    display_name = " ".join(parts)

                    author_identifiers = []
                    orcid = _clean_str(a_dict.get("ORCID"))
                    if orcid:
                        orcid_val = orcid
                        if "/" in orcid_val:
                            orcid_val = orcid_val.rstrip("/").split("/")[-1]
                        orcid_val = orcid_val.strip()
                        if orcid_val:
                            author_identifiers.append(
                                Identifier(type=IdentifierType.ORCID, value=orcid_val)
                            )

                    affiliations = []
                    aff_list = a_dict.get("affiliation")
                    if isinstance(aff_list, list):
                        for aff_dict in aff_list:
                            if isinstance(aff_dict, dict):
                                aff_name = _clean_str(aff_dict.get("name"))
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
            issns = work.get("ISSN")
            if isinstance(issns, list):
                for issn in issns:
                    if isinstance(issn, str):
                        s_issn = issn.strip()
                        if s_issn:
                            venue_identifiers.append(
                                Identifier(type=IdentifierType.ISSN, value=s_issn)
                            )
            venue = Venue(name=venue_name, identifiers=venue_identifiers)

        publisher = _clean_str(work.get("publisher"))

        type_str = work.get("type")
        doc_type = None
        if isinstance(type_str, str):
            s_type = type_str.strip()
            if s_type:
                doc_type = _TYPE_MAP.get(s_type, DocumentType.OTHER)

        language = _clean_str(work.get("language"))

        urls = []
        raw_url = work.get("URL")
        if isinstance(raw_url, str):
            s_url = raw_url.strip()
            if s_url.startswith(("http://", "https://")):
                urls.append(s_url)

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
        source_record_id = _clean_str(work.get("DOI"))
        if source_record_id is None:
            raise ValueError("Crossref work DOI must be a non-blank string for provenance")

        publication = self.map_work(work)
        provenance = ProvenanceEntry(
            source=self.name,
            source_record_id=source_record_id.lower(),
            retrieved_at=retrieved_at,
            query_id=search_query.query_id,
            run_id=search_run.run_id,
            rendered_query=search_run.rendered_query,
        )
        return publication.model_copy(update={"provenance": [provenance]})

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
            raise ValueError(
                "search_run query_version must match search_query version"
            )
