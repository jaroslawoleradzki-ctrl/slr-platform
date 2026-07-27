import pytest

from app.domain import IdentifierType
from app.domain.publication import DocumentType
from app.providers.import_file.ris.google_scholar import import_ris


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SINGLE_RECORD = """\
TY  - JOUR
TI  - Lean Manufacturing in the Automotive Sector
AU  - Smith, John
AU  - Doe, Jane
PY  - 2021
DO  - 10.1000/lean-2021
AB  - A study of lean methods.
ER  - """

_TWO_RECORDS = """\
TY  - JOUR
TI  - First Paper
AU  - Alpha, Alice
PY  - 2020
DO  - 10.1000/first
ER  - 

TY  - CONF
TI  - Second Paper
AU  - Beta, Bob
PY  - 2019
ER  - """


# ---------------------------------------------------------------------------
# Happy-path: basic end-to-end
# ---------------------------------------------------------------------------


def test_import_ris_empty_content_returns_empty_list() -> None:
    assert import_ris("") == []
    assert import_ris("   \n\n   ") == []


def test_import_ris_single_record_returns_one_publication() -> None:
    pubs = import_ris(_SINGLE_RECORD)
    assert len(pubs) == 1


def test_import_ris_two_records_returns_two_publications() -> None:
    pubs = import_ris(_TWO_RECORDS)
    assert len(pubs) == 2


def test_import_ris_title_mapped() -> None:
    pubs = import_ris(_SINGLE_RECORD)
    assert pubs[0].title == "Lean Manufacturing in the Automotive Sector"


def test_import_ris_abstract_mapped() -> None:
    pubs = import_ris(_SINGLE_RECORD)
    assert pubs[0].abstract == "A study of lean methods."


def test_import_ris_authors_mapped() -> None:
    pubs = import_ris(_SINGLE_RECORD)
    assert len(pubs[0].authors) == 2
    assert pubs[0].authors[0].display_name == "Smith, John"
    assert pubs[0].authors[1].display_name == "Doe, Jane"


def test_import_ris_year_mapped() -> None:
    pubs = import_ris(_SINGLE_RECORD)
    assert pubs[0].publication_year == 2021


def test_import_ris_document_type_mapped() -> None:
    pubs = import_ris(_SINGLE_RECORD)
    assert pubs[0].document_type == DocumentType.JOURNAL_ARTICLE


def test_import_ris_doi_mapped_and_normalized() -> None:
    pubs = import_ris(_SINGLE_RECORD)
    assert len(pubs[0].identifiers) == 1
    assert pubs[0].identifiers[0].type == IdentifierType.DOI
    assert pubs[0].identifiers[0].value == "10.1000/lean-2021"


# ---------------------------------------------------------------------------
# Provenance: source must always be "google_scholar"
# ---------------------------------------------------------------------------


def test_import_ris_provenance_source_is_google_scholar() -> None:
    pubs = import_ris(_SINGLE_RECORD)
    assert pubs[0].provenance[0].source == "google_scholar"


def test_import_ris_provenance_source_is_google_scholar_for_all_records() -> None:
    pubs = import_ris(_TWO_RECORDS)
    for pub in pubs:
        assert pub.provenance[0].source == "google_scholar"


def test_import_ris_provenance_source_record_id_is_doi() -> None:
    pubs = import_ris(_SINGLE_RECORD)
    assert pubs[0].provenance[0].source_record_id == "10.1000/lean-2021"


def test_import_ris_provenance_source_record_id_falls_back_to_title() -> None:
    """Record without DO uses title as source_record_id."""
    content = "TY  - CONF\nTI  - No DOI Paper\nPY  - 2022\nER  - "
    pubs = import_ris(content)
    assert pubs[0].provenance[0].source_record_id == "No DOI Paper"


def test_import_ris_second_record_uses_conference_type() -> None:
    pubs = import_ris(_TWO_RECORDS)
    assert pubs[1].document_type == DocumentType.CONFERENCE_PAPER


def test_import_ris_record_ordering_preserved() -> None:
    pubs = import_ris(_TWO_RECORDS)
    assert pubs[0].title == "First Paper"
    assert pubs[1].title == "Second Paper"


# ---------------------------------------------------------------------------
# DOI variants passed through google_scholar import
# ---------------------------------------------------------------------------


def test_import_ris_doi_with_url_prefix_normalized() -> None:
    content = "TY  - JOUR\nTI  - A\nDO  - https://doi.org/10.1000/xyz\nER  - "
    pubs = import_ris(content)
    assert pubs[0].identifiers[0].value == "10.1000/xyz"


def test_import_ris_doi_with_doi_colon_prefix_normalized() -> None:
    content = "TY  - JOUR\nTI  - A\nDO  - doi:10.1000/xyz\nER  - "
    pubs = import_ris(content)
    assert pubs[0].identifiers[0].value == "10.1000/xyz"


# ---------------------------------------------------------------------------
# Multiline abstract survives through the full pipeline
# ---------------------------------------------------------------------------


def test_import_ris_multiline_abstract_folded() -> None:
    content = """\
TY  - JOUR
TI  - Multiline Test
AB  - First sentence.
Second sentence.
Third sentence.
ER  - """
    pubs = import_ris(content)
    assert pubs[0].abstract == "First sentence. Second sentence. Third sentence."


# ---------------------------------------------------------------------------
# Error propagation
# ---------------------------------------------------------------------------


def test_import_ris_malformed_ris_raises_value_error() -> None:
    """Structural parse error propagated from parse_ris."""
    with pytest.raises(ValueError):
        import_ris("TY  - JOUR\nTI  - Title")  # missing ER


def test_import_ris_missing_title_raises_value_error() -> None:
    """Mapping error propagated from map_ris_record."""
    with pytest.raises(ValueError, match="missing a title"):
        import_ris("TY  - JOUR\nAU  - Smith, John\nER  - ")
