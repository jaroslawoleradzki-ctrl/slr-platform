from datetime import datetime, timedelta, timezone
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.domain.deduplication import (
    DuplicateDecision,
    DuplicateDecisionType,
    DuplicateGroup,
    DuplicateGroupStatus,
    InvalidDuplicateGroupTransition,
)

_PUBLICATION_A = UUID("00000000-0000-0000-0000-000000000001")
_PUBLICATION_B = UUID("00000000-0000-0000-0000-000000000002")
_CREATED_AT = datetime(2026, 7, 29, 8, 0, tzinfo=timezone.utc)
_DECIDED_AT = _CREATED_AT + timedelta(minutes=5)
_MERGED_AT = _DECIDED_AT + timedelta(minutes=5)


def _group() -> DuplicateGroup:
    return DuplicateGroup(
        publication_ids=(_PUBLICATION_A, _PUBLICATION_B),
        created_at=_CREATED_AT,
        updated_at=_CREATED_AT,
    )


def test_create_group_with_two_distinct_publications() -> None:
    group = _group()

    assert group.publication_ids == (_PUBLICATION_A, _PUBLICATION_B)
    assert group.status is DuplicateGroupStatus.PENDING
    assert group.decision_history == ()


@pytest.mark.parametrize("publication_ids", [(), (_PUBLICATION_A,)])
def test_group_requires_at_least_two_publications(
    publication_ids: tuple[UUID, ...],
) -> None:
    with pytest.raises(ValidationError, match="at least two publications"):
        DuplicateGroup(publication_ids=publication_ids)


def test_group_rejects_repeated_publication_ids() -> None:
    with pytest.raises(ValidationError, match="must not occur more than once"):
        DuplicateGroup(publication_ids=(_PUBLICATION_A, _PUBLICATION_A))


def test_confirm_pending_group() -> None:
    confirmed = _group().confirm(
        decided_at=_DECIDED_AT,
        reviewer_id=" reviewer-1 ",
        rationale=" Same DOI. ",
    )

    assert confirmed.status is DuplicateGroupStatus.CONFIRMED
    assert confirmed.decision_history[0].decision is DuplicateDecisionType.CONFIRM
    assert confirmed.decision_history[0].reviewer_id == "reviewer-1"
    assert confirmed.decision_history[0].rationale == "Same DOI."


def test_reject_pending_group() -> None:
    rejected = _group().reject(decided_at=_DECIDED_AT)

    assert rejected.status is DuplicateGroupStatus.REJECTED
    assert rejected.decision_history[0].decision is DuplicateDecisionType.REJECT


def test_confirmed_group_can_be_marked_merged() -> None:
    confirmed = _group().confirm(decided_at=_DECIDED_AT)
    merged = confirmed.mark_merged(decided_at=_MERGED_AT)

    assert merged.status is DuplicateGroupStatus.MERGED
    assert [entry.decision for entry in merged.decision_history] == [
        DuplicateDecisionType.CONFIRM,
        DuplicateDecisionType.MARK_MERGED,
    ]


def test_pending_group_cannot_be_marked_merged() -> None:
    with pytest.raises(InvalidDuplicateGroupTransition, match="cannot mark_merged"):
        _group().mark_merged(decided_at=_DECIDED_AT)


@pytest.mark.parametrize("operation", ["confirm", "reject", "mark_merged"])
def test_rejected_group_is_terminal(operation: str) -> None:
    rejected = _group().reject(decided_at=_DECIDED_AT)

    with pytest.raises(InvalidDuplicateGroupTransition):
        getattr(rejected, operation)(decided_at=_MERGED_AT)


@pytest.mark.parametrize("operation", ["confirm", "reject", "mark_merged"])
def test_merged_group_is_terminal(operation: str) -> None:
    merged = (
        _group()
        .confirm(decided_at=_DECIDED_AT)
        .mark_merged(decided_at=_MERGED_AT)
    )

    with pytest.raises(InvalidDuplicateGroupTransition):
        getattr(merged, operation)(decided_at=_MERGED_AT + timedelta(minutes=1))


def test_confirmed_group_cannot_be_rejected() -> None:
    confirmed = _group().confirm(decided_at=_DECIDED_AT)

    with pytest.raises(InvalidDuplicateGroupTransition, match="cannot reject"):
        confirmed.reject(decided_at=_MERGED_AT)


def test_rejected_group_cannot_be_confirmed() -> None:
    rejected = _group().reject(decided_at=_DECIDED_AT)

    with pytest.raises(InvalidDuplicateGroupTransition, match="cannot confirm"):
        rejected.confirm(decided_at=_MERGED_AT)


def test_decision_updates_modified_time_and_preserves_created_time() -> None:
    original = _group()
    confirmed = original.confirm(decided_at=_DECIDED_AT)

    assert confirmed.created_at == _CREATED_AT
    assert confirmed.updated_at == _DECIDED_AT
    assert original.updated_at == _CREATED_AT


def test_optional_rationale_can_be_absent() -> None:
    confirmed = _group().confirm(decided_at=_DECIDED_AT)

    assert confirmed.decision_history[0].rationale is None


