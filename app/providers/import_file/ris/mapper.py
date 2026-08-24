from __future__ import annotations

from datetime import datetime, timezone

from app.domain import Author, Identifier, IdentifierType
from app.domain.provenance import ProvenanceEntry
from app.domain.publication import DocumentType, Publication
from app.normalization import normalize_doi

_TY_TO_DOC_TYPE: dict[str, DocumentType] = {
    "JOUR": DocumentType.JOURNAL_ARTICLE,
    "JFULL": DocumentType.JOURNAL_ARTICLE,
    "MGZN": DocumentType.JOURNAL_ARTICLE,
    "NEWS": DocumentType.JOURNAL_ARTICLE,
    "CONF": DocumentType.CONFERENCE_PAPER,
    "CPAPER": DocumentType.CONFERENCE_PAPER,
    "BOOK": DocumentType.BOOK,
    "CHAP": DocumentType.BOOK_CHAPTER,
    "ECHAP": DocumentType.BOOK_CHAPTER,
    "THES": DocumentType.DISSERTATION,
    "RPRT": DocumentType.REPORT,
    "UNPB": DocumentType.PREPRINT,
    "DATA": DocumentType.DATASET,
}


def _first_non_blank(record: dict[str, list[str]], *tags: str) -> str | None:
    """Return the first non-blank string found across the given tags, or None."""
    for tag in tags:
        for value in record.get(tag, []):
            stripped = value.strip()
            if stripped:
                return stripped
    return None


def _parse_year(raw: str) -> int | None:
    """Parse a year string to int, returning None if malformed or out of range."""
    try:
        year = int(raw.strip())
    except ValueError:
        return None
    return year if 1000 <= year <= 9999 else None


def _parse_authors(record: dict[str, list[str]]) -> list[Author]:
    """Map AU (or A1 as fallback) entries to Author objects.

    Name format:
    - ``"Smith, John"``  → family_name="Smith", given_name="John"
    - ``"Smith, J."``    → family_name="Smith", given_name="J."
    - ``"John Smith"``   → display_name only; given_name/family_name=None
    Blank names are silently skipped.
    """
    raw_names = record.get("AU") or record.get("A1") or []
    authors: list[Author] = []
    for raw in raw_names:
        display = raw.strip()
        if not display:
            continue
        if ", " in display:
            family, _, given = display.partition(", ")
            family_stripped = family.strip() or None
            given_stripped = given.strip() or None
        else:
            family_stripped = None
            given_stripped = None
        authors.append(
            Author(
                display_name=display,
                family_name=family_stripped,
                given_name=given_stripped,
            )
        )
    return authors


def map_ris_record(
    record: dict[str, list[str]],
    *,
    source: str,
    source_database: str | None = None,
) -> Publication:
    """Map one parsed RIS record to a canonical :class:`Publication`.

    Parameters
    ----------
    record:
        A single record as returned by ``parse_ris()``.  The dict maps
        two-character RIS tags to lists of string values.
    source:
        Non-blank identifier of the bibliography origin, e.g.
        ``"google_scholar"`` or ``"zotero"``.
    source_database:
        Optional bibliographic source/database identifier, e.g.
        ``"google_scholar_pop"`` or ``"scopus"``.  When provided, this is
        used as the provenance source instead of the generic *source*.
    """
    # 0. Validate source
    source_stripped = source.strip()
    if not source_stripped:
        raise ValueError("source must be a non-blank string")

    provenance_source = source_database or source_stripped

    # 1. Title (required)
    title = _first_non_blank(record, "TI", "T1", "CT")
    if title is None:
        raise ValueError("RIS record is missing a title (TI/T1/CT)")

    # 2. Abstract
    abstract = _first_non_blank(record, "AB", "N2")

    # 3. Authors
    authors = _parse_authors(record)

    # 4. Publication year  (PY preferred, Y1 as fallback)
    pub_year: int | None = None
    for tag in ("PY", "Y1"):
        raw_year = _first_non_blank(record, tag)
        if raw_year is not None:
            pub_year = _parse_year(raw_year)
            if pub_year is not None:
                break

    # 5. Document type
    #    Unknown or absent TY → OTHER (consistent treatment, no silent None).
    ty_value = _first_non_blank(record, "TY")
    doc_type: DocumentType = _TY_TO_DOC_TYPE.get(ty_value or "", DocumentType.OTHER)

    # 6. DOI — normalized via the project's existing helper
    identifiers: list[Identifier] = []
    normalized_doi: str | None = None
    raw_doi = _first_non_blank(record, "DO")
    if raw_doi is not None:
        normalized_doi = normalize_doi(raw_doi)
        if normalized_doi:
            identifiers.append(Identifier(type=IdentifierType.DOI, value=normalized_doi))

    # 7. Language (LA tag) — passed through to normalization stage
    language = _first_non_blank(record, "LA")

    # 8. Provenance
    #    source_record_id: use the normalized DOI when available; fall back to
    #    the record title, which is always present (required above).
    source_record_id = normalized_doi if normalized_doi else title
    provenance = [
        ProvenanceEntry(
            source=provenance_source,
            source_record_id=source_record_id,
            retrieved_at=datetime.now(timezone.utc),
            transformation="ris_to_publication",
        )
    ]

    return Publication(
        title=title,
        abstract=abstract,
        authors=authors,
        publication_year=pub_year,
        document_type=doc_type,
        identifiers=identifiers,
        provenance=provenance,
        language=language,
    )
