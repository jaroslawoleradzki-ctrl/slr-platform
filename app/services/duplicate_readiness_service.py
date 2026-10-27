from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Iterable

from app.domain.deduplication import DuplicateGroup, DuplicateGroupMergeRecord
from app.domain.duplicate_review import DuplicateDecision, DuplicateGroupReviewDecision
from app.services.duplicate_group_builder import DuplicateGroupBuilder


class DuplicateReadinessStatus(StrEnum):
    NO_CANDIDATES = "no_candidates"
    PENDING_REVIEW = "pending_review"
    APPROVED_UNMERGED = "approved_unmerged"
    READY = "ready"


@dataclass(frozen=True, slots=True)
class DuplicateReadiness:
    status: DuplicateReadinessStatus
    screening_ready: bool
    total_groups: int
    pending_review_groups: int
    approved_unmerged_groups: int
    merged_groups: int
    rejected_groups: int
    stale_decisions: int
    blocking_groups: int
    blocking_group_ids: tuple[str, ...]
    reason: str


def evaluate_duplicate_readiness(
    groups: Iterable[DuplicateGroup],
    decisions: dict[str, DuplicateGroupReviewDecision],
    merges: dict[str, DuplicateGroupMergeRecord],
) -> DuplicateReadiness:
    """Evaluate duplicate review state for one already-built active group set.

    The caller owns publication selection. Every workflow view must pass the
    same active-canonical group set and the same persisted decisions/merges.
    Historical merges whose members are no longer live are counted as completed
    audit state and never block screening.
    """
    live_groups = list(groups)
    live_group_ids = {str(group.group_id) for group in live_groups}
    pending_groups: list[str] = []
    unmerged_groups: list[str] = []
    rejected_groups = 0
    merged_groups = 0

    for group in live_groups:
        group_id = str(group.group_id)
        decision = decisions.get(group_id)
        merge = merges.get(group_id)
        if merge is not None and merge.status == "merged":
            merged_groups += 1
        elif decision is None:
            pending_groups.append(group_id)
        elif decision.decision is DuplicateDecision.APPROVE:
            unmerged_groups.append(group_id)
        else:
            rejected_groups += 1

    historical_merged = [
        merge
        for group_id, merge in merges.items()
        if group_id not in live_group_ids and merge.status == "merged"
    ]
    merged_groups += len(historical_merged)
    stale_decisions = sum(
        1
        for group_id in decisions
        if group_id not in live_group_ids and group_id not in merges
    )

    total_groups = len(live_groups) + len(historical_merged)
    blocking_group_ids = tuple(sorted(pending_groups + unmerged_groups))
    blocking_groups = len(blocking_group_ids)

    if total_groups == 0:
        status = DuplicateReadinessStatus.NO_CANDIDATES
        reason = "No candidate duplicate groups."
    elif pending_groups:
        status = DuplicateReadinessStatus.PENDING_REVIEW
        reason = (
            f"{len(pending_groups)} duplicate group(s) require a reviewer decision."
        )
    elif unmerged_groups:
        status = DuplicateReadinessStatus.APPROVED_UNMERGED
        reason = (
            f"{len(unmerged_groups)} approved duplicate group(s) require a persisted merge."
        )
    else:
        status = DuplicateReadinessStatus.READY
        reason = "No duplicate groups block screening."

    return DuplicateReadiness(
        status=status,
        screening_ready=status in {
            DuplicateReadinessStatus.NO_CANDIDATES,
            DuplicateReadinessStatus.READY,
        },
        total_groups=total_groups,
        pending_review_groups=len(pending_groups),
        approved_unmerged_groups=len(unmerged_groups),
        merged_groups=merged_groups,
        rejected_groups=rejected_groups,
        stale_decisions=stale_decisions,
        blocking_groups=blocking_groups,
        blocking_group_ids=blocking_group_ids,
        reason=reason,
    )


def build_duplicate_readiness(
    publications: Iterable,
    decisions: dict[str, DuplicateGroupReviewDecision],
    merges: dict[str, DuplicateGroupMergeRecord],
    *,
    builder: DuplicateGroupBuilder | None = None,
) -> DuplicateReadiness:
    """Build active-corpus groups and evaluate readiness in one call."""
    group_builder = builder or DuplicateGroupBuilder()
    groups = group_builder.build(list(publications), include_title_candidates=True)
    return evaluate_duplicate_readiness(groups, decisions, merges)
