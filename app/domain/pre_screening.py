from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class PreScreeningStatus(StrEnum):
    RETAINED = "retained"
    REMOVED = "removed"


class PreScreeningRemovalReason(StrEnum):
    CLEARLY_OUTSIDE_SCOPE = "clearly_outside_scope"
    RETRIEVAL_ARTEFACT = "retrieval_artefact"
    INCOMPLETE_RECORD = "incomplete_record"
    OTHER = "other"


class PreScreeningDecision(BaseModel):
    """Auditable record representing a pre-screening decision before formal Screening."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    decision_id: UUID = Field(default_factory=uuid4)
    project_id: str = Field(min_length=1)
    record_id: UUID
    import_id: UUID | None = None
    status: PreScreeningStatus
    reason: PreScreeningRemovalReason | None = None
    notes: str | None = None
    reviewer_id: str = "default_reviewer"
    decided_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("project_id", "reviewer_id")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("field must not be blank")
        return stripped

    @field_validator("notes")
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @field_validator("decided_at", "created_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("datetime must be timezone-aware")
        return value

    @model_validator(mode="after")
    def validate_removal_contract(self) -> "PreScreeningDecision":
        if self.status is PreScreeningStatus.REMOVED:
            if self.reason is None:
                raise ValueError("a removal reason is required when status is 'removed'")
            if self.reason is PreScreeningRemovalReason.OTHER and not self.notes:
                raise ValueError("a note is required when removal reason is 'other'")
        elif self.status is PreScreeningStatus.RETAINED:
            # When restoring or retained, reason/notes are not required
            pass
        return self
