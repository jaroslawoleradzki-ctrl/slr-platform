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


class MechanismPathwayDTO(BaseModel):
    """DTO representing a mechanism pathway."""

    model_config = ConfigDict(extra="forbid")

    pathway_id: UUID
    project_id: str
    analytical_relation_id: UUID
    group_item_id: UUID
    publication_id: UUID
    latest_revision_id: UUID
    source_mechanism_text: str | None = None
    analytical_mechanism_category_id: str | None = None
    is_review_synthesized: bool = False
    approval_state: str
    approved_by: str | None = None
    approved_at: datetime | None = None
    notes: str | None = None
    created_at: datetime
    updated_at: datetime


class AssignMechanismCategoryRequestDTO(BaseModel):
    """Request payload for assigning an analytical mechanism category."""

    model_config = ConfigDict(extra="forbid")

    category_id: str | None = None
    is_review_synthesized: bool = False
    notes: str | None = None


class ApproveMechanismPathwayRequestDTO(BaseModel):
    """Request payload for approving a mechanism pathway classification."""

    model_config = ConfigDict(extra="forbid")

    reviewer_id: str = Field(min_length=1)


class MechanismPathwayDetailDTO(BaseModel):
    """Detailed view of a mechanism pathway with relation, publication, and QA provenance."""

    model_config = ConfigDict(extra="forbid")

    pathway: MechanismPathwayDTO
    publication_title: str | None = None
    publication_year: int | None = None
    source_practice: str
    source_effect: str
    analytical_lean_category_id: str | None = None
    analytical_lean_category_name: str | None = None
    analytical_energy_category_id: str | None = None
    analytical_energy_category_name: str | None = None
    analytical_mechanism_category_name: str | None = None
    direction: str
    evidence_character: str
    qa_profile: QAProfileSummaryDTO | None = None


class MechanismSynthesisPathwayDTO(BaseModel):
    """Aggregated synthesis chain: Lean Category -> Mechanism Category -> Energy Category."""

    model_config = ConfigDict(extra="forbid")

    lean_category_id: str
    lean_category_name: str
    mechanism_category_id: str
    mechanism_category_name: str
    energy_category_id: str
    energy_category_name: str
    pathway_count: int
    publication_count: int
    relation_count: int
    pathways: list[MechanismPathwayDetailDTO]


class MechanismWorkspaceStatsDTO(BaseModel):
    """Statistical summary of mechanism synthesis progress."""

    model_config = ConfigDict(extra="forbid")

    total_pathways: int
    mapped_count: int
    unmapped_count: int
    approved_count: int
    total_publications: int


class MechanismWorkspaceDataDTO(BaseModel):
    """Complete dataset for the Mechanism Synthesis Workspace."""

    model_config = ConfigDict(extra="forbid")

    project_id: str
    categories: list[CategoryDTO]
    pathways: list[MechanismPathwayDetailDTO]
    synthesis_chains: list[MechanismSynthesisPathwayDTO]
    stats: MechanismWorkspaceStatsDTO


# -------------------------------------------------------------------------
# Task 10.5: Context & Moderating Factors DTOs
# -------------------------------------------------------------------------


class ContextCategoryDTO(BaseModel):
    """DTO representing a researcher-created context taxonomy category."""

    model_config = ConfigDict(extra="forbid")

    category_id: str
    name: str
    project_id: str = ""
    description: str | None = None
    display_order: int = 0


class CreateContextCategoryRequestDTO(BaseModel):
    """Request payload for creating a new context category."""

    model_config = ConfigDict(extra="forbid")

    category_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    description: str | None = None
    display_order: int = 0


