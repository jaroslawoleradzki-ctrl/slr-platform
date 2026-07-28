from copy import deepcopy

import pytest

from app.domain import Affiliation, Author, Identifier, IdentifierType
from app.normalization import AuthorNormalizer, Normalizer, normalize_author


def _author(
    *,
    display_name: str = "  John   Smith  ",
    given_name: str | None = " John   A. ",
    family_name: str | None = " Smith ",
) -> Author:
    return Author(
        display_name=display_name,
        given_name=given_name,
        family_name=family_name,
        identifiers=[
            Identifier(type=IdentifierType.ORCID, value="0000-0002-1825-0097"),
            Identifier(
                type=IdentifierType.OTHER,
                value="A1",
                source="provider",
            ),
        ],
        affiliations=[
            Affiliation(name="First Institute"),
            Affiliation(name="Second Institute"),
        ],
    )


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("  John   Smith  ", "John Smith"),
        ("John\tSmith", "John Smith"),
        ("John\nSmith", "John Smith"),
        ("John \t\n Smith", "John Smith"),
    ],
)
def test_normalizes_display_name_whitespace(value: str, expected: str) -> None:
    assert normalize_author(_author(display_name=value)).display_name == expected


def test_normalizes_given_and_family_name_whitespace() -> None:
    result = normalize_author(
        _author(
            display_name="SMITH, JOHN",
            given_name=" JOHN \t A. ",
            family_name=" SMITH \n JR. ",
        )
    )

    assert result.given_name == "JOHN A."
    assert result.family_name == "SMITH JR."


@pytest.mark.parametrize(
    ("given_name", "family_name"),
    [
        (None, "Smith"),
        ("John", None),
        (None, None),
    ],
)
def test_preserves_missing_optional_name_parts(
    given_name: str | None,
    family_name: str | None,
) -> None:
    result = normalize_author(
        _author(given_name=given_name, family_name=family_name)
    )

    assert result.given_name == given_name
    assert result.family_name == family_name


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("SMITH,   JOHN", "SMITH, JOHN"),
        ("Łukasz   O’Connor-Smith", "Łukasz O’Connor-Smith"),
        ("J.   Smith   Jr.", "J. Smith Jr."),
        ("van   der   Waals", "van der Waals"),
        ("von   Neumann", "von Neumann"),
        ("de   la   Cruz", "de la Cruz"),
        ("Institute   of   Energy   Research", "Institute of Energy Research"),
    ],
)
def test_preserves_name_content_while_collapsing_whitespace(
    value: str,
    expected: str,
) -> None:
    assert normalize_author(_author(display_name=value)).display_name == expected


def test_does_not_reconstruct_or_parse_display_name() -> None:
    result = normalize_author(
        _author(
            display_name="SMITH,   JOHN",
            given_name="Different",
            family_name=None,
        )
    )

    assert result.display_name == "SMITH, JOHN"
    assert result.given_name == "Different"
    assert result.family_name is None


def test_normalization_is_idempotent() -> None:
    author = _author(display_name="  J.   Smith   Jr.  ")

    assert normalize_author(normalize_author(author)) == normalize_author(author)


def test_normalization_is_deterministic() -> None:
    author = _author(display_name="Łukasz   O’Connor-Smith")

    assert normalize_author(author) == normalize_author(author)


def test_author_normalizer_satisfies_structural_contract() -> None:
    normalizer: Normalizer[Author, Author] = AuthorNormalizer()

    assert normalizer.normalize(_author()).display_name == "John Smith"


def test_returns_new_deep_copy_without_mutating_input() -> None:
    author = _author()
    original = deepcopy(author)

    result = normalize_author(author)

    assert result is not author
    assert author == original
    assert result.identifiers == author.identifiers
    assert result.affiliations == author.affiliations
    assert result.identifiers is not author.identifiers
    assert result.affiliations is not author.affiliations
    assert result.identifiers[0] is not author.identifiers[0]
    assert result.affiliations[0] is not author.affiliations[0]


def test_preserves_identifier_and_affiliation_order() -> None:
    author = _author()
    result = normalize_author(author)

    assert [identifier.value for identifier in result.identifiers] == [
        "0000-0002-1825-0097",
        "A1",
    ]
    assert [affiliation.name for affiliation in result.affiliations] == [
        "First Institute",
        "Second Institute",
    ]


def test_mutating_result_lists_does_not_change_input_lists() -> None:
    author = _author()
    result = normalize_author(author)

    result.identifiers.append(
        Identifier(type=IdentifierType.OTHER, value="new")
    )
    result.affiliations.append(Affiliation(name="New Institute"))

    assert [identifier.value for identifier in author.identifiers] == [
        "0000-0002-1825-0097",
        "A1",
    ]
    assert [affiliation.name for affiliation in author.affiliations] == [
        "First Institute",
        "Second Institute",
    ]


def test_preserves_full_value_outside_normalized_text_fields() -> None:
    author = _author()
    result = normalize_author(author)

    assert result.identifiers == author.identifiers
    assert result.affiliations == author.affiliations
