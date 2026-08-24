"""Deterministic BibTeX serialization for canonical publications (v0.6.1 Slice 1).

Pure function layer: ``render_bibtex(publications) -> str``. No I/O, no
repository access, no mutation. Output is byte-stable for identical input.

Field mapping mirrors the import direction in
``app.providers.import_file.bibtex.mapper`` for round-trip fidelity:

- entry type: inverse of ``_ENTRY_TYPE_TO_DOCUMENT_TYPE`` (fallback ``misc``);
- author: ``Family, Given`` when both names are known, else the bare name;
- journal for journal articles, booktitle otherwise (mirrors ``_map_venue``);
- volume/number/pages are absent from the domain model (plan §9, D5) and are
  never emitted empty — missing fields are omitted entirely.
"""

from __future__ import annotations

from app.domain.author import Author
from app.domain.identifiers import IdentifierType
from app.domain.publication import DocumentType, Publication

_DOCUMENT_TYPE_TO_ENTRY_TYPE: dict[DocumentType, str] = {
    DocumentType.JOURNAL_ARTICLE: "article",
    DocumentType.CONFERENCE_PAPER: "inproceedings",
    DocumentType.BOOK: "book",
    DocumentType.BOOK_CHAPTER: "incollection",
    DocumentType.DISSERTATION: "phdthesis",
    DocumentType.REPORT: "techreport",
}

_FALLBACK_ENTRY_TYPE = "misc"

# Characters protected with brace groups per plan §9 (escaping/Unicode).
_SPECIAL_CHARACTERS = "%&#~^_+"

# Control characters stripped from every emitted value (plan §17).
_CONTROL_CHARACTERS = frozenset(
    "\x00\x01\x02\x03\x04\x05\x06\x07\x08\x0b\x0c\x0e\x0f"
    "\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1b\x1c\x1d\x1e\x1f\x7f"
)

_FIELD_ORDER = (
    "title",
    "author",
    "year",
    "journal",
    "booktitle",
    "publisher",
    "doi",
    "url",
    "abstract",
    "keywords",
    "language",
)


def escape_bibtex_value(value: str) -> str:
    """Escape *value* for safe inclusion inside a braced BibTeX field value."""
    cleaned = "".join(character for character in value if character not in _CONTROL_CHARACTERS)
    cleaned = cleaned.replace("{", "{{").replace("}", "}}")
    for character in _SPECIAL_CHARACTERS:
        cleaned = cleaned.replace(character, "{" + character + "}")
    return cleaned


def _ascii_key_token(value: str) -> str:
    return "".join(character.lower() for character in value if character.isascii() and character.isalnum())


def _first_author_family(publication: Publication) -> str:
    for author in publication.authors:
        candidate = author.family_name or author.display_name
        token = _ascii_key_token(candidate)
        if token:
            return token
    return ""


def _first_title_word(publication: Publication) -> str:
    for word in publication.title.split():
        token = _ascii_key_token(word)
        if token:
            return token
    return ""


def citation_key_base(publication: Publication) -> str:
    """Deterministic citation-key base: first family, year, first title word."""
    year = str(publication.publication_year) if publication.publication_year is not None else ""
    base = _ascii_key_token("".join([_first_author_family(publication), year, _first_title_word(publication)]))
    return base or "item"


def assign_citation_keys(publications: list[Publication]) -> list[str]:
    """Assign deterministic, collision-safe keys ordered by ascending record_id.

    The first occurrence of a base key (in ascending ``str(record_id)`` order)
    keeps the bare base; subsequent occurrences receive ``-b``, ``-c``, …
    (numeric fallback beyond ``z``). Assignment depends only on record ids,
    never on input ordering.
    """
    ranked = sorted(publications, key=lambda publication: str(publication.record_id))
    occurrences: dict[str, int] = {}
    keys_by_record: dict[str, str] = {}
    for publication in ranked:
        base = citation_key_base(publication)
        index = occurrences.get(base, 0)
        occurrences[base] = index + 1
        if index == 0:
            key = base
        elif index <= 25:
            key = f"{base}-{chr(ord('a') + index)}"
        else:
            key = f"{base}-{index + 1}"
        keys_by_record[str(publication.record_id)] = key
    return [keys_by_record[str(publication.record_id)] for publication in publications]


def _format_author(author: Author) -> str:
    if author.family_name and author.given_name:
        return f"{author.family_name}, {author.given_name}"
    if author.family_name:
        return author.family_name
    return author.display_name


def _entry_type(publication: Publication) -> str:
    if publication.document_type is None:
        return _FALLBACK_ENTRY_TYPE
    return _DOCUMENT_TYPE_TO_ENTRY_TYPE.get(publication.document_type, _FALLBACK_ENTRY_TYPE)


def _doi(publication: Publication) -> str | None:
    return next(
        (identifier.value for identifier in publication.identifiers if identifier.type is IdentifierType.DOI),
        None,
    )


def _field_values(publication: Publication) -> dict[str, str]:
    values: dict[str, str] = {"title": publication.title}

    if publication.authors:
        values["author"] = " and ".join(_format_author(author) for author in publication.authors)
    if publication.publication_year is not None:
        values["year"] = str(publication.publication_year)

    venue_name = publication.venue.name if publication.venue else None
    if venue_name:
        field = "journal" if publication.document_type is DocumentType.JOURNAL_ARTICLE else "booktitle"
        values[field] = venue_name

    publisher = publication.publisher or (publication.venue.publisher if publication.venue else None)
    if publisher:
        values["publisher"] = publisher

    doi = _doi(publication)
    if doi:
        values["doi"] = doi
    if publication.urls:
        values["url"] = publication.urls[0]
    if publication.abstract:
        values["abstract"] = publication.abstract
    if publication.keywords:
        values["keywords"] = ", ".join(publication.keywords)
    if publication.language:
        values["language"] = publication.language
    return values


def _render_entry(entry_type: str, citation_key: str, values: dict[str, str]) -> str:
    lines = [f"@{entry_type}{{{citation_key},"]
    ordered_fields = [field for field in _FIELD_ORDER if field in values]
    for position, field in enumerate(ordered_fields):
        terminator = "," if position < len(ordered_fields) - 1 else ""
        lines.append(f"  {field} = {{{escape_bibtex_value(values[field])}}}{terminator}")
    lines.append("}")
    return "\n".join(lines)


def render_bibtex(publications: list[Publication]) -> str:
    """Render canonical publications as a UTF-8 BibTeX bibliography.

    Deterministic: identical input yields byte-identical output. An empty
    collection renders an empty string. Superseded records must be excluded
    upstream by ``ExportDatasetService.get_bibliographic_records``.
    """
    keys = assign_citation_keys(publications)
    entries: list[str] = []
    for publication, citation_key in zip(publications, keys):
        entries.append(_render_entry(_entry_type(publication), citation_key, _field_values(publication)))
    if not entries:
        return ""
    return "\n\n".join(entries) + "\n"
