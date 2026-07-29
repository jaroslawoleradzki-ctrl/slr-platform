from copy import deepcopy
from datetime import datetime, timedelta, timezone
from uuid import UUID

import pytest

from app.domain.deduplication import DuplicateGroupStatus
from app.domain.identifiers import Identifier, IdentifierType
from app.domain.publication import Publication
from app.services.duplicate_group_builder import DuplicateGroupBuilder

_TIME = datetime(2026, 7, 29, 8, 0, tzinfo=timezone.utc)


def _publication(
    number: int,
    *identifiers: tuple[IdentifierType, str],
) -> Publication:
    return Publication(
        record_id=UUID(f"00000000-0000-0000-0000-{number:012d}"),
        title=f"Publication {number}",
        identifiers=[
            Identifier(type=identifier_type, value=value)
            for identifier_type, value in identifiers
        ],
        created_at=_TIME + timedelta(minutes=number),
    )


def test_empty_input_produces_no_groups() -> None:
    assert DuplicateGroupBuilder().build([]) == []


def test_single_publication_and_unmatched_identifiers_are_omitted() -> None:
    publications = [
        _publication(1, (IdentifierType.DOI, "10.1000/one")),
        _publication(2, (IdentifierType.PMID, "two")),
        _publication(3),
    ]

    assert DuplicateGroupBuilder().build(publications) == []


def test_shared_normalized_doi_builds_pending_group() -> None:
    first = _publication(1, (IdentifierType.DOI, "10.1000/EXAMPLE"))
    second = _publication(
        2,
        (IdentifierType.DOI, "https://doi.org/10.1000/example"),
    )

    groups = DuplicateGroupBuilder().build([first, second])

    assert len(groups) == 1
    assert groups[0].publication_ids == (first.record_id, second.record_id)
    assert groups[0].status is DuplicateGroupStatus.PENDING
    assert groups[0].decision_history == ()


def test_shared_pmid_and_openalex_id_build_groups() -> None:
    pmid_first = _publication(1, (IdentifierType.PMID, "PMID-1"))
    pmid_second = _publication(2, (IdentifierType.PMID, "PMID-1"))
    openalex_first = _publication(3, (IdentifierType.OPENALEX, "W123"))
    openalex_second = _publication(4, (IdentifierType.OPENALEX, "W123"))

    groups = DuplicateGroupBuilder().build(
        [openalex_second, pmid_second, openalex_first, pmid_first]
    )

    assert [group.publication_ids for group in groups] == [
        (pmid_first.record_id, pmid_second.record_id),
        (openalex_first.record_id, openalex_second.record_id),
    ]


def test_weak_identifiers_do_not_build_groups() -> None:
    first = _publication(1, (IdentifierType.ISSN, "1234-5678"))
    second = _publication(2, (IdentifierType.ISSN, "1234-5678"))

    assert DuplicateGroupBuilder().build([first, second]) == []


def test_transitive_strong_identifiers_build_one_connected_group() -> None:
    first = _publication(1, (IdentifierType.DOI, "10.1000/shared"))
    bridge = _publication(
        2,
        (IdentifierType.DOI, "10.1000/shared"),
        (IdentifierType.PMID, "123"),
    )
    third = _publication(3, (IdentifierType.PMID, "123"))

    groups = DuplicateGroupBuilder().build([third, first, bridge])

    assert [group.publication_ids for group in groups] == [
        (first.record_id, bridge.record_id, third.record_id)
    ]


def test_output_is_independent_of_input_order() -> None:
    publications = [
        _publication(1, (IdentifierType.DOI, "10.1000/a")),
        _publication(2, (IdentifierType.DOI, "10.1000/a")),
        _publication(3, (IdentifierType.PMID, "3")),
        _publication(4, (IdentifierType.PMID, "3")),
    ]
    builder = DuplicateGroupBuilder()

    assert builder.build(publications, created_at=_TIME) == builder.build(
        reversed(publications),
        created_at=_TIME,
    )


def test_group_identity_is_independent_of_order_and_timestamp() -> None:
    first = _publication(1, (IdentifierType.DOI, "10.1000/a"))
    second = _publication(2, (IdentifierType.DOI, "10.1000/a"))
    builder = DuplicateGroupBuilder()

    first_result = builder.build([first, second], created_at=_TIME)
    second_result = builder.build(
        [second, first],
        created_at=_TIME + timedelta(days=1),
    )

    assert first_result[0].group_id == second_result[0].group_id
    assert first_result[0].created_at == _TIME
    assert first_result[0].updated_at == _TIME


def test_explicit_created_at_is_used_for_every_group() -> None:
    publications = [
        _publication(1, (IdentifierType.DOI, "10.1000/a")),
        _publication(2, (IdentifierType.DOI, "10.1000/a")),
        _publication(3, (IdentifierType.PMID, "123")),
        _publication(4, (IdentifierType.PMID, "123")),
    ]

    groups = DuplicateGroupBuilder().build(publications, created_at=_TIME)

    assert {group.created_at for group in groups} == {_TIME}
    assert {group.updated_at for group in groups} == {_TIME}


def test_default_created_at_is_timezone_aware() -> None:
    first = _publication(1, (IdentifierType.DOI, "10.1000/a"))
    second = _publication(2, (IdentifierType.DOI, "10.1000/a"))

    group = DuplicateGroupBuilder().build([first, second])[0]

    assert group.created_at.tzinfo is not None
    assert group.created_at.utcoffset() is not None


def test_naive_created_at_is_rejected() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        DuplicateGroupBuilder().build(
            [],
            created_at=datetime(2026, 7, 29, 8, 0),
        )


