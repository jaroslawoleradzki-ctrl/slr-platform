from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from app.domain.screening import ScreeningDecision, ScreeningStage


class ResolvedOutcome(StrEnum):
    INCLUDE = "include"
    EXCLUDE = "exclude"
    UNCERTAIN = "uncertain"


class PublicationScreeningStatus(StrEnum):
    INCOMPLETE = "incomplete"
    AGREEMENT = "agreement"
    CONFLICT = "conflict"
    RESOLVED = "resolved"
    STALE_RESOLUTION = "stale_resolution"


@dataclass(frozen=True, slots=True)
class ConflictResolution:
    resolution_id: UUID
    project_id: str
    publication_id: UUID
    stage: ScreeningStage
    decision_set_key: str
    resolved_outcome: ResolvedOutcome
    resolver_id: str
    rationale: str
    resolved_at: datetime
    decision_ids: tuple[UUID, ...]

    def __post_init__(self) -> None:
        resolver_id = self.resolver_id.strip()
        rationale = self.rationale.strip()
        if not self.project_id.strip():
            raise ValueError("project_id must not be blank")
        if not self.decision_set_key.strip():
            raise ValueError("decision_set_key must not be blank")
        if not resolver_id:
            raise ValueError("resolver_id must not be blank")
        if not rationale:
            raise ValueError("rationale must not be blank")
        if self.resolved_at.tzinfo is None or self.resolved_at.utcoffset() is None:
            raise ValueError("resolved_at must be timezone-aware")
        if not self.decision_ids or len(set(self.decision_ids)) != len(self.decision_ids):
            raise ValueError("decision_ids must be non-empty and unique")
        object.__setattr__(self, "resolver_id", resolver_id)
        object.__setattr__(self, "rationale", rationale)


@dataclass(frozen=True, slots=True)
class ProjectScreeningOutcome:
    status: PublicationScreeningStatus
    outcome: ResolvedOutcome | None

    @property
    def is_final(self) -> bool:
        return self.status in (PublicationScreeningStatus.AGREEMENT, PublicationScreeningStatus.RESOLVED)


def compute_decision_set_key(project_id: str, publication_id: UUID, stage: ScreeningStage,
                             active_reviewer_ids: tuple[str, ...],
                             latest_decisions: dict[str, ScreeningDecision]) -> str:
    reviewers = tuple(sorted(active_reviewer_ids))
    parts = [project_id, str(publication_id), stage.value, ",".join(reviewers)]
    for reviewer_id in reviewers:
        value = latest_decisions.get(reviewer_id)
        parts.append(f"{reviewer_id}:{value.decision_id}:{value.outcome.value}" if value else f"{reviewer_id}:PENDING:PENDING")
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
