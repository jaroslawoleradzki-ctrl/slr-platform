from copy import deepcopy

import pytest

from app.domain import IdentifierType
from app.domain.publication import DocumentType
from app.providers.import_file.bibtex.mapper import map_bibtex_record
from app.providers.import_file.bibtex.parser import BibTeXRecord


def _record(
    *,
    entry_type: str = "article",
    citation_key: str = "key",
    **fields: str,
) -> BibTeXRecord:
    return {
        "entry_type": entry_type,
        "citation_key": citation_key,
        "fields": {"title": "Test Title", **fields},
    }


def test_map_bibtex_record_minimal_record() -> None:
    publication = map_bibtex_record(_record(), source="bibtex")

    assert publication.title == "Test Title"
    assert publication.abstract is None
    assert publication.authors == []
    assert publication.publication_year is None
    assert publication.identifiers == []
    assert publication.venue is None


def test_map_bibtex_record_full_article() -> None:
    publication = map_bibtex_record(
        _record(
            author="Smith, John and Doe, Jane",
            abstract="An abstract.",
            year="2024",
            doi="10.1000/example",
            journal="Example Journal",
        ),
        source="bibtex",
    )

    assert publication.title == "Test Title"
    assert publication.abstract == "An abstract."
    assert len(publication.authors) == 2
    assert publication.publication_year == 2024
    assert publication.document_type == DocumentType.JOURNAL_ARTICLE
    assert publication.identifiers[0].value == "10.1000/example"
    assert publication.venue is not None
    assert publication.venue.name == "Example Journal"
    assert publication.provenance[0].source == "bibtex"


def test_map_bibtex_record_maps_title() -> None:
    publication = map_bibtex_record(_record(title="Mapped Title"), source="s")

    assert publication.title == "Mapped Title"


def test_map_bibtex_record_maps_abstract() -> None:
    publication = map_bibtex_record(_record(abstract="Mapped abstract"), source="s")

    assert publication.abstract == "Mapped abstract"


def test_map_bibtex_record_author_family_given_format() -> None:
    publication = map_bibtex_record(_record(author="Smith, John"), source="s")

    assert publication.authors[0].display_name == "Smith, John"
    assert publication.authors[0].family_name == "Smith"
    assert publication.authors[0].given_name == "John"


def test_map_bibtex_record_author_given_family_format() -> None:
    publication = map_bibtex_record(_record(author="John Smith"), source="s")

    assert publication.authors[0].display_name == "John Smith"
    assert publication.authors[0].given_name == "John"
    assert publication.authors[0].family_name == "Smith"


def test_map_bibtex_record_multiple_authors() -> None:
    publication = map_bibtex_record(
        _record(author="Smith, John and Doe, Jane and Alice Brown"),
        source="s",
    )

    assert [author.display_name for author in publication.authors] == [
        "Smith, John",
        "Doe, Jane",
        "Alice Brown",
    ]


def test_map_bibtex_record_does_not_split_and_inside_braces() -> None:
    publication = map_bibtex_record(
        _record(author="{Research and Development Group} and Smith, John"),
        source="s",
    )

    assert [author.display_name for author in publication.authors] == [
        "Research and Development Group",
        "Smith, John",
    ]


def test_map_bibtex_record_corporate_author_uses_display_name_only() -> None:
    publication = map_bibtex_record(
        _record(author="{World Health Organization}"),
        source="s",
    )

    author = publication.authors[0]
    assert author.display_name == "World Health Organization"
    assert author.given_name is None
    assert author.family_name is None


def test_map_bibtex_record_valid_year() -> None:
    publication = map_bibtex_record(_record(year="2024"), source="s")

    assert publication.publication_year == 2024


def test_map_bibtex_record_missing_year() -> None:
    publication = map_bibtex_record(_record(), source="s")

    assert publication.publication_year is None


@pytest.mark.parametrize("year", ["unknown", "24", "2024-01", "0000"])
def test_map_bibtex_record_invalid_year(year: str) -> None:
    publication = map_bibtex_record(_record(year=year), source="s")

    assert publication.publication_year is None


def test_map_bibtex_record_normalizes_doi() -> None:
    publication = map_bibtex_record(
        _record(doi=" HTTPS://DOI.ORG/10.1000/EXAMPLE "),
        source="s",
    )

    assert publication.identifiers[0].type == IdentifierType.DOI
    assert publication.identifiers[0].value == "10.1000/example"


def test_map_bibtex_record_without_doi_has_no_identifier() -> None:
    publication = map_bibtex_record(_record(), source="s")

    assert publication.identifiers == []


