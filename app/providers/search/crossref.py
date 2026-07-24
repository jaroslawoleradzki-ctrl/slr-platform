from __future__ import annotations

import html
import re
from datetime import date
from typing import Any

from app.domain import Affiliation, Author, Identifier, IdentifierType, Venue
from app.domain.publication import DocumentType, Publication

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

    async def search(self, config):
        raise NotImplementedError("Moduł Crossref będzie wdrożony w następnym etapie.")

    def map_work(self, work: dict[str, Any]) -> Publication:
        if not isinstance(work, dict):
            raise TypeError("work must be a dictionary")

        # 1. Title mapping
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

        # 2. DOI mapping
        identifiers = []
        doi = work.get("DOI")
        if isinstance(doi, str):
            doi_val = doi.strip().lower()
            if doi_val:
                identifiers.append(Identifier(type=IdentifierType.DOI, value=doi_val))

        # 3. Author mapping
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

        # 4. Publication date mapping
        pub_year = None
        pub_date = None
        for date_field in ["published-print", "published-online", "published", "issued"]:
            res = _parse_crossref_date(work.get(date_field))
            if res is not None:
                pub_year, pub_date = res
                break

        # 5. Venue mapping
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

        # 6. Publisher mapping
        publisher = _clean_str(work.get("publisher"))

        # 7. Document type mapping
        type_str = work.get("type")
        doc_type = None
        if isinstance(type_str, str):
            s_type = type_str.strip()
            if s_type:
                doc_type = _TYPE_MAP.get(s_type, DocumentType.OTHER)

        # 8. Language mapping
        language = _clean_str(work.get("language"))

        # 9. URL mapping
        urls = []
        raw_url = work.get("URL")
        if isinstance(raw_url, str):
            s_url = raw_url.strip()
            if s_url.startswith(("http://", "https://")):
                urls.append(s_url)

        # 10. Abstract mapping
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
