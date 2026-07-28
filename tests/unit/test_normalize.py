from app.modules.normalize.service import (
    normalize_doi as legacy_normalize_doi,
    normalize_record,
    normalize_title as legacy_normalize_title,
)
from app.domain.models import PublicationRecord
from app.normalization import normalize_doi, normalize_title


def test_normalize_doi() -> None:
    assert normalize_doi("https://doi.org/10.1234/ABC") == "10.1234/abc"


def test_legacy_normalize_doi_import_matches_canonical_api() -> None:
    value = " DOI:10.1234/ABC "

    assert legacy_normalize_doi(value) == normalize_doi(value)


def test_normalize_title() -> None:
    assert normalize_title("Lean: Energy!") == "lean energy"


def test_legacy_normalize_title_import_matches_canonical_api() -> None:
    value = "  Lean-Manufacturing: Energy!  "

    assert legacy_normalize_title(value) == normalize_title(value)


def test_normalize_record_uses_canonical_title_normalizer() -> None:
    record = PublicationRecord(
        title="  Lean-Manufacturing: Energy!  ",
        authors=["Jane Doe"],
        publication_year=2024,
        doi="DOI:10.1234/ABC",
    )

    result = normalize_record(record)

    assert result is record
    assert result.title_normalized == normalize_title(record.title)
    assert result.doi == "10.1234/abc"
    assert result.title == "  Lean-Manufacturing: Energy!  "
    assert result.authors == ["Jane Doe"]
    assert result.publication_year == 2024
