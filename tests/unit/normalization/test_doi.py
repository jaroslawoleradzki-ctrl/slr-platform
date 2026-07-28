import pytest

from app.normalization import DoiNormalizer, Normalizer, normalize_doi


def test_normalizes_canonical_doi_to_lowercase() -> None:
    assert normalize_doi("10.1000/Example") == "10.1000/example"


def test_trims_surrounding_whitespace() -> None:
    assert normalize_doi("  10.1000/Example  ") == "10.1000/example"


@pytest.mark.parametrize(
    "prefix",
    [
        "https://doi.org/",
        "http://doi.org/",
        "https://dx.doi.org/",
        "http://dx.doi.org/",
        "doi:",
    ],
)
def test_removes_supported_prefixes(prefix: str) -> None:
    assert normalize_doi(f"{prefix}10.1000/Example") == "10.1000/example"


def test_prefix_matching_is_case_insensitive() -> None:
    assert normalize_doi("HTTPS://DOI.ORG/10.1000/Example") == "10.1000/example"


def test_removes_prefix_only_at_the_start() -> None:
    assert normalize_doi("prefix-doi:10.1000/Example") == (
        "prefix-doi:10.1000/example"
    )


@pytest.mark.parametrize(
    "value",
    [
        "https://doi.org/",
        "http://doi.org/",
        "https://dx.doi.org/",
        "http://dx.doi.org/",
        "doi:",
        "DOI:",
    ],
)
def test_prefix_without_doi_returns_none(value: str) -> None:
    assert normalize_doi(value) is None


@pytest.mark.parametrize("value", ["", " ", "\t\n"])
def test_blank_value_returns_none(value: str) -> None:
    assert normalize_doi(value) is None


@pytest.mark.parametrize("value", [None, 123, True, [], {}])
def test_non_string_value_returns_none(value: object) -> None:
    assert normalize_doi(value) is None


@pytest.mark.parametrize(
    "value",
    [
        "10.1000/Example",
        " HTTPS://DOI.ORG/10.1000/Example ",
        "prefix-doi:10.1000/Example",
        "doi:",
        None,
    ],
)
def test_normalization_is_idempotent(value: object) -> None:
    normalized = normalize_doi(value)

    assert normalize_doi(normalized) == normalized


def test_normalization_is_deterministic() -> None:
    value = " DOI: 10.1000/Example "

    assert normalize_doi(value) == normalize_doi(value)


def test_doi_normalizer_satisfies_structural_contract() -> None:
    normalizer: Normalizer[object, str | None] = DoiNormalizer()

    assert normalizer.normalize("DOI:10.1000/Example") == "10.1000/example"
