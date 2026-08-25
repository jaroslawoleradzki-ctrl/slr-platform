"""Deterministic RIS serialization for canonical publications (v0.6.1 Slice 1).

Pure function layer: ``render_ris(publications) -> str``. No I/O, no
repository access, no mutation. Output is byte-stable for identical input.

Tag mapping mirrors the import direction in
``app.providers.import_file.ris.mapper`` for round-trip fidelity:

- TY: inverse of ``_TY_TO_DOC_TYPE`` (default ``JOUR``);
- authors and keywords are repeated tags, one physical line per value;
- lines use the exact ``XX  - value`` separator the parser requires;
- records terminate with ``ER``; newline convention is CRLF (D6).
"""

from __future__ import annotations

import re

from app.domain.author import Author
from app.domain.identifiers import IdentifierType
from app.domain.publication import DocumentType, Publication

_DOCUMENT_TYPE_TO_RIS: dict[DocumentType, str] = {
    DocumentType.JOURNAL_ARTICLE: "JOUR",
    DocumentType.REVIEW: "JOUR",
    DocumentType.OTHER: "JOUR",
    DocumentType.CONFERENCE_PAPER: "CONF",
    DocumentType.BOOK: "BOOK",
    DocumentType.BOOK_CHAPTER: "CHAP",
    DocumentType.DISSERTATION: "THES",
    DocumentType.REPORT: "RPRT",
    DocumentType.PREPRINT: "UNPB",
    DocumentType.DATASET: "DATA",
}

_DEFAULT_RIS_TYPE = "JOUR"

# Control characters stripped from every emitted value (plan §17). CR and LF
# are handled separately by the line-break normalization below.
_CONTROL_CHARACTERS = frozenset(
    "\x00\x01\x02\x03\x04\x05\x06\x07\x08\x0b\x0c\x0e\x0f"
    "\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1b\x1c\x1d\x1e\x1f\x7f"
)

_LINE_BREAKS = re.compile(r"\r\n|\r|\n")

_NEWLINE = "\r\n"


def sanitize_ris_value(value: str) -> str:
    """Central safety boundary for every serialized RIS field value.

    RIS is line-oriented, so embedded CR/LF in metadata could otherwise inject
    tags, ``ER`` terminators, or whole fake records into an export. Each line
    break is replaced with a single space (preserving the text content) and
    remaining control characters are stripped, guaranteeing that no sanitized
    value can alter RIS record structure.
    """
    normalized = _LINE_BREAKS.sub(" ", value)
    return "".join(character for character in normalized if character not in _CONTROL_CHARACTERS)


def _ris_type(publication: Publication) -> str:
    if publication.document_type is None:
        return _DEFAULT_RIS_TYPE
    return _DOCUMENT_TYPE_TO_RIS.get(publication.document_type, _DEFAULT_RIS_TYPE)


def _format_author(author: Author) -> str:
    if author.family_name and author.given_name:
        return f"{author.family_name}, {author.given_name}"
    if author.family_name:
        return author.family_name
    return author.display_name


def _doi(publication: Publication) -> str | None:
    return next(
        (identifier.value for identifier in publication.identifiers if identifier.type is IdentifierType.DOI),
        None,
    )


def render_ris_record(publication: Publication) -> list[str]:
    """Return the ordered RIS tag lines for a single publication (no newlines).

    Every metadata value passes through :func:`sanitize_ris_value`; only the
    exporter itself may emit structural tags and the ``ER`` terminator.
    """
    lines = [f"TY  - {_ris_type(publication)}"]
    lines.append(f"TI  - {sanitize_ris_value(publication.title)}")
    for author in publication.authors:
        lines.append(f"AU  - {sanitize_ris_value(_format_author(author))}")
    if publication.publication_year is not None:
        lines.append(f"PY  - {publication.publication_year}")
    if publication.venue is not None:
        venue_line = f"JO  - {sanitize_ris_value(publication.venue.name)}"
        lines.append(venue_line)
        lines.append(venue_line.replace("JO  - ", "T2  - ", 1))
    doi = _doi(publication)
    if doi:
        lines.append(f"DO  - {sanitize_ris_value(doi)}")
    if publication.urls:
        lines.append(f"UR  - {sanitize_ris_value(publication.urls[0])}")
    if publication.abstract:
        lines.append(f"AB  - {sanitize_ris_value(publication.abstract)}")
    for keyword in publication.keywords:
        lines.append(f"KW  - {sanitize_ris_value(keyword)}")
    if publication.language:
        lines.append(f"LA  - {sanitize_ris_value(publication.language)}")
    lines.append("ER  - ")
    return lines


def render_ris(publications: list[Publication]) -> str:
    """Render canonical publications as a UTF-8 (CRLF) RIS bibliography.

    Deterministic: identical input yields byte-identical output. An empty
    collection renders an empty string. Superseded records must be excluded
    upstream by ``ExportDatasetService.get_bibliographic_records``.
    """
    if not publications:
        return ""
    lines: list[str] = []
    for publication in publications:
        lines.extend(render_ris_record(publication))
    return _NEWLINE.join(lines) + _NEWLINE
