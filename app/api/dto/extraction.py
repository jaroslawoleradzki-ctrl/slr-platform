"""Data Transfer Objects for Data Extraction Phase 9.3."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ProjectExtractionConfigurationRequestDTO(BaseModel):
    """Request DTO to set or update project extraction configuration."""

    model_config = ConfigDict(extra="forbid")

    template_id: str = Field(..., description="Extraction template identifier (e.g. 'generic_extraction').")
    template_version: str = Field(..., description="Immutable template semver version (e.g. '1.0.0').")


class ProjectExtractionConfigurationResponseDTO(BaseModel):
    """Response DTO representing active project extraction configuration."""

    model_config = ConfigDict(extra="forbid")

    project_id: str
    template_id: str
    template_version: str
    configured_at: str
    updated_at: str


class ExtractionEligibilityResultDTO(BaseModel):
    """Response DTO for publication extraction eligibility status."""

    model_config = ConfigDict(extra="forbid")

    publication_id: UUID
    status: str
    is_eligible: bool
    reason_details: str | None = None


class ExtractionEligibilityListResponseDTO(BaseModel):
    """Response DTO for list of publication eligibility statuses in a project."""

    model_config = ConfigDict(extra="forbid")

    project_id: str
    total_publications: int
    eligible_count: int
    items: list[ExtractionEligibilityResultDTO]