class UpdateContextCategoryRequestDTO(BaseModel):
    """Request payload for updating a context category."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    description: str | None = None
    display_order: int = 0


class ContextAssignmentDTO(BaseModel):
    """DTO representing an assignment of source context evidence to a category."""

    model_config = ConfigDict(extra="forbid")

    assignment_id: UUID
    project_id: str
    analytical_relation_id: UUID
    group_item_id: UUID
    publication_id: UUID
    latest_revision_id: UUID
    source_context_text: str
    analytical_context_category_id: str | None = None
    context_impact: str = Field(min_length=1)  # ENABLE, STRENGTHEN, WEAKEN, CONDITION
    approval_state: str
    approved_by: str | None = None
    approved_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class AssignContextToRelationRequestDTO(BaseModel):
    """Request payload for assigning source context evidence to a relation."""

    model_config = ConfigDict(extra="forbid")

    category_id: str = Field(min_length=1)
    context_impact: str = Field(min_length=1, pattern="^(ENABLE|STRENGTHEN|WEAKEN|CONDITION)$")


class UnassignContextRequestDTO(BaseModel):
    """Request payload for unassigning context from a relation."""

    model_config = ConfigDict(extra="forbid")


class ContextSynthesisSummaryDTO(BaseModel):
    """Deterministic context synthesis summary statistics."""

    model_config = ConfigDict(extra="forbid")

    context_evidence_count: int
    distinct_publication_count: int
    distinct_analytical_relation_count: int
    distinct_mechanism_pathway_count: int


class ContextWorkspaceDataDTO(BaseModel):
    """Complete dataset for the Context Synthesis Workspace."""

    model_config = ConfigDict(extra="forbid")

    project_id: str
    categories: list[ContextCategoryDTO]
    assignments: list[ContextAssignmentDTO]
    stats: ContextSynthesisSummaryDTO


# -------------------------------------------------------------------------
# Task 10.6: Research Gap Synthesis DTOs
# -------------------------------------------------------------------------


class ResearchGapDTO(BaseModel):
    """DTO representing a researcher-authored research gap."""

    model_config = ConfigDict(extra="forbid")

    gap_id: UUID
    project_id: str
    gap_type: str
    title: str
    rationale: str
    researcher_id: str
    created_at: datetime
    updated_at: datetime


class ResearchGapLinkDTO(BaseModel):
    """DTO representing a traceable evidence link for a research gap."""

    model_config = ConfigDict(extra="forbid")

    link_id: UUID
    project_id: str
    gap_id: UUID
    link_type: str
    target_id: UUID
    group_item_id: UUID
    publication_id: UUID
    latest_revision_id: UUID
    created_at: datetime


class ResearchGapDetailDTO(BaseModel):
    """DTO representing a research gap with its supporting evidence links."""

    model_config = ConfigDict(extra="forbid")

    gap: ResearchGapDTO
    links: list[ResearchGapLinkDTO]


class ResearchGapWorkspaceStatsDTO(BaseModel):
    """Count-only statistics for the research gap workspace (no scoring)."""

    model_config = ConfigDict(extra="forbid")

    total_gaps: int
    thematic_count: int
    mechanism_count: int
    methodological_count: int
    contextual_count: int
    inconsistent_evidence_count: int
    linked_publication_count: int


class ResearchGapWorkspaceDataDTO(BaseModel):
    """Complete dataset for the Research Gap Synthesis Workspace."""

    model_config = ConfigDict(extra="forbid")

    project_id: str
    gaps: list[ResearchGapDetailDTO]
    stats: ResearchGapWorkspaceStatsDTO


class ResearchGapEvidenceCandidateDTO(BaseModel):
    """DTO representing a candidate synthesis artifact eligible for linking."""

    model_config = ConfigDict(extra="forbid")

    link_type: str
    target_id: UUID
    group_item_id: UUID
    publication_id: UUID
    latest_revision_id: UUID
    traceable: bool
    label: str
    publication_title: str | None = None
    publication_year: int | None = None
    qa_profile: QAProfileSummaryDTO | None = None


class CreateResearchGapRequestDTO(BaseModel):
    """Request payload for creating a research gap."""

    model_config = ConfigDict(extra="forbid")

    gap_type: str = Field(min_length=1)
    title: str = Field(min_length=1)
    rationale: str = Field(min_length=1)
    researcher_id: str = Field(min_length=1)


class UpdateResearchGapRequestDTO(BaseModel):
    """Request payload for updating a research gap."""

    model_config = ConfigDict(extra="forbid")

    gap_type: str | None = None
    title: str | None = None
    rationale: str | None = None


class LinkEvidenceRequestDTO(BaseModel):
    """Request payload for linking evidence to a research gap."""

    model_config = ConfigDict(extra="forbid")

    link_type: str = Field(pattern="^(analytical_relation|mechanism_pathway|context_factor_link)$")
    target_id: UUID
