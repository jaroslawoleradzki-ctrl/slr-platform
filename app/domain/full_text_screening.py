from __future__ import annotations

from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class FullTextAvailabilityStatus(StrEnum):
    """Workflow metadata describing whether a reviewer can access full text."""

    UNKNOWN = "unknown"
    TO_RETRIEVE = "to_retrieve"
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"


class FullTextAvailability(BaseModel):
    """Project-scoped, non-destructive full-text access metadata.

    This deliberately stores a reference only, never downloaded or copyrighted
    full-text content.  Its status does not determine a screening outcome.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    project_id: str = Field(min_length=1)
    publication_id: UUID
    status: FullTextAvailabilityStatus = FullTextAvailabilityStatus.UNKNOWN
    external_url: str | None = None
    notes: str | None = None

    @field_validator("project_id")
    @classmethod
    def validate_project_id(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("project_id must not be blank")
        return value

    @field_validator("external_url")
    @classmethod
    def validate_external_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            return None
        if not value.startswith(("https://", "http://")):
            raise ValueError("external_url must use http or https")
        return value

    @field_validator("notes")
    @classmethod
    def normalize_notes(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None
