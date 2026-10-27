from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4


class ImportReviewDecisionType(StrEnum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class ImportReviewDecision:
    """Append-only reviewer decision for one import.

    The decision snapshots the warnings and the exact active records affected
    by a rejection so audit remains possible after canonical rows are removed
    from the active corpus.
    """

    project_id: str
    import_id: UUID
    decision: str
    reviewer_id: str
    decided_at: datetime
    import_status_at_decision: str
    warning_snapshot: tuple[str, ...] = ()
    affected_source_record_ids: tuple[str, ...] = ()
    affected_publication_ids: tuple[str, ...] = ()
    removed_publication_snapshots: tuple[dict, ...] = ()
    deleted_publication_count: int = 0
    retained_source_record_count: int = 0
    prisma_treatment: str = "not_applicable"
    rationale: str | None = None
    decision_id: UUID = field(default_factory=uuid4)


def effective_import_status(original_status: str, decision: str | None) -> str:
    """Return the active workflow status for an import-history row."""
    if decision == ImportReviewDecisionType.REJECTED.value:
        return "rejected"
    if decision == ImportReviewDecisionType.ACCEPTED.value:
        return "success"
    return original_status
