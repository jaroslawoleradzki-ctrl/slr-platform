from __future__ import annotations

from datetime import datetime, timezone

from app.domain import Author, Identifier, IdentifierType
from app.domain.provenance import ProvenanceEntry
from app.domain.publication import DocumentType, Publication
from app.domain.venue import Venue
from app.normalization import normalize_doi
from app.providers.import_file.bibtex.parser import BibTeXRecord

_ENTRY_TYPE_TO_DOCUMENT_TYPE: dict[str, DocumentType] = {
    "article": DocumentType.JOURNAL_ARTICLE,
    "book": DocumentType.BOOK,
    "inbook": DocumentType.BOOK_CHAPTER,
    "incollection": DocumentType.BOOK_CHAPTER,
    "inproceedings": DocumentType.CONFERENCE_PAPER,
    "conference": DocumentType.CONFERENCE_PAPER,
    "proceedings": DocumentType.CONFERENCE_PAPER,
    "phdthesis": DocumentType.DISSERTATION,
    "mastersthesis": DocumentType.DISSERTATION,
    "techreport": DocumentType.REPORT,
    "misc": DocumentType.OTHER,
}


def _non_blank(fields: dict[str, str], name: str) -> str | None:
    value = fields.get(name)
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _split_authors(value: str) -> list[str]:
    authors: list[str] = []
    start = 0
    depth = 0
    position = 0

    while position < len(value):
        character = value[position]
        if character == "{":
            depth += 1
        elif character == "}" and depth > 0:
            depth -= 1
        elif depth == 0 and value[position : position + 3].casefold() == "and":
            before = value[position - 1] if position > 0 else ""
            after_position = position + 3
            after = value[after_position] if after_position < len(value) else ""
            if before.isspace() and after.isspace():
                authors.append(value[start:position].strip())
                position = after_position
                start = position
                continue
        position += 1

    authors.append(value[start:].strip())
    return [author for author in authors if author]


def _is_outer_braced(value: str) -> bool:
    if not (value.startswith("{") and value.endswith("}")):
        return False

    depth = 0
    for position, character in enumerate(value):
        if character == "{":
            depth += 1
        elif character == "}":
            depth -= 1
            if depth == 0 and position != len(value) - 1:
                return False
    return depth == 0


def _map_author(value: str) -> Author:
    display_name = value.strip()
    if _is_outer_braced(display_name):
        return Author(display_name=display_name[1:-1].strip())

    if "," in display_name:
        family_name, given_name = display_name.split(",", maxsplit=1)
        return Author(
            display_name=display_name,
            family_name=family_name.strip() or None,
            given_name=given_name.strip() or None,
        )

    parts = display_name.split()
    if len(parts) == 1:
        return Author(display_name=display_name, family_name=parts[0])
    return Author(
        display_name=display_name,
        given_name=" ".join(parts[:-1]),
        family_name=parts[-1],
    )


def _map_authors(fields: dict[str, str]) -> list[Author]:
    raw_authors = _non_blank(fields, "author")
    if raw_authors is None:
        return []
    return [_map_author(author) for author in _split_authors(raw_authors)]


def _parse_year(fields: dict[str, str]) -> int | None:
    raw_year = _non_blank(fields, "year")
    if raw_year is None or len(raw_year) != 4 or not raw_year.isdigit():
        return None
    year = int(raw_year)
    return year if 1000 <= year <= 9999 else None


def _map_venue(fields: dict[str, str]) -> Venue | None:
    for field_name in ("journal", "booktitle", "publisher"):
        name = _non_blank(fields, field_name)
        if name is not None:
            return Venue(name=name)
    return None


def map_bibtex_record(
    record: BibTeXRecord,
    *,
    source: str,
) -> Publication:
    """Map one parsed BibTeX record to a canonical publication."""
    source_stripped = source.strip()
    if not source_stripped:
        raise ValueError("source must be a non-blank string")

    fields = record["fields"]
    title = _non_blank(fields, "title")
    if title is None:
        raise ValueError("BibTeX record is missing a title")

    normalized_doi = normalize_doi(_non_blank(fields, "doi"))
    identifiers = (
        [Identifier(type=IdentifierType.DOI, value=normalized_doi)]
        if normalized_doi is not None
        else []
    )

    citation_key = record["citation_key"].strip()
    source_record_id = normalized_doi or citation_key or title

    return Publication(
        title=title,
        abstract=_non_blank(fields, "abstract"),
        authors=_map_authors(fields),
        publication_year=_parse_year(fields),
        document_type=_ENTRY_TYPE_TO_DOCUMENT_TYPE.get(
            record["entry_type"].lower(),
            DocumentType.OTHER,
        ),
        identifiers=identifiers,
        venue=_map_venue(fields),
        provenance=[
            ProvenanceEntry(
                source=source_stripped,
                source_record_id=source_record_id,
                retrieved_at=datetime.now(timezone.utc),
                transformation="bibtex_to_publication",
            )
        ],
    )
