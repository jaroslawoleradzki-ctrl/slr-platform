from datetime import datetime, timezone
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ScreeningStage(StrEnum):
    """Stage of the systematic review screening process."""

    TITLE_ABSTRACT = "title_abstract"
    FULL_TEXT = "full_text"


class ScreeningCriterionStage(StrEnum):
    """Stage in the systematic review process where a screening criterion applies."""

    TITLE_ABSTRACT = "title_abstract"
    FULL_TEXT = "full_text"
    BOTH = "both"


class ScreeningCriterionType(StrEnum):
    """Type of screening criterion (inclusion vs exclusion)."""

    INCLUSION = "inclusion"
    EXCLUSION = "exclusion"


class ScreeningOutcome(StrEnum):
    """Possible inclusion decision at a screening stage."""

    INCLUDE = "include"
    EXCLUDE = "exclude"
    UNCERTAIN = "uncertain"


class CriterionAssessmentValue(StrEnum):
    """Methodology-neutral assessment value for an individual screening criterion."""

    MET = "met"
    NOT_MET = "not_met"
    UNCERTAIN = "uncertain"
    NOT_ASSESSED = "not_assessed"


class ScreeningCriterion(BaseModel):
    """Domain model representing a configurable screening criterion for a project."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    criterion_id: UUID = Field(default_factory=uuid4)
    project_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    description: str | None = None
    criterion_type: ScreeningCriterionType
    screening_stage: ScreeningCriterionStage
    display_order: int = Field(default=0, ge=0)
    is_active: bool = True
    is_required: bool = True

    @field_validator("project_id", "name")
    @classmethod
    def validate_non_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("text fields must not be blank")
        return stripped

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped if stripped else None


class AIRecommendation(BaseModel):
    """Standalone AI-generated screening recommendation domain model (Phase 1)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    outcome: ScreeningOutcome
    confidence: float = Field(ge=0.0, le=1.0)
    model_name: str = Field(min_length=1)
    model_version: str | None = None
    rationale: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("model_name", "model_version", "rationale")
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("text fields must not be blank")
        return stripped

    @field_validator("created_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("created_at must be timezone-aware")
        return value


class CriterionAssessment(BaseModel):
    """Assessment of an individual screening criterion with an immutable historical snapshot."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    criterion_id: UUID
    criterion_name: str = Field(min_length=1)
    criterion_type: ScreeningCriterionType
    criterion_stage: ScreeningCriterionStage
    criterion_is_required: bool
    assessment_value: CriterionAssessmentValue
    notes: str | None = None

    @field_validator("criterion_name")
    @classmethod
    def validate_non_blank_name(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("criterion_name must not be blank")
        return stripped

    @field_validator("notes")
    @classmethod
    def normalize_notes(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped if stripped else None


class ScreeningDecision(BaseModel):
    """Immutable screening decision record for a single publication, reviewer, and stage.

    100% AI-free. Contains decision outcome, rationale, and criterion assessments snapshot.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    decision_id: UUID = Field(default_factory=uuid4)
    project_id: str = Field(min_length=1)
    publication_id: UUID
    stage: ScreeningStage
    outcome: ScreeningOutcome
    reviewer_id: str = Field(min_length=1)
    rationale: str | None = None
    criterion_assessments: list[CriterionAssessment] = Field(default_factory=list)
    decided_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("project_id", "reviewer_id")
    @classmethod
    def validate_non_blank_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("text fields must not be blank")
        return stripped

    @field_validator("rationale")
    @classmethod
    def normalize_rationale(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped if stripped else None

    @field_validator("decided_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("decided_at must be timezone-aware")
        return value

    @model_validator(mode="after")
    def validate_unique_assessments(self) -> "ScreeningDecision":
        seen_criterion_ids: set[UUID] = set()
        for assessment in self.criterion_assessments:
            if assessment.criterion_id in seen_criterion_ids:
                raise ValueError(
                    f"Duplicate criterion assessment for criterion_id '{assessment.criterion_id}'"
                )
            seen_criterion_ids.add(assessment.criterion_id)
        return self