def test_blank_rationale_is_rejected_consistently() -> None:
    with pytest.raises(ValidationError, match="must not be blank"):
        _group().confirm(decided_at=_DECIDED_AT, rationale="   ")


def test_decision_history_cannot_be_modified_from_outside() -> None:
    confirmed = _group().confirm(decided_at=_DECIDED_AT)

    with pytest.raises(ValidationError):
        confirmed.decision_history = ()
    assert isinstance(confirmed.decision_history, tuple)


def test_group_rejects_naive_timestamps() -> None:
    with pytest.raises(ValidationError, match="timezone-aware"):
        DuplicateGroup(
            publication_ids=(_PUBLICATION_A, _PUBLICATION_B),
            created_at=datetime(2026, 7, 29, 8, 0),
        )


def test_decision_time_cannot_precede_group_creation() -> None:
    with pytest.raises(
        InvalidDuplicateGroupTransition,
        match="must not be earlier than updated_at",
    ):
        _group().confirm(decided_at=_CREATED_AT - timedelta(seconds=1))


def test_mark_merged_time_cannot_precede_confirm_time() -> None:
    confirmed = _group().confirm(decided_at=_DECIDED_AT)

    with pytest.raises(
        InvalidDuplicateGroupTransition,
        match="must not be earlier than updated_at",
    ):
        confirmed.mark_merged(decided_at=_DECIDED_AT - timedelta(seconds=1))


def test_updated_at_cannot_precede_created_at() -> None:
    with pytest.raises(ValidationError, match="earlier than created_at"):
        DuplicateGroup(
            publication_ids=(_PUBLICATION_A, _PUBLICATION_B),
            created_at=_CREATED_AT,
            updated_at=_CREATED_AT - timedelta(seconds=1),
        )


def test_merged_status_requires_decision_history() -> None:
    with pytest.raises(ValidationError, match="status must match decision history"):
        DuplicateGroup(
            publication_ids=(_PUBLICATION_A, _PUBLICATION_B),
            status=DuplicateGroupStatus.MERGED,
            created_at=_CREATED_AT,
            updated_at=_CREATED_AT,
        )


def test_pending_status_rejects_decision_history() -> None:
    decision = DuplicateDecision(
        decision=DuplicateDecisionType.CONFIRM,
        decided_at=_DECIDED_AT,
    )

    with pytest.raises(ValidationError, match="status must match decision history"):
        DuplicateGroup(
            publication_ids=(_PUBLICATION_A, _PUBLICATION_B),
            status=DuplicateGroupStatus.PENDING,
            created_at=_CREATED_AT,
            updated_at=_DECIDED_AT,
            decision_history=(decision,),
        )


def test_status_must_match_last_decision() -> None:
    decision = DuplicateDecision(
        decision=DuplicateDecisionType.REJECT,
        decided_at=_DECIDED_AT,
    )

    with pytest.raises(ValidationError, match="status must match decision history"):
        DuplicateGroup(
            publication_ids=(_PUBLICATION_A, _PUBLICATION_B),
            status=DuplicateGroupStatus.CONFIRMED,
            created_at=_CREATED_AT,
            updated_at=_DECIDED_AT,
            decision_history=(decision,),
        )


def test_direct_construction_rejects_non_chronological_history() -> None:
    confirm = DuplicateDecision(
        decision=DuplicateDecisionType.CONFIRM,
        decided_at=_MERGED_AT,
    )
    mark_merged = DuplicateDecision(
        decision=DuplicateDecisionType.MARK_MERGED,
        decided_at=_DECIDED_AT,
    )

    with pytest.raises(ValidationError, match="must be chronological"):
        DuplicateGroup(
            publication_ids=(_PUBLICATION_A, _PUBLICATION_B),
            status=DuplicateGroupStatus.MERGED,
            created_at=_CREATED_AT,
            updated_at=_DECIDED_AT,
            decision_history=(confirm, mark_merged),
        )


def test_updated_at_must_equal_latest_decision_time() -> None:
    decision = DuplicateDecision(
        decision=DuplicateDecisionType.CONFIRM,
        decided_at=_DECIDED_AT,
    )

    with pytest.raises(ValidationError, match="must equal the latest decision time"):
        DuplicateGroup(
            publication_ids=(_PUBLICATION_A, _PUBLICATION_B),
            status=DuplicateGroupStatus.CONFIRMED,
            created_at=_CREATED_AT,
            updated_at=_MERGED_AT,
            decision_history=(decision,),
        )


def test_later_decision_appends_without_changing_earlier_state() -> None:
    pending = _group()
    confirmed = pending.confirm(
        decided_at=_DECIDED_AT,
        reviewer_id="reviewer-1",
        rationale="Same work.",
    )
    original_decision = confirmed.decision_history[0]

    merged = confirmed.mark_merged(decided_at=_MERGED_AT)

    assert pending.decision_history == ()
    assert confirmed.decision_history == (original_decision,)
    assert merged.decision_history[0] == original_decision
    assert merged.decision_history[0].rationale == "Same work."
    assert len(merged.decision_history) == 2
