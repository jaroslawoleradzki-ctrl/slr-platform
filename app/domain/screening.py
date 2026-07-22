from datetime import datetime, timezone
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ScreeningStage(StrEnum):
    """Stage of the systematic review screening process."""

    TITLE_ABSTRACT = "title_abstract"
    FULL_TEXT = "full_text"


class ScreeningOutcome(StrEnum):
    """Possible inclusion decision at a screening stage."""

    INCLUDE = "include"
    EXCLUDE = "exclude"
    UNCERTAIN = "uncertain"


class AIRecommendation(BaseModel):
    """AI-generated screening recommendation stored separately from human judgement."""

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


class ScreeningDecision(BaseModel):
    """Immutable screening event for one publication, reviewer and stage."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    decision_id: UUID = Field(default_factory=uuid4)
    publication_id: UUID
    stage: ScreeningStage
    human_outcome: ScreeningOutcome | None = None
    reviewer_id: str | None = None
    exclusion_reason: str | None = None
    notes: str | None = None
    ai_recommendation: AIRecommendation | None = None
    decided_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("reviewer_id", "exclusion_reason", "notes")
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("text fields must not be blank")
        return stripped

    @field_validator("decided_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("decided_at must be timezone-aware")
        return value

    @model_validator(mode="after")
    def validate_decision(self) -> "ScreeningDecision":
        if self.human_outcome is None and self.ai_recommendation is None:
            raise ValueError(
                "a screening decision must contain a human outcome or AI recommendation"
            )

        if self.human_outcome is not None and self.reviewer_id is None:
            raise ValueError("reviewer_id is required for a human screening outcome")

        if self.human_outcome is None and self.reviewer_id is not None:
            raise ValueError("reviewer_id requires a human screening outcome")

        if (
            self.human_outcome is ScreeningOutcome.EXCLUDE
            and self.exclusion_reason is None
        ):
            raise ValueError("exclusion_reason is required when excluding a publication")

        if (
            self.human_outcome is not ScreeningOutcome.EXCLUDE
            and self.exclusion_reason is not None
        ):
            raise ValueError("exclusion_reason is only valid for an exclusion")

        return self
