import pytest

from app.domain import IdentifierType
from app.domain.publication import DocumentType
from app.providers.import_file.ris.mapper import map_ris_record


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _record(**kwargs: list[str]) -> dict[str, list[str]]:
    """Build a minimal RIS record dict from keyword arguments."""
    return {k: v for k, v in kwargs.items()}


def _minimal(**extra: list[str]) -> dict[str, list[str]]:
    """Build the smallest valid record: TY + TI, plus any extra tags."""
    base: dict[str, list[str]] = {"TY": ["JOUR"], "TI": ["Test Title"]}
    base.update(extra)
    return base


# ---------------------------------------------------------------------------
# Happy-path: full record
# ---------------------------------------------------------------------------


def test_map_ris_record_full_journal_record() -> None:
    record = {
        "TY": ["JOUR"],
        "TI": ["  Lean Manufacturing  "],
        "AB": ["  An abstract.  "],
        "AU": ["Smith, John", "Doe, Jane"],
        "PY": ["2021"],
        "DO": ["  10.1000/lean-2021  "],
    }

    pub = map_ris_record(record, source="google_scholar")

    assert pub.title == "Lean Manufacturing"
    assert pub.abstract == "An abstract."
    assert len(pub.authors) == 2
    assert pub.authors[0].display_name == "Smith, John"
    assert pub.authors[1].display_name == "Doe, Jane"
    assert pub.publication_year == 2021
    assert pub.document_type == DocumentType.JOURNAL_ARTICLE
    assert len(pub.identifiers) == 1
    assert pub.identifiers[0].type == IdentifierType.DOI
    assert pub.identifiers[0].value == "10.1000/lean-2021"
    assert len(pub.provenance) == 1
    assert pub.provenance[0].source == "google_scholar"
    assert pub.provenance[0].source_record_id == "10.1000/lean-2021"


def test_map_ris_record_minimal_record() -> None:
    """Only title and source are strictly required."""
    record = {"TI": ["Minimal Title"]}

    pub = map_ris_record(record, source="zotero")

    assert pub.title == "Minimal Title"
    assert pub.abstract is None
    assert pub.authors == []
    assert pub.publication_year is None
    assert pub.document_type == DocumentType.OTHER  # TY absent → OTHER
    assert pub.identifiers == []
    assert pub.provenance[0].source_record_id == "Minimal Title"  # title fallback


# ---------------------------------------------------------------------------
# Title precedence
# ---------------------------------------------------------------------------


def test_map_ris_record_title_ti_wins_over_t1() -> None:
    record = {"TY": ["JOUR"], "TI": ["Primary Title"], "T1": ["Alternate Title"]}
    pub = map_ris_record(record, source="s")
    assert pub.title == "Primary Title"


def test_map_ris_record_title_t1_fallback() -> None:
    record = {"TY": ["JOUR"], "T1": ["T1 Title"]}
    pub = map_ris_record(record, source="s")
    assert pub.title == "T1 Title"


def test_map_ris_record_title_ct_fallback() -> None:
    record = {"TY": ["BOOK"], "CT": ["Book Caption Title"]}
    pub = map_ris_record(record, source="s")
    assert pub.title == "Book Caption Title"


# ---------------------------------------------------------------------------
# Abstract precedence
# ---------------------------------------------------------------------------


def test_map_ris_record_abstract_from_ab() -> None:
    pub = map_ris_record(_minimal(AB=["The abstract."]), source="s")
    assert pub.abstract == "The abstract."


def test_map_ris_record_abstract_n2_fallback() -> None:
    pub = map_ris_record(_minimal(N2=["N2 abstract."]), source="s")
    assert pub.abstract == "N2 abstract."


def test_map_ris_record_abstract_ab_wins_over_n2() -> None:
    pub = map_ris_record(_minimal(AB=["AB abstract."], N2=["N2 abstract."]), source="s")
    assert pub.abstract == "AB abstract."


# ---------------------------------------------------------------------------
# Authors
# ---------------------------------------------------------------------------


def test_map_ris_record_authors_comma_format_family_given() -> None:
    pub = map_ris_record(_minimal(AU=["Smith, John"]), source="s")
    assert pub.authors[0].display_name == "Smith, John"
    assert pub.authors[0].family_name == "Smith"
    assert pub.authors[0].given_name == "John"


def test_map_ris_record_authors_comma_format_initial() -> None:
    pub = map_ris_record(_minimal(AU=["Smith, J."]), source="s")
    assert pub.authors[0].family_name == "Smith"
    assert pub.authors[0].given_name == "J."


