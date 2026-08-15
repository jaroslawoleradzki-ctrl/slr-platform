"""DTOs for Phase 10 Evidence Synthesis and Terminology Classification."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CategoryDTO(BaseModel):
    """DTO representing an analytical taxonomy category."""

    model_config = ConfigDict(extra="forbid")

    category_id: str
    name: str
    project_id: str = ""
    description: str | None = None
    display_order: int = 0


class CreateCategoryRequestDTO(BaseModel):
    """Request payload for creating a new analytical category."""

    model_config = ConfigDict(extra="forbid")

    category_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    description: str | None = None
    display_order: int = 0


class UpdateCategoryRequestDTO(BaseModel):
    """Request payload for updating an analytical category."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    description: str | None = None
    display_order: int = 0


class ClassifiedSourceTermDTO(BaseModel):
    """DTO representing a discovered source term with its analytical mapping state."""

    model_config = ConfigDict(extra="forbid")

    project_id: str
    term_type: str
    source_value: str
    occurrence_count: int
    publication_count: int
    analytical_category_id: str | None = None
    analytical_category_name: str | None = None
    approval_state: str
    approved_by: str | None = None
    approved_at: datetime | None = None
    mapping_id: UUID | None = None


class SetTermMappingRequestDTO(BaseModel):
    """Request payload for setting or updating a term-to-category mapping."""

    model_config = ConfigDict(extra="forbid")

    term_type: str = Field(pattern="^(lean_practice|energy_effect)$")
    source_value: str = Field(min_length=1)
    analytical_category_id: str = Field(min_length=1)


class ApproveTermMappingRequestDTO(BaseModel):
    """Request payload for explicitly approving a term mapping."""

    model_config = ConfigDict(extra="forbid")

    term_type: str = Field(pattern="^(lean_practice|energy_effect)$")
    source_value: str = Field(min_length=1)
    reviewer_id: str = Field(min_length=1)


class TermMappingDTO(BaseModel):
    """DTO representing a saved term mapping."""

    model_config = ConfigDict(extra="forbid")

    mapping_id: UUID
    project_id: str
    term_type: str
    source_value: str
    analytical_category_id: str
    approval_state: str
    approved_by: str | None = None
    approved_at: datetime | None = None


class ClassificationWorkspaceStatsDTO(BaseModel):
    """Summary statistics for classification workspace."""

    model_config = ConfigDict(extra="forbid")

    total_lean_terms: int
    total_energy_terms: int
    total_terms: int
    mapped_count: int
    approved_count: int


class TerminologyClassificationWorkspaceDTO(BaseModel):
    """Complete workspace payload for terminology classification."""

    model_config = ConfigDict(extra="forbid")

    project_id: str
    lean_categories: list[CategoryDTO]
    energy_categories: list[CategoryDTO]
    lean_terms: list[ClassifiedSourceTermDTO]
    energy_terms: list[ClassifiedSourceTermDTO]
    stats: ClassificationWorkspaceStatsDTO
