import pytest

from app.normalization import Normalizer, OrcidNormalizer, normalize_orcid


def test_preserves_canonical_orcid() -> None:
    assert normalize_orcid("0000-0002-1825-0097") == "0000-0002-1825-0097"


@pytest.mark.parametrize(
    "prefix",
    [
        "https://orcid.org/",
        "http://orcid.org/",
    ],
)
def test_removes_supported_prefixes(prefix: str) -> None:
    assert normalize_orcid(f"{prefix}0000-0002-1825-0097") == (
        "0000-0002-1825-0097"
    )


def test_prefix_matching_is_case_insensitive() -> None:
    assert normalize_orcid("HTTPS://ORCID.ORG/0000-0002-1825-0097") == (
        "0000-0002-1825-0097"
    )


def test_trims_whitespace_and_trailing_slash() -> None:
    assert normalize_orcid(" 0000-0002-1825-0097/ ") == "0000-0002-1825-0097"


def test_uppercases_only_final_x() -> None:
    assert normalize_orcid("0000-0002-1825-009x") == "0000-0002-1825-009X"


def test_does_not_remove_prefix_inside_value() -> None:
    value = "prefix-https://orcid.org/0000-0002-1825-0097"

    assert normalize_orcid(value) == value


@pytest.mark.parametrize(
    "value",
    [
        "",
        " ",
        "https://orcid.org/",
        "http://orcid.org/",
    ],
)
def test_empty_value_returns_none(value: str) -> None:
    assert normalize_orcid(value) is None


@pytest.mark.parametrize("value", [None, 123, True, [], {}])
def test_non_string_value_returns_none(value: object) -> None:
    assert normalize_orcid(value) is None


@pytest.mark.parametrize(
    "value",
    [
        "0000-0002-1825-0097",
        " HTTPS://ORCID.ORG/0000-0002-1825-009x/ ",
        "prefix-https://orcid.org/0000-0002-1825-0097",
        "https://orcid.org/",
        None,
    ],
)
def test_normalization_is_idempotent(value: object) -> None:
    normalized = normalize_orcid(value)

    assert normalize_orcid(normalized) == normalized


def test_normalization_is_deterministic() -> None:
    value = " HTTPS://ORCID.ORG/0000-0002-1825-009x/ "

    assert normalize_orcid(value) == normalize_orcid(value)


def test_orcid_normalizer_satisfies_structural_contract() -> None:
    normalizer: Normalizer[object, str | None] = OrcidNormalizer()

    assert normalizer.normalize("0000-0002-1825-009x") == (
        "0000-0002-1825-009X"
    )