def test_repeated_publication_id_is_not_a_duplicate_group() -> None:
    publication = _publication(1, (IdentifierType.DOI, "10.1000/a"))

    assert DuplicateGroupBuilder().build([publication, publication]) == []


def test_many_repetitions_of_one_record_id_do_not_build_group() -> None:
    publication = _publication(1, (IdentifierType.DOI, "10.1000/a"))

    assert DuplicateGroupBuilder().build([publication] * 5) == []


def test_repeated_record_id_aggregates_identifiers_without_metadata_resolution() -> None:
    first_representation = _publication(1, (IdentifierType.DOI, "10.1000/a"))
    second_representation = first_representation.model_copy(
        update={
            "title": "Different metadata is not selected",
            "identifiers": [
                Identifier(type=IdentifierType.PMID, value="123"),
            ],
        },
        deep=True,
    )
    doi_match = _publication(2, (IdentifierType.DOI, "10.1000/a"))
    pmid_match = _publication(3, (IdentifierType.PMID, "123"))
    builder = DuplicateGroupBuilder()

    forward = builder.build(
        [first_representation, second_representation, doi_match, pmid_match],
        created_at=_TIME,
    )
    reverse = builder.build(
        [pmid_match, doi_match, second_representation, first_representation],
        created_at=_TIME,
    )

    assert forward == reverse
    assert forward[0].publication_ids == (
        first_representation.record_id,
        doi_match.record_id,
        pmid_match.record_id,
    )


def test_builder_does_not_mutate_or_merge_publications() -> None:
    first = _publication(1, (IdentifierType.DOI, "10.1000/a"))
    second = _publication(2, (IdentifierType.DOI, "10.1000/a"))
    before = deepcopy([first, second])

    groups = DuplicateGroupBuilder().build([first, second])

    assert [first, second] == before
    assert groups[0].publication_ids == (first.record_id, second.record_id)


def test_one_publication_cannot_appear_in_overlapping_groups() -> None:
    first = _publication(1, (IdentifierType.DOI, "10.1000/a"))
    bridge = _publication(
        2,
        (IdentifierType.DOI, "10.1000/a"),
        (IdentifierType.OPENALEX, "W2"),
    )
    third = _publication(3, (IdentifierType.OPENALEX, "W2"))

    groups = DuplicateGroupBuilder().build([first, bridge, third])

    memberships = [
        publication_id
        for group in groups
        for publication_id in group.publication_ids
    ]
    assert len(memberships) == len(set(memberships))
    assert len(groups) == 1


def test_two_independent_components_and_unmatched_record() -> None:
    doi_first = _publication(1, (IdentifierType.DOI, "10.1000/a"))
    doi_second = _publication(2, (IdentifierType.DOI, "10.1000/a"))
    pmid_first = _publication(3, (IdentifierType.PMID, "123"))
    pmid_second = _publication(4, (IdentifierType.PMID, "123"))
    unmatched = _publication(5, (IdentifierType.OPENALEX, "W5"))

    groups = DuplicateGroupBuilder().build(
        [unmatched, pmid_second, doi_second, pmid_first, doi_first],
        created_at=_TIME,
    )

    assert [group.publication_ids for group in groups] == [
        (doi_first.record_id, doi_second.record_id),
        (pmid_first.record_id, pmid_second.record_id),
    ]


def test_different_member_set_has_different_group_id() -> None:
    first = _publication(1, (IdentifierType.DOI, "10.1000/a"))
    second = _publication(2, (IdentifierType.DOI, "10.1000/a"))
    third = _publication(3, (IdentifierType.DOI, "10.1000/a"))
    builder = DuplicateGroupBuilder()

    pair = builder.build([first, second], created_at=_TIME)
    triple = builder.build([third, second, first], created_at=_TIME)

    assert pair[0].group_id != triple[0].group_id


def test_metadata_changes_do_not_change_group_id() -> None:
    first = _publication(1, (IdentifierType.DOI, "10.1000/a"))
    second = _publication(2, (IdentifierType.DOI, "10.1000/a"))
    changed = second.model_copy(update={"title": "Changed title"}, deep=True)
    builder = DuplicateGroupBuilder()

    original = builder.build([first, second], created_at=_TIME)
    modified = builder.build([changed, first], created_at=_TIME)

    assert original[0].group_id == modified[0].group_id


def test_actual_openalex_provider_identifier_format_builds_group() -> None:
    first = _publication(1)
    second = _publication(2)
    openalex_identifier = Identifier(
        type=IdentifierType.OTHER,
        value="https://openalex.org/W123",
        source="openalex",
    )
    first = first.model_copy(update={"identifiers": [openalex_identifier]}, deep=True)
    second = second.model_copy(update={"identifiers": [openalex_identifier]}, deep=True)

    groups = DuplicateGroupBuilder().build([first, second], created_at=_TIME)

    assert groups[0].publication_ids == (first.record_id, second.record_id)


def test_compact_and_url_openalex_ids_are_not_implicitly_normalized() -> None:
    compact = _publication(1, (IdentifierType.OPENALEX, "W123"))
    provider_url = _publication(2)
    provider_url = provider_url.model_copy(
        update={
            "identifiers": [
                Identifier(
                    type=IdentifierType.OTHER,
                    value="https://openalex.org/W123",
                    source="openalex",
                )
            ]
        },
        deep=True,
    )

    assert (
        DuplicateGroupBuilder().build(
            [compact, provider_url],
            created_at=_TIME,
        )
        == []
    )


def test_pmid_uses_exact_identifier_value() -> None:
    uppercase = _publication(1, (IdentifierType.PMID, "PMID-1"))
    lowercase = _publication(2, (IdentifierType.PMID, "pmid-1"))

    assert DuplicateGroupBuilder().build([uppercase, lowercase]) == []
