from __future__ import annotations

from datetime import date, datetime
from typing import Any

from app.domain import Author, Identifier, IdentifierType, Venue, VenueType
from app.domain.provenance import ProvenanceEntry
from app.domain.publication import DocumentType, Publication
from app.domain.search import SearchQuery, SearchRun

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


def _clean_str(val: Any) -> str | None:
    if isinstance(val, str):
        s = val.strip()
        return s if s else None
    return None


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
        paper_id = _clean_str(paper.get("paperId"))
        if paper_id is None:
            raise ValueError("Semantic Scholar paper must have a valid paperId for provenance")

        # 1. Title
        title = _clean_str(paper.get("title"))
        if title is None:
            raise ValueError("Semantic Scholar paper title is missing or blank")

        # 2. Abstract
        abstract = _clean_str(paper.get("abstract"))

        # 3. Authors
        authors: list[Author] = []
        author_list = paper.get("authors")
        if isinstance(author_list, list):
            for auth_dict in author_list:
                if isinstance(auth_dict, dict):
                    display_name = _clean_str(auth_dict.get("name"))
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
            venue_name = _clean_str(pub_venue.get("name"))
            raw_type = _clean_str(pub_venue.get("type"))
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
            issn = _clean_str(pub_venue.get("issn"))
            if issn:
                venue_identifiers.append(Identifier(type=IdentifierType.ISSN, value=issn))
            issns = pub_venue.get("issns")
            if isinstance(issns, list):
                for single_issn in issns:
                    if isinstance(single_issn, str):
                        s_issn = single_issn.strip()
                        if s_issn and s_issn not in [vi.value for vi in venue_identifiers]:
                            venue_identifiers.append(Identifier(type=IdentifierType.ISSN, value=s_issn))

        if not venue_name:
            venue_name = _clean_str(paper.get("venue"))

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
            for pt in pub_types:
                if isinstance(pt, str):
                    pt_clean = pt.strip().lower().replace(" ", "").replace("_", "").replace("-", "")
                    if pt_clean in _DOC_TYPE_MAP:
                        doc_type = _DOC_TYPE_MAP[pt_clean]
                        break
            if doc_type is None:
                doc_type = DocumentType.OTHER

        # 7. Identifiers
        identifiers: list[Identifier] = []

        # paperId
        identifiers.append(
            Identifier(
                type=IdentifierType.OTHER,
                value=paper_id,
                source="semanticscholar",
            )
        )

        # externalIds
        ext_ids = paper.get("externalIds")
        if isinstance(ext_ids, dict):
            # DOI
            doi = _clean_str(ext_ids.get("DOI"))
            if doi:
                identifiers.append(
                    Identifier(
                        type=IdentifierType.DOI,
                        value=doi.strip().lower(),
                    )
                )
            # PMID / PubMed
            pmid = _clean_str(ext_ids.get("PubMed"))
            if pmid:
                identifiers.append(
                    Identifier(
                        type=IdentifierType.PMID,
                        value=pmid,
                    )
                )

        # 8. URL
        urls: list[str] = []
        raw_url = paper.get("url")
        if isinstance(raw_url, str):
            s_url = raw_url.strip()
            if s_url.startswith(("http://", "https://")):
                urls.append(s_url)

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
            urls=urls,
            provenance=provenance,
        )



