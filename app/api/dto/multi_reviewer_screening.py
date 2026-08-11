from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.api.dto.conflict_resolution import ConflictResolutionResponse
from app.api.dto.screening import ScreeningDecisionResponse
from app.domain.screening import ScreeningOutcome, ScreeningStage
from app.repositories.screening_reviewer_assignment_repository import ScreeningReviewerAssignment
from app.services.multi_reviewer_screening_service import ScreeningConflictRecord, ScreeningConflictStatus


class ReviewerRosterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reviewer_ids: list[str] = Field(default_factory=list)


class ReviewerAssignmentResponse(BaseModel):
    project_id: str
    stage: ScreeningStage
    reviewer_id: str
    is_active: bool

    @classmethod
    def from_domain(cls, value: ScreeningReviewerAssignment):
        return cls(
            project_id=value.project_id, stage=value.stage, reviewer_id=value.reviewer_id, is_active=value.is_active
        )


class ReviewerLatestDecisionResponse(BaseModel):
    reviewer_id: str
    outcome: ScreeningOutcome
    decision_id: UUID
    decided_at: str
    decision: ScreeningDecisionResponse | None = None


class ScreeningConflictResponse(BaseModel):
    project_id: str
    publication_id: UUID
    publication_title: str | None
    stage: ScreeningStage
    status: ScreeningConflictStatus
    expected_reviewers: list[str]
    pending_reviewers: list[str]
    latest_decisions: list[ReviewerLatestDecisionResponse]
    current_decision_set_key: str
    resolution: ConflictResolutionResponse | None = None

    @classmethod
    def from_domain(cls, value: ScreeningConflictRecord):
        return cls(
            project_id=value.project_id,
            publication_id=value.publication_id,
            publication_title=value.publication_title,
            stage=value.stage,
            status=value.status,
            expected_reviewers=list(value.expected_reviewers),
            pending_reviewers=list(value.pending_reviewers),
            latest_decisions=[
                ReviewerLatestDecisionResponse(
                    reviewer_id=item.reviewer_id,
                    outcome=item.outcome,
                    decision_id=item.decision_id,
                    decided_at=item.decided_at,
                    decision=ScreeningDecisionResponse.from_domain(next(
                        decision for decision in value.source_decisions if decision.decision_id == item.decision_id
                    )) if value.source_decisions else None,
                )
                for item in value.latest_decisions
            ],
            current_decision_set_key=value.current_decision_set_key,
            resolution=ConflictResolutionResponse.from_domain(
                value.resolution, is_current=value.status is ScreeningConflictStatus.RESOLVED
            )
            if value.resolution
            else None,
        )


class ScreeningConflictPageResponse(BaseModel):
    total: int
    offset: int
    limit: int
    items: list[ScreeningConflictResponse]


class ScreeningConflictMetricsResponse(BaseModel):
    incomplete: int
    agreement: int
    conflict: int
    resolved: int
    stale_resolution: int
    agreement_rate: float | None
    resolution_rate: float | None
