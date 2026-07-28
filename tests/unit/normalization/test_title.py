import pytest

from app.normalization import Normalizer, TitleNormalizer, normalize_title


def test_normalizes_basic_title_to_lowercase() -> None:
    assert normalize_title("Lean Manufacturing") == "lean manufacturing"


def test_removes_leading_and_trailing_whitespace() -> None:
    assert normalize_title("  Lean Manufacturing  ") == "lean manufacturing"


def test_collapses_multiple_spaces() -> None:
    assert normalize_title("Lean    Manufacturing") == "lean manufacturing"


def test_collapses_tabs_and_newlines() -> None:
    assert normalize_title("Lean\tManufacturing\nEnergy") == (
        "lean manufacturing energy"
    )


@pytest.mark.parametrize(
    "value",
    [
        "Lean, Manufacturing.",
        "Lean-Manufacturing",
        "Lean: Manufacturing",
        "Lean (Manufacturing)",
        "Lean & Manufacturing",
    ],
)
def test_replaces_punctuation_and_symbols_with_spaces(value: str) -> None:
    assert normalize_title(value) == "lean manufacturing"


def test_preserves_digits() -> None:
    assert normalize_title("Industry 4.0") == "industry 4 0"


def test_applies_unicode_nfkc_normalization() -> None:
    assert normalize_title("ＡＢＣ") == "abc"


def test_applies_unicode_casefold() -> None:
    assert normalize_title("Straße") == "strasse"


def test_preserves_diacritics_without_transliteration() -> None:
    assert normalize_title("Efektywność energetyczna łodzi") == (
        "efektywność energetyczna łodzi"
    )


@pytest.mark.parametrize("value", ["", " ", "\t\n"])
def test_blank_title_returns_none(value: str) -> None:
    assert normalize_title(value) is None


@pytest.mark.parametrize("value", ["!", "!!!", "—:()&"])
def test_punctuation_only_title_returns_none(value: str) -> None:
    assert normalize_title(value) is None


@pytest.mark.parametrize("value", [None, 123, True, [], {}])
def test_non_string_title_returns_none(value: object) -> None:
    assert normalize_title(value) is None


@pytest.mark.parametrize(
    "value",
    [
        "Lean Manufacturing",
        "  Lean-Manufacturing: Energy!  ",
        "ＡＢＣ",
        "Straße",
        "!!!",
        None,
    ],
)
def test_normalization_is_idempotent(value: object) -> None:
    normalized = normalize_title(value)

    assert normalize_title(normalized) == normalized


def test_normalization_is_deterministic() -> None:
    value = "  Lean-Manufacturing: Efektywność 4.0  "

    assert normalize_title(value) == normalize_title(value)


def test_title_normalizer_satisfies_structural_contract() -> None:
    normalizer: Normalizer[object, str | None] = TitleNormalizer()

    assert normalizer.normalize("Lean: Energy!") == "lean energy"


def test_normalizer_does_not_mutate_input() -> None:
    value = "  Lean-Manufacturing: Energy!  "
    original = value

    normalize_title(value)

    assert value == original