@pytest.mark.parametrize(
    ("entry_type", "expected"),
    [
        ("article", DocumentType.JOURNAL_ARTICLE),
        ("book", DocumentType.BOOK),
        ("inbook", DocumentType.BOOK_CHAPTER),
        ("incollection", DocumentType.BOOK_CHAPTER),
        ("inproceedings", DocumentType.CONFERENCE_PAPER),
        ("conference", DocumentType.CONFERENCE_PAPER),
        ("proceedings", DocumentType.CONFERENCE_PAPER),
        ("phdthesis", DocumentType.DISSERTATION),
        ("mastersthesis", DocumentType.DISSERTATION),
        ("techreport", DocumentType.REPORT),
        ("misc", DocumentType.OTHER),
    ],
)
def test_map_bibtex_record_document_type(
    entry_type: str,
    expected: DocumentType,
) -> None:
    publication = map_bibtex_record(_record(entry_type=entry_type), source="s")

    assert publication.document_type == expected


def test_map_bibtex_record_unknown_type_maps_to_other() -> None:
    publication = map_bibtex_record(_record(entry_type="unknown"), source="s")

    assert publication.document_type == DocumentType.OTHER


def test_map_bibtex_record_venue_from_journal() -> None:
    publication = map_bibtex_record(_record(journal="Journal"), source="s")

    assert publication.venue is not None
    assert publication.venue.name == "Journal"


def test_map_bibtex_record_venue_from_booktitle() -> None:
    publication = map_bibtex_record(_record(booktitle="Proceedings"), source="s")

    assert publication.venue is not None
    assert publication.venue.name == "Proceedings"


def test_map_bibtex_record_venue_from_publisher() -> None:
    publication = map_bibtex_record(_record(publisher="Publisher"), source="s")

    assert publication.venue is not None
    assert publication.venue.name == "Publisher"


def test_map_bibtex_record_venue_precedence() -> None:
    publication = map_bibtex_record(
        _record(journal="Journal", booktitle="Book", publisher="Publisher"),
        source="s",
    )

    assert publication.venue is not None
    assert publication.venue.name == "Journal"


def test_map_bibtex_record_provenance_uses_doi_as_source_record_id() -> None:
    publication = map_bibtex_record(
        _record(doi="https://doi.org/10.1000/EXAMPLE"),
        source="bibtex_file",
    )

    provenance = publication.provenance[0]
    assert provenance.source == "bibtex_file"
    assert provenance.source_record_id == "10.1000/example"
    assert provenance.transformation == "bibtex_to_publication"


def test_map_bibtex_record_provenance_falls_back_to_citation_key() -> None:
    publication = map_bibtex_record(
        _record(citation_key="Smith2024"),
        source="s",
    )

    assert publication.provenance[0].source_record_id == "Smith2024"


def test_map_bibtex_record_does_not_modify_input() -> None:
    record = _record(author="Smith, John", doi="10.1000/EXAMPLE")
    original = deepcopy(record)

    map_bibtex_record(record, source="s")

    assert record == original


def test_map_bibtex_record_preserves_latex_text() -> None:
    publication = map_bibtex_record(
        _record(title=r"Energy in M{\"u}nchen"),
        source="s",
    )

    assert publication.title == r"Energy in M{\"u}nchen"


def test_map_bibtex_record_preserves_nested_braces_in_title() -> None:
    publication = map_bibtex_record(
        _record(title="Lean {Manufacturing}"),
        source="s",
    )

    assert publication.title == "Lean {Manufacturing}"


def test_map_bibtex_record_missing_title_raises_value_error() -> None:
    record: BibTeXRecord = {
        "entry_type": "article",
        "citation_key": "key",
        "fields": {},
    }

    with pytest.raises(ValueError, match="missing a title"):
        map_bibtex_record(record, source="s")


def test_map_bibtex_record_blank_source_raises_value_error() -> None:
    with pytest.raises(ValueError, match="source must be a non-blank string"):
        map_bibtex_record(_record(), source=" ")


# ---------------------------------------------------------------------------
# Language field
# ---------------------------------------------------------------------------


def test_map_bibtex_record_language_from_field() -> None:
    """BibTeX language field maps to Publication.language (raw, not canonicalized)."""
    pub = map_bibtex_record(_record(language="eng"), source="s")
    assert pub.language == "eng"


def test_map_bibtex_record_language_case_preserved() -> None:
    """Language value is passed through as-is; normalization happens later."""
    pub = map_bibtex_record(_record(language="English"), source="s")
    assert pub.language == "English"


def test_map_bibtex_record_language_absent_is_none() -> None:
    """Missing language field results in None language."""
    pub = map_bibtex_record(_record(), source="s")
    assert pub.language is None


def test_map_bibtex_record_language_blank_is_none() -> None:
    """Blank language field results in None language."""
    pub = map_bibtex_record(_record(language="  "), source="s")
    assert pub.language is None


def test_map_bibtex_record_integration_with_normalization() -> None:
    """BibTeX mapper output + normalization yields canonical ISO 639-1."""
    from app.normalization import normalize_publication

    pub = map_bibtex_record(_record(language="English"), source="s")
    assert pub.language == "English"

    normalized = normalize_publication(pub)
    assert normalized.language == "en"
