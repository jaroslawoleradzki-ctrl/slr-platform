from copy import deepcopy

import pytest

from app.domain.identifiers import Identifier, IdentifierType
from app.domain.publication import Publication
from app.services.publication_merge_policy import PublicationMergePolicy
from app.services.result_merger import ResultMerger


def _publication(
    title: str,
    *,
    identifiers: list[Identifier] | None = None,
) -> Publication:
    return Publication(title=title, identifiers=identifiers or [])


def _doi(value: str) -> Identifier:
    return Identifier(type=IdentifierType.DOI, value=value)


def test_merge_empty_sequence() -> None:
    assert ResultMerger().merge([]) == []


def test_merge_preserves_distinct_publications_and_identity() -> None:
    publications = [
        _publication("A", identifiers=[_doi("10.1000/a")]),
        _publication("B", identifiers=[_doi("10.1000/b")]),
        _publication("C", identifiers=[_doi("10.1000/c")]),
    ]

    result = ResultMerger().merge(publications)

    assert result == publications
    assert result is not publications
    assert all(actual is expected for actual, expected in zip(result, publications))


def test_merge_same_doi_keeps_first_object() -> None:
    first = _publication("First", identifiers=[_doi("10.1000/same")])
    duplicate = _publication("Duplicate", identifiers=[_doi("10.1000/same")])

    result = ResultMerger().merge([first, duplicate])

    assert result == [first]
    assert result[0] is first


def test_merge_normalizes_doi_case() -> None:
    first = _publication("First", identifiers=[_doi("10.1000/ABC")])
    duplicate = _publication("Duplicate", identifiers=[_doi("10.1000/abc")])

    assert ResultMerger().merge([first, duplicate]) == [first]


def test_merge_normalizes_supported_doi_prefixes() -> None:
    first = _publication(
        "First",
        identifiers=[_doi("https://doi.org/10.1000/Example")],
    )
    second = _publication("Second", identifiers=[_doi("doi:10.1000/example")])
    third = _publication("Third", identifiers=[_doi("10.1000/EXAMPLE")])

    assert ResultMerger().merge([first, second, third]) == [first]


def test_merge_keeps_publications_without_doi_separate() -> None:
    first = _publication("Same title")
    second = _publication("Same title")

    result = ResultMerger().merge([first, second])

    assert result == [first, second]
    assert result[0] is first
    assert result[1] is second


def test_merge_preserves_mixed_first_occurrence_order() -> None:
    no_doi_first = _publication("No DOI first")
    doi_first = _publication("DOI first", identifiers=[_doi("10.1000/a")])
    no_doi_second = _publication("No DOI second")
    doi_duplicate = _publication(
        "DOI duplicate",
        identifiers=[_doi("10.1000/A")],
    )
    doi_second = _publication("DOI second", identifiers=[_doi("10.1000/b")])

    result = ResultMerger().merge(
        [
            no_doi_first,
            doi_first,
            no_doi_second,
            doi_duplicate,
            doi_second,
        ]
    )

    assert result == [no_doi_first, doi_first, no_doi_second, doi_second]


def test_merge_skips_multiple_duplicates_of_one_doi() -> None:
    first = _publication("First", identifiers=[_doi("10.1000/a")])
    second = _publication("Second", identifiers=[_doi("10.1000/a")])
    third = _publication("Third", identifiers=[_doi("10.1000/a")])

    assert ResultMerger().merge([first, second, third]) == [first]


def test_merge_keeps_same_metadata_with_different_dois() -> None:
    first = _publication("Same", identifiers=[_doi("10.1000/a")])
    second = _publication("Same", identifiers=[_doi("10.1000/b")])

    assert ResultMerger().merge([first, second]) == [first, second]


def test_merge_uses_first_doi_and_ignores_other_identifier_types() -> None:
    first = _publication(
        "First",
        identifiers=[
            Identifier(type=IdentifierType.PMID, value="10.1000/shared"),
            _doi("10.1000/first"),
            _doi("10.1000/later"),
        ],
    )
    duplicate = _publication(
        "Duplicate",
        identifiers=[_doi("10.1000/FIRST")],
    )
    matches_ignored_doi = _publication(
        "Matches later DOI",
        identifiers=[_doi("10.1000/later")],
    )

    result = ResultMerger().merge([first, duplicate, matches_ignored_doi])

    assert result == [first, matches_ignored_doi]


@pytest.mark.parametrize(
    "identifier_type",
    [IdentifierType.PMID, IdentifierType.OPENALEX],
)
def test_merge_does_not_deduplicate_non_doi_identifiers(
    identifier_type: IdentifierType,
) -> None:
    first = _publication(
        "First",
        identifiers=[Identifier(type=identifier_type, value="shared")],
    )
    second = _publication(
        "Second",
        identifiers=[Identifier(type=identifier_type, value="shared")],
    )

    assert ResultMerger().merge([first, second]) == [first, second]


def test_merge_does_not_mutate_inputs_or_merge_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = _publication("First", identifiers=[_doi("10.1000/shared")])
    second = _publication(
        "Richer metadata",
        identifiers=[_doi("10.1000/shared")],
    )
    publications = [first, second]
    before = deepcopy(publications)

    def fail_if_called(
        self: PublicationMergePolicy,
        first: Publication,
        second: Publication,
    ) -> Publication:
        raise AssertionError("PublicationMergePolicy must not be called")

    monkeypatch.setattr(PublicationMergePolicy, "merge", fail_if_called)
    result = ResultMerger().merge(publications)

    assert result == [first]
    assert result[0] is first
    assert publications == before
