from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.domain.conflict_resolution import ConflictResolution, ResolvedOutcome
from app.domain.screening import ScreeningStage


class ConflictResolutionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    publication_id: UUID
    stage: ScreeningStage
    resolved_outcome: ResolvedOutcome
    resolver_id: str = Field(min_length=1)
    rationale: str = Field(min_length=1)
    expected_decision_set_key: str = Field(min_length=1)


class ResolutionReviewerOutcomeResponse(BaseModel):
    decision_id: UUID
    reviewer_id: str
    outcome: ResolvedOutcome


class ConflictResolutionResponse(BaseModel):
    resolution_id: UUID
    project_id: str
    publication_id: UUID
    stage: ScreeningStage
    decision_set_key: str
    resolved_outcome: ResolvedOutcome
    resolver_id: str
    rationale: str
    resolved_at: str
    decision_ids: list[UUID]
    reviewer_outcomes: list[ResolutionReviewerOutcomeResponse] = Field(default_factory=list)
    is_current: bool | None = None

    @classmethod
    def from_domain(
        cls,
        v: ConflictResolution,
        *,
        is_current: bool | None = None,
        reviewer_outcomes: tuple[tuple[UUID, str, ResolvedOutcome], ...] = (),
    ):
        return cls(
            resolution_id=v.resolution_id,
            project_id=v.project_id,
            publication_id=v.publication_id,
            stage=v.stage,
            decision_set_key=v.decision_set_key,
            resolved_outcome=v.resolved_outcome,
            resolver_id=v.resolver_id,
            rationale=v.rationale,
            resolved_at=v.resolved_at.isoformat(),
            decision_ids=list(v.decision_ids),
            reviewer_outcomes=[
                ResolutionReviewerOutcomeResponse(
                    decision_id=decision_id,
                    reviewer_id=reviewer_id,
                    outcome=outcome,
                )
                for decision_id, reviewer_id, outcome in reviewer_outcomes
            ],
            is_current=is_current,
        )


class ConflictResolutionHistoryResponse(BaseModel):
    publication_id: UUID
    stage: ScreeningStage
    current_decision_set_key: str
    total: int
    offset: int
    limit: int
    resolutions: list[ConflictResolutionResponse]