def test_map_ris_record_authors_comma_format_multiple_given_parts() -> None:
    pub = map_ris_record(_minimal(AU=["Smith, John A."]), source="s")
    assert pub.authors[0].family_name == "Smith"
    assert pub.authors[0].given_name == "John A."


def test_map_ris_record_authors_plain_format_no_split() -> None:
    pub = map_ris_record(_minimal(AU=["John Smith"]), source="s")
    assert pub.authors[0].display_name == "John Smith"
    assert pub.authors[0].family_name is None
    assert pub.authors[0].given_name is None


def test_map_ris_record_authors_single_token() -> None:
    pub = map_ris_record(_minimal(AU=["Smith"]), source="s")
    assert pub.authors[0].display_name == "Smith"
    assert pub.authors[0].family_name is None
    assert pub.authors[0].given_name is None


def test_map_ris_record_authors_au_wins_over_a1() -> None:
    pub = map_ris_record(
        _minimal(AU=["Smith, John"], A1=["Doe, Jane"]),
        source="s",
    )
    assert len(pub.authors) == 1
    assert pub.authors[0].display_name == "Smith, John"


def test_map_ris_record_authors_a1_fallback_when_au_absent() -> None:
    pub = map_ris_record(_minimal(A1=["Doe, Jane"]), source="s")
    assert len(pub.authors) == 1
    assert pub.authors[0].display_name == "Doe, Jane"


def test_map_ris_record_authors_blank_entries_skipped() -> None:
    pub = map_ris_record(_minimal(AU=["Smith, John", "   ", "Doe, Jane"]), source="s")
    assert len(pub.authors) == 2
    assert pub.authors[0].display_name == "Smith, John"
    assert pub.authors[1].display_name == "Doe, Jane"


def test_map_ris_record_authors_multiple_repeated_au() -> None:
    pub = map_ris_record(
        _minimal(AU=["Smith, John", "Doe, Jane", "Brown, Alice"]),
        source="s",
    )
    assert len(pub.authors) == 3


# ---------------------------------------------------------------------------
# Publication year
# ---------------------------------------------------------------------------


def test_map_ris_record_year_from_py() -> None:
    pub = map_ris_record(_minimal(PY=["2023"]), source="s")
    assert pub.publication_year == 2023


def test_map_ris_record_year_from_y1_when_py_absent() -> None:
    record = {k: v for k, v in _minimal().items() if k != "PY"}
    record["Y1"] = ["2020"]
    pub = map_ris_record(record, source="s")
    assert pub.publication_year == 2020


def test_map_ris_record_year_py_wins_over_y1() -> None:
    pub = map_ris_record(_minimal(PY=["2023"], Y1=["2019"]), source="s")
    assert pub.publication_year == 2023


def test_map_ris_record_year_malformed_ignored() -> None:
    pub = map_ris_record(_minimal(PY=["not-a-year"]), source="s")
    assert pub.publication_year is None


def test_map_ris_record_year_out_of_range_ignored() -> None:
    pub = map_ris_record(_minimal(PY=["999"]), source="s")
    assert pub.publication_year is None
    pub2 = map_ris_record(_minimal(PY=["10000"]), source="s")
    assert pub2.publication_year is None


def test_map_ris_record_year_absent_is_none() -> None:
    pub = map_ris_record({"TI": ["Title"]}, source="s")
    assert pub.publication_year is None


# ---------------------------------------------------------------------------
# Document type
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "ty, expected",
    [
        ("JOUR", DocumentType.JOURNAL_ARTICLE),
        ("JFULL", DocumentType.JOURNAL_ARTICLE),
        ("MGZN", DocumentType.JOURNAL_ARTICLE),
        ("NEWS", DocumentType.JOURNAL_ARTICLE),
        ("CONF", DocumentType.CONFERENCE_PAPER),
        ("CPAPER", DocumentType.CONFERENCE_PAPER),
        ("BOOK", DocumentType.BOOK),
        ("CHAP", DocumentType.BOOK_CHAPTER),
        ("ECHAP", DocumentType.BOOK_CHAPTER),
        ("THES", DocumentType.DISSERTATION),
        ("RPRT", DocumentType.REPORT),
        ("UNPB", DocumentType.PREPRINT),
        ("DATA", DocumentType.DATASET),
    ],
)
def test_map_ris_record_document_type_mapping(ty: str, expected: DocumentType) -> None:
    pub = map_ris_record({"TY": [ty], "TI": ["Title"]}, source="s")
    assert pub.document_type == expected


