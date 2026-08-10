from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.domain.screening import (
    CriterionAssessment,
    CriterionAssessmentValue,
    ScreeningCriterion,
    ScreeningCriterionStage,
    ScreeningCriterionType,
    ScreeningDecision,
    ScreeningOutcome,
    ScreeningStage,
)


class ScreeningCriterionCreateRequest(BaseModel):
    """Payload for creating a new project screening criterion."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, description="Non-blank name of the criterion.")
    description: str | None = Field(
        default=None, description="Optional detailed description or instruction."
    )
    criterion_type: ScreeningCriterionType = Field(
        description="Type of criterion: 'inclusion' or 'exclusion'."
    )
    screening_stage: ScreeningCriterionStage = Field(
        description="Stage scope: 'title_abstract', 'full_text', or 'both'."
    )
    display_order: int = Field(
        default=0, ge=0, description="Non-negative sorting order index."
    )
    is_active: bool = Field(
        default=True, description="Whether the criterion is currently active."
    )
    is_required: bool = Field(
        default=True, description="Whether evaluation of this criterion is required."
    )


class ScreeningCriterionUpdateRequest(BaseModel):
    """Payload for updating an existing project screening criterion."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, description="Non-blank name of the criterion.")
    description: str | None = Field(
        default=None, description="Optional detailed description or instruction."
    )
    criterion_type: ScreeningCriterionType = Field(
        description="Type of criterion: 'inclusion' or 'exclusion'."
    )
    screening_stage: ScreeningCriterionStage = Field(
        description="Stage scope: 'title_abstract', 'full_text', or 'both'."
    )
    display_order: int = Field(
        default=0, ge=0, description="Non-negative sorting order index."
    )
    is_active: bool = Field(
        default=True, description="Whether the criterion is currently active."
    )
    is_required: bool = Field(
        default=True, description="Whether evaluation of this criterion is required."
    )


class ScreeningCriterionResponse(BaseModel):
    """API response model representing a screening criterion."""

    model_config = ConfigDict(extra="forbid")

    criterion_id: UUID = Field(description="Unique identifier of the criterion.")
    project_id: str = Field(description="Project identifier.")
    name: str = Field(description="Name of the criterion.")
    description: str | None = Field(description="Description of the criterion.")
    criterion_type: ScreeningCriterionType = Field(
        description="Type of criterion: 'inclusion' or 'exclusion'."
    )
    screening_stage: ScreeningCriterionStage = Field(
        description="Stage scope: 'title_abstract', 'full_text', or 'both'."
    )
    display_order: int = Field(description="Sorting order index.")
    is_active: bool = Field(description="Active status indicator.")
    is_required: bool = Field(description="Required status indicator.")

    @classmethod
    def from_domain(cls, criterion: ScreeningCriterion) -> ScreeningCriterionResponse:
        return cls(
            criterion_id=criterion.criterion_id,
            project_id=criterion.project_id,
            name=criterion.name,
            description=criterion.description,
            criterion_type=criterion.criterion_type,
            screening_stage=criterion.screening_stage,
            display_order=criterion.display_order,
            is_active=criterion.is_active,
            is_required=criterion.is_required,
        )


class ScreeningCriterionListResponse(BaseModel):
    """Response model for a list of project screening criteria."""

    model_config = ConfigDict(extra="forbid")

    items: list[ScreeningCriterionResponse] = Field(
        description="List of screening criteria for the project."
    )
    total: int = Field(description="Total number of items returned.")


# --- Screening Decision DTOs ---


class CriterionAssessmentRequest(BaseModel):
    """Client payload for evaluating an individual screening criterion.

    Authoritative criterion metadata is populated server-side from ScreeningCriterionRepository.
    """

    model_config = ConfigDict(extra="forbid")

    criterion_id: UUID = Field(description="Identifier of the criterion being evaluated.")
    assessment_value: CriterionAssessmentValue = Field(
        description="Assessment value: 'met', 'not_met', 'uncertain', or 'not_assessed'."
    )
    notes: str | None = Field(
        default=None, description="Optional reviewer notes for this assessment."
    )


class ScreeningDecisionCreateRequest(BaseModel):
    """Payload for recording a new screening decision for a publication."""

    model_config = ConfigDict(extra="forbid")

    publication_id: UUID = Field(description="Identifier of the publication being screened.")
    stage: ScreeningStage = Field(
        description="Screening stage: 'title_abstract' or 'full_text'."
    )
    outcome: ScreeningOutcome = Field(
        description="Decision outcome: 'include', 'exclude', or 'uncertain'."
    )
    reviewer_id: str = Field(
        min_length=1, description="Non-blank reviewer identifier."
    )
    rationale: str | None = Field(
        default=None, description="Optional overall decision rationale."
    )
    criterion_assessments: list[CriterionAssessmentRequest] = Field(
        default_factory=list, description="Criterion-level assessments."
    )


class CriterionAssessmentResponse(BaseModel):
    """API response model representing a criterion assessment snapshot."""

    model_config = ConfigDict(extra="forbid")

    criterion_id: UUID = Field(description="Criterion identifier.")
    criterion_name: str = Field(description="Criterion name at decision time.")
    criterion_type: ScreeningCriterionType = Field(description="Criterion type.")
    criterion_stage: ScreeningCriterionStage = Field(description="Criterion stage scope.")
    criterion_is_required: bool = Field(description="Whether criterion was required at decision time.")
    assessment_value: CriterionAssessmentValue = Field(description="Assessment value.")
    notes: str | None = Field(description="Reviewer notes.")

    @classmethod
    def from_domain(cls, assessment: CriterionAssessment) -> CriterionAssessmentResponse:
        return cls(
            criterion_id=assessment.criterion_id,
            criterion_name=assessment.criterion_name,
            criterion_type=assessment.criterion_type,
            criterion_stage=assessment.criterion_stage,
            criterion_is_required=assessment.criterion_is_required,
            assessment_value=assessment.assessment_value,
            notes=assessment.notes,
        )


class ScreeningDecisionResponse(BaseModel):
    """API response model representing a screening decision record."""

    model_config = ConfigDict(extra="forbid")

    decision_id: UUID = Field(description="Unique identifier of the decision record.")
    project_id: str = Field(description="Project identifier.")
    publication_id: UUID = Field(description="Publication identifier.")
    stage: ScreeningStage = Field(description="Screening stage.")
    outcome: ScreeningOutcome = Field(description="Screening outcome.")
    reviewer_id: str = Field(description="Reviewer identifier.")
    rationale: str | None = Field(description="Decision rationale.")
    criterion_assessments: list[CriterionAssessmentResponse] = Field(
        description="Criterion assessments snapshot."
    )
    decided_at: datetime = Field(description="Timezone-aware decision timestamp.")

    @classmethod
    def from_domain(cls, decision: ScreeningDecision) -> ScreeningDecisionResponse:
        return cls(
            decision_id=decision.decision_id,
            project_id=decision.project_id,
            publication_id=decision.publication_id,
            stage=decision.stage,
            outcome=decision.outcome,
            reviewer_id=decision.reviewer_id,
            rationale=decision.rationale,
            criterion_assessments=[
                CriterionAssessmentResponse.from_domain(a)
                for a in decision.criterion_assessments
            ],
            decided_at=decision.decided_at,
        )


class ScreeningDecisionListResponse(BaseModel):
    """Response model for a list of screening decision records."""

    model_config = ConfigDict(extra="forbid")

    items: list[ScreeningDecisionResponse] = Field(
        description="List of screening decision records."
    )
    total: int = Field(description="Total number of items returned.")
