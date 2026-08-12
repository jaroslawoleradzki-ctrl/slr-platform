from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.api.dto.screening import (
    CriterionAssessmentResponse,
    ScreeningDecisionResponse,
)
from app.domain.conflict_resolution import ResolvedOutcome
from app.domain.screening import ScreeningOutcome, ScreeningStage
from app.services.screening_reporting_service import (
    AuditEvent,
    AuditResolutionEvent,
    ReasonAggregation,
    ScreeningTransitions,
    StageProgress,
)


class StageProgressResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_eligible: int
    screened: int
    remaining: int
    included: int
    excluded: int
    uncertain: int

    @classmethod
    def from_domain(cls, value: StageProgress) -> StageProgressResponse:
        return cls(
            total_eligible=value.total_eligible,
            screened=value.screened,
            remaining=value.remaining,
            included=value.included,
            excluded=value.excluded,
            uncertain=value.uncertain,
        )


class ExclusionReasonAggregationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    criterion_id: UUID
    criterion_snapshot_key: str
    snapshot_schema_version: int
    snapshot_complete: bool
    count: int
    criterion_assessment: CriterionAssessmentResponse

    @classmethod
    def from_domain(cls, value: ReasonAggregation) -> ExclusionReasonAggregationResponse:
        return cls(
            criterion_id=value.criterion_id,
            criterion_snapshot_key=value.criterion_snapshot_key,
            snapshot_schema_version=value.snapshot_schema_version,
            snapshot_complete=value.snapshot_complete,
            count=value.count,
            criterion_assessment=CriterionAssessmentResponse.from_domain(value.assessment),
        )


class ScreeningTransitionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    canonical_input: int
    title_abstract_screened: int
    title_abstract_included: int
    full_text_eligible: int
    full_text_screened: int
    full_text_included: int

    @classmethod
    def from_domain(cls, value: ScreeningTransitions) -> ScreeningTransitionResponse:
        return cls(
            canonical_input=value.canonical_input,
            title_abstract_screened=value.title_abstract_screened,
            title_abstract_included=value.title_abstract_included,
            full_text_eligible=value.full_text_eligible,
            full_text_screened=value.full_text_screened,
            full_text_included=value.full_text_included,
        )


class MultiReviewerStageMetricsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    incomplete: int
    agreement: int
    conflict: int
    resolved: int
    stale_resolution: int
    agreement_rate: float | None
    resolution_rate: float | None


class ProjectOutcomeSummaryResponse(BaseModel):
    stage: str
    total: int
    include: int
    exclude: int
    uncertain: int
    pending: int


class ScreeningReportResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: str
    reviewer_id: str
    ready: bool
    readiness_status: str
    working_collection_count: int
    canonical_records_count: int
    title_abstract: StageProgressResponse | None
    full_text: StageProgressResponse | None
    transitions: ScreeningTransitionResponse | None
    full_text_exclusion_reasons: list[ExclusionReasonAggregationResponse]
    title_abstract_multi_reviewer: MultiReviewerStageMetricsResponse | None = None
    full_text_multi_reviewer: MultiReviewerStageMetricsResponse | None = None
    title_abstract_project_outcomes: ProjectOutcomeSummaryResponse | None = None
    full_text_project_outcomes: ProjectOutcomeSummaryResponse | None = None


class ScreeningAuditEventResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: ScreeningDecisionResponse
    publication_title: str | None
    revision_index: int
    previous_outcome: ScreeningOutcome | None
    is_latest_for_reviewer: bool
    event_type: Literal["DECISION"] = "DECISION"

    @classmethod
    def from_domain(cls, value: AuditEvent) -> ScreeningAuditEventResponse:
        return cls(
            decision=ScreeningDecisionResponse.from_domain(value.decision),
            publication_title=value.publication_title,
            revision_index=value.revision_index,
            previous_outcome=value.previous_outcome,
            is_latest_for_reviewer=value.is_latest_for_reviewer,
        )


class ScreeningAuditResolutionEventResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event_type: Literal["RESOLUTION"] = "RESOLUTION"
    resolution_id: UUID
    publication_id: UUID
    publication_title: str | None
    stage: ScreeningStage
    resolver_id: str
    resolved_outcome: ResolvedOutcome
    rationale: str
    resolved_at: str
    decision_set_key: str
    is_current: bool
    status: Literal["CURRENT", "STALE"]
    reviewer_outcomes: list["AuditResolutionReviewerOutcomeResponse"]

    @classmethod
    def from_domain(cls, value: AuditResolutionEvent) -> "ScreeningAuditResolutionEventResponse":
        r = value.resolution
        return cls(
            resolution_id=r.resolution_id,
            publication_id=r.publication_id,
            publication_title=value.publication_title,
            stage=r.stage,
            resolver_id=r.resolver_id,
            resolved_outcome=r.resolved_outcome,
            rationale=r.rationale,
            resolved_at=r.resolved_at.isoformat(),
            decision_set_key=r.decision_set_key,
            is_current=value.is_current,
            status="CURRENT" if value.is_current else "STALE",
            reviewer_outcomes=[
                AuditResolutionReviewerOutcomeResponse(
                    decision_id=decision_id,
                    reviewer_id=reviewer_id,
                    outcome=resolved_outcome,
                )
                for decision_id, reviewer_id, resolved_outcome in value.reviewer_outcomes
            ],
        )


class AuditResolutionReviewerOutcomeResponse(BaseModel):
    decision_id: UUID
    reviewer_id: str
    outcome: ResolvedOutcome


class ScreeningAuditPageResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total: int
    offset: int
    limit: int
    items: list[ScreeningAuditEventResponse | ScreeningAuditResolutionEventResponse]