def test_map_ris_record_unknown_ty_maps_to_other() -> None:
    pub = map_ris_record({"TY": ["XYZZY"], "TI": ["Title"]}, source="s")
    assert pub.document_type == DocumentType.OTHER


def test_map_ris_record_absent_ty_maps_to_other() -> None:
    pub = map_ris_record({"TI": ["Title"]}, source="s")
    assert pub.document_type == DocumentType.OTHER


# ---------------------------------------------------------------------------
# DOI identifier
# ---------------------------------------------------------------------------


def test_map_ris_record_doi_stripped_and_lowercased() -> None:
    pub = map_ris_record(_minimal(DO=["  10.1000/XYZ-123  "]), source="s")
    assert len(pub.identifiers) == 1
    assert pub.identifiers[0].type == IdentifierType.DOI
    assert pub.identifiers[0].value == "10.1000/xyz-123"


def test_map_ris_record_doi_https_prefix_stripped() -> None:
    pub = map_ris_record(_minimal(DO=["https://doi.org/10.1000/xyz"]), source="s")
    assert pub.identifiers[0].value == "10.1000/xyz"


def test_map_ris_record_doi_http_prefix_stripped() -> None:
    pub = map_ris_record(_minimal(DO=["http://doi.org/10.1000/xyz"]), source="s")
    assert pub.identifiers[0].value == "10.1000/xyz"


def test_map_ris_record_doi_dx_doi_prefix_stripped() -> None:
    pub = map_ris_record(_minimal(DO=["https://dx.doi.org/10.1000/xyz"]), source="s")
    assert pub.identifiers[0].value == "10.1000/xyz"


def test_map_ris_record_doi_colon_prefix_stripped() -> None:
    pub = map_ris_record(_minimal(DO=["doi:10.1000/xyz"]), source="s")
    assert pub.identifiers[0].value == "10.1000/xyz"


def test_map_ris_record_doi_absent_no_identifier() -> None:
    pub = map_ris_record({"TI": ["Title"]}, source="s")
    assert pub.identifiers == []


# ---------------------------------------------------------------------------
# Provenance
# ---------------------------------------------------------------------------


def test_map_ris_record_provenance_source_stored() -> None:
    pub = map_ris_record(_minimal(DO=["10.1000/xyz"]), source="google_scholar")
    assert pub.provenance[0].source == "google_scholar"


def test_map_ris_record_provenance_source_record_id_is_doi_when_present() -> None:
    pub = map_ris_record(_minimal(DO=["10.1000/xyz"]), source="s")
    assert pub.provenance[0].source_record_id == "10.1000/xyz"


def test_map_ris_record_provenance_source_record_id_is_doi_normalized() -> None:
    pub = map_ris_record(_minimal(DO=["  https://doi.org/10.1000/XYZ  "]), source="s")
    assert pub.provenance[0].source_record_id == "10.1000/xyz"


def test_map_ris_record_provenance_source_record_id_falls_back_to_title() -> None:
    """When no DOI is present, the title is used as the provenance identifier."""
    pub = map_ris_record({"TI": ["A unique title"]}, source="s")
    assert pub.provenance[0].source_record_id == "A unique title"


def test_map_ris_record_provenance_retrieved_at_is_utc_aware() -> None:
    pub = map_ris_record(_minimal(), source="s")
    assert pub.provenance[0].retrieved_at.tzinfo is not None
    assert pub.provenance[0].retrieved_at.utcoffset() is not None


# ---------------------------------------------------------------------------
# Error-path tests
# ---------------------------------------------------------------------------


def test_map_ris_record_missing_title_raises_value_error() -> None:
    with pytest.raises(ValueError, match="missing a title"):
        map_ris_record({"TY": ["JOUR"]}, source="s")


def test_map_ris_record_all_title_tags_blank_raises_value_error() -> None:
    with pytest.raises(ValueError, match="missing a title"):
        map_ris_record({"TY": ["JOUR"], "TI": ["   "], "T1": [""], "CT": ["  "]}, source="s")


def test_map_ris_record_blank_source_raises_value_error() -> None:
    with pytest.raises(ValueError, match="source must be a non-blank string"):
        map_ris_record(_minimal(), source="")


def test_map_ris_record_whitespace_only_source_raises_value_error() -> None:
    with pytest.raises(ValueError, match="source must be a non-blank string"):
        map_ris_record(_minimal(), source="   ")
