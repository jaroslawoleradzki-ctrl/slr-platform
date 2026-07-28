from app.modules.normalize.service import (
    normalize_doi as legacy_normalize_doi,
    normalize_title,
)
from app.normalization import normalize_doi


def test_normalize_doi() -> None:
    assert normalize_doi("https://doi.org/10.1234/ABC") == "10.1234/abc"


def test_legacy_normalize_doi_import_matches_canonical_api() -> None:
    value = " DOI:10.1234/ABC "

    assert legacy_normalize_doi(value) == normalize_doi(value)


def test_normalize_title() -> None:
    assert normalize_title("Lean: Energy!") == "lean energy"
