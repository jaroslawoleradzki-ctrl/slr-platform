"""DTOs for Phase 10 Evidence Synthesis, Terminology Classification, and Analytical Matrix."""

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


# -------------------------------------------------------------------------
# Task 10.3: Analytical Matrix & Evidence Aggregation DTOs
# -------------------------------------------------------------------------


class ConvertedValueDTO(BaseModel):
    """DTO representing a calculated physical energy unit conversion."""

    model_config = ConfigDict(extra="forbid")

    transformed_value: float
    transformed_unit: str
    conversion_rule: str


class MatrixCellDTO(BaseModel):
    """Aggregated matrix cell DTO for Lean × Energy intersection."""

    model_config = ConfigDict(extra="forbid")

    lean_category_id: str
    lean_category_name: str
    energy_category_id: str
    energy_category_name: str
    relation_count: int
    publication_count: int
    direction_distribution: dict[str, int]
    evidence_character_distribution: dict[str, int]


class SynthesisMatrixDTO(BaseModel):
    """Complete M × N analytical matrix payload."""

    model_config = ConfigDict(extra="forbid")

    project_id: str
    lean_categories: list[CategoryDTO]
    energy_categories: list[CategoryDTO]
    cells: list[MatrixCellDTO]
    total_relations: int
    total_publications: int
    unclassified_relations_count: int


class QACriterionAssessmentSummaryDTO(BaseModel):
    """DTO for an individual QA criterion evaluation."""

    model_config = ConfigDict(extra="forbid")

    criterion_id: UUID
    question_text: str
    response_value: str
    justification: str | None = None


class QAProfileSummaryDTO(BaseModel):
    """DTO for a publication QA evaluation profile."""

    model_config = ConfigDict(extra="forbid")

    assessment_id: UUID
    template_id: UUID
    reviewer_id: str
    criteria_assessments: list[QACriterionAssessmentSummaryDTO]


class AnalyticalRelationDTO(BaseModel):
    """DTO representing an analytical Lean-EE relation."""

    model_config = ConfigDict(extra="forbid")

    relation_id: UUID
    project_id: str
    publication_id: UUID
    latest_revision_id: UUID
    group_item_id: UUID
    item_index: int
    source_practice: str
    analytical_lean_category_id: str | None = None
    source_effect: str
    analytical_energy_category_id: str | None = None
    direction: str
    magnitude: float | None = None
    original_unit: str | None = None
    converted_value: ConvertedValueDTO | None = None
    evidence_character: str
    context_summary: str | None = None
    approval_state: str
    created_at: datetime
    updated_at: datetime


class AnalyticalRelationDetailDTO(BaseModel):
    """DTO representing detailed relation with publication, QA, and quote provenance."""

    model_config = ConfigDict(extra="forbid")

    relation: AnalyticalRelationDTO
    publication_title: str | None = None
    publication_year: int | None = None
    source_quote: str | None = None
    source_page: str | None = None
    source_section: str | None = None
    qa_profile: QAProfileSummaryDTO | None = None


class MatrixCellDetailDTO(BaseModel):
    """Complete detail payload for matrix cell drill-down."""

    model_config = ConfigDict(extra="forbid")

    lean_category: CategoryDTO
    energy_category: CategoryDTO
    relation_count: int
    publication_count: int
    direction_distribution: dict[str, int]
    evidence_character_distribution: dict[str, int]
    relations: list[AnalyticalRelationDetailDTO]


class ConvertUnitRequestDTO(BaseModel):
    """Request payload for unit conversion calculation or save."""

    model_config = ConfigDict(extra="forbid")

    target_unit: str = Field(min_length=1)
