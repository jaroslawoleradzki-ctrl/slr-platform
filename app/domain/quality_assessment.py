from datetime import datetime, timezone
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictInt,
    StrictStr,
    field_validator,
    model_validator,
)


class QualityAssessmentResponseValue(StrEnum):
    """Methodology-neutral assessment response value per quality criterion."""

    YES = "YES"
    NO = "NO"
    CANNOT_DETERMINE = "CANNOT_DETERMINE"


class QualityAssessmentTool(BaseModel):
    """Domain model for a methodological quality assessment tool family (e.g. CASP-inspired, JBI, MMAT)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    tool_id: StrictStr = Field(min_length=1)
    name: StrictStr = Field(min_length=1)
    description: StrictStr | None = None
    is_active: StrictBool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("tool_id", "name")
    @classmethod
    def validate_non_blank_text(cls, value: str) -> str:
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

    @field_validator("created_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("created_at must be timezone-aware")
        return value


class QualityAssessmentTemplateCriterion(BaseModel):
    """Domain model representing a single question / criterion within a quality assessment template version."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    criterion_id: UUID = Field(default_factory=uuid4)
    template_id: UUID
    display_order: StrictInt = Field(default=0, ge=0)
    question: StrictStr = Field(min_length=1)
    guidance: StrictStr | None = None
    is_required: StrictBool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("question")
    @classmethod
    def validate_non_blank_question(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("question must not be blank")
        return stripped

    @field_validator("guidance")
    @classmethod
    def normalize_guidance(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped if stripped else None

    @field_validator("created_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("created_at must be timezone-aware")
        return value


class QualityAssessmentTemplate(BaseModel):
    """Domain model for an immutable, versioned quality assessment template form.

    Template content (name, version, criteria, wording) is strictly immutable.
    is_active is mutable lifecycle metadata controlling new project selection.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    template_id: UUID = Field(default_factory=uuid4)
    tool_id: StrictStr = Field(min_length=1)
    template_key: StrictStr = Field(min_length=1)
    name: StrictStr = Field(min_length=1)
    version: StrictInt = Field(ge=1)
    description: StrictStr | None = None
    is_active: StrictBool = True
    criteria: list[QualityAssessmentTemplateCriterion] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("tool_id", "template_key", "name")
    @classmethod
    def validate_non_blank_text(cls, value: str) -> str:
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

    @field_validator("created_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("created_at must be timezone-aware")
        return value

    @model_validator(mode="after")
    def validate_criteria_ownership_and_order(self) -> "QualityAssessmentTemplate":
        seen_orders: set[int] = set()
        seen_ids: set[UUID] = set()
        for criterion in self.criteria:
            if criterion.template_id != self.template_id:
                raise ValueError(
                    f"Criterion '{criterion.criterion_id}' template_id '{criterion.template_id}' "
                    f"does not match template_id '{self.template_id}'"
                )
            if criterion.criterion_id in seen_ids:
                raise ValueError(f"Duplicate criterion_id '{criterion.criterion_id}' in template criteria")
            if criterion.display_order in seen_orders:
                raise ValueError(f"Duplicate display_order '{criterion.display_order}' in template criteria")
            seen_ids.add(criterion.criterion_id)
            seen_orders.add(criterion.display_order)
        return self


class QualityAssessmentResponse(BaseModel):
    """Criterion-level response with authoritative criterion metadata snapshots."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    response_id: UUID = Field(default_factory=uuid4)
    assessment_id: UUID
    criterion_id: UUID
    question_snapshot: StrictStr = Field(min_length=1)
    guidance_snapshot: StrictStr | None = None
    is_required_snapshot: StrictBool = True
    response_value: QualityAssessmentResponseValue
    justification: StrictStr = Field(min_length=1)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("question_snapshot", "justification")
    @classmethod
    def validate_non_blank_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("text fields must not be blank")
        return stripped

    @field_validator("guidance_snapshot")
    @classmethod
    def normalize_guidance(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped if stripped else None

    @field_validator("created_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("created_at must be timezone-aware")
        return value


class QualityAssessment(BaseModel):
    """Immutable quality assessment record for a publication by a reviewer (Append-only)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    assessment_id: UUID = Field(default_factory=uuid4)
    project_id: StrictStr = Field(min_length=1)
    publication_id: UUID
    reviewer_id: StrictStr = Field(min_length=1)
    template_id: UUID
    responses: list[QualityAssessmentResponse] = Field(default_factory=list)
    assessed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("project_id", "reviewer_id")
    @classmethod
    def validate_non_blank_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("text fields must not be blank")
        return stripped

    @field_validator("assessed_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("assessed_at must be timezone-aware")
        return value

    @model_validator(mode="after")
    def validate_response_ownership_and_uniqueness(self) -> "QualityAssessment":
        seen_criterion_ids: set[UUID] = set()
        for resp in self.responses:
            if resp.assessment_id != self.assessment_id:
                raise ValueError(
                    f"Response '{resp.response_id}' assessment_id '{resp.assessment_id}' "
                    f"does not match assessment_id '{self.assessment_id}'"
                )
            if resp.criterion_id in seen_criterion_ids:
                raise ValueError(f"Duplicate response for criterion_id '{resp.criterion_id}'")
            seen_criterion_ids.add(resp.criterion_id)
        return self


class ProjectQualityAssessmentConfiguration(BaseModel):
    """Domain model for a project's active Quality Assessment configuration."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    project_id: StrictStr = Field(min_length=1)
    tool_id: StrictStr = Field(min_length=1)
    template_id: UUID
    configured_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("project_id", "tool_id")
    @classmethod
    def validate_non_blank_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("text fields must not be blank")
        return stripped

    @field_validator("configured_at", "updated_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamps must be timezone-aware")
        return value
