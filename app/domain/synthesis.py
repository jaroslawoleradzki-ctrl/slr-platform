"""Phase 10: Core Data Synthesis / Evidence Synthesis domain models.

Pure Python domain objects, enums, value objects, and relation models
establishing deterministic evidence synthesis, terminology classification,
and QA profile integration.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ValueOrigin(StrEnum):
    """Origin/attribution of an extracted value."""

    REPORTED = "reported"
    REVIEWER_CODED = "reviewer_coded"


class RelationDirection(StrEnum):
    """Direction of the observed effect on energy performance."""

    POSITIVE = "positive"  # Efficiency improvement / consumption reduction
    NEGATIVE = "negative"  # Efficiency degradation / consumption increase
    NO_EFFECT = "no_effect"  # Statistically or qualitatively no change observed
    MIXED = "mixed"  # Inconsistent or context-dependent effects within study
    CANNOT_DETERMINE = "cannot_determine"  # Insufficient information reported


class EvidenceCharacter(StrEnum):
    """Methodological character of the reported empirical evidence."""

    EMPIRICAL = "empirical"  # Measured, metered, or direct statistical observation
    QUALITATIVE = "qualitative"  # Descriptive narrative, expert interview, observation
    ESTIMATED = "estimated"  # Simulated, engineering calculation, model-based
    POSTULATED = "postulated"  # Theoretical proposition or author assertion


class ClassificationApprovalState(StrEnum):
    """Reviewer approval state for analytical category assignments."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class TermType(StrEnum):
    """Discriminator for terminology classification domain."""

    LEAN_PRACTICE = "lean_practice"
    ENERGY_EFFECT = "energy_effect"


# Standard energy conversion factors to Base Unit (Joules) for pure domain validation
_ENERGY_FACTORS_TO_JOULES: dict[str, float] = {
    "j": 1.0,
    "kj": 1_000.0,
    "mj": 1_000_000.0,
    "gj": 1_000_000_000.0,
    "wh": 3_600.0,
    "kwh": 3_600_000.0,
    "mwh": 3_600_000_000.0,
}


def convert_physical_energy_unit(value: float, from_unit: str, to_unit: str) -> tuple[float, str, str]:
    """Deterministically calculates standard physical energy unit conversion.

    Returns (converted_value, standard_to_unit, conversion_rule_description).
    Raises ValueError if conversion is unsupported or attempts cross-metric transformation.
    """
    from_u = from_unit.strip().lower()
    to_u = to_unit.strip().lower()

    if from_u not in _ENERGY_FACTORS_TO_JOULES or to_u not in _ENERGY_FACTORS_TO_JOULES:
        raise ValueError(
            f"Unsupported physical energy unit conversion from '{from_unit}' to '{to_unit}'. "
            f"Supported units: {list(_ENERGY_FACTORS_TO_JOULES.keys())}"
        )

    val_in_joules = value * _ENERGY_FACTORS_TO_JOULES[from_u]
    converted_val = val_in_joules / _ENERGY_FACTORS_TO_JOULES[to_u]
    rule_desc = f"1 {from_unit} = {(_ENERGY_FACTORS_TO_JOULES[from_u] / _ENERGY_FACTORS_TO_JOULES[to_u]):.6g} {to_unit}"

    return converted_val, to_unit, rule_desc


class ConvertedValue(BaseModel):
    """Pure domain representation of a calculated converted numeric value."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    transformed_value: float
    transformed_unit: str = Field(min_length=1)
    conversion_rule: str = Field(min_length=1)


class LeanPracticeCategory(BaseModel):
    """Standardized analytical Lean practice taxonomy category."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    category_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    project_id: str = Field(default="", min_length=0)
    description: str | None = None
    display_order: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("created_at", "updated_at")
    @classmethod
    def validate_tz(cls, v: datetime) -> datetime:
        if v.tzinfo is None or v.utcoffset() is None:
            raise ValueError("timestamps must be timezone-aware")
        return v


class EnergyEffectCategory(BaseModel):
    """Standardized analytical Energy effect taxonomy category."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    category_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    project_id: str = Field(default="", min_length=0)
    description: str | None = None
    display_order: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("created_at", "updated_at")
    @classmethod
    def validate_tz(cls, v: datetime) -> datetime:
        if v.tzinfo is None or v.utcoffset() is None:
            raise ValueError("timestamps must be timezone-aware")
        return v


class TermMapping(BaseModel):
    """Researcher mapping from an empirical source term to an analytical category."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    mapping_id: UUID = Field(default_factory=uuid4)
    project_id: str = Field(min_length=1)
    term_type: TermType
    source_value: str = Field(min_length=1)
    analytical_category_id: str = Field(min_length=1)
    approval_state: ClassificationApprovalState = ClassificationApprovalState.PENDING
    approved_by: str | None = None
    approved_at: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("approved_at")
    @classmethod
    def validate_approved_at(cls, v: datetime | None) -> datetime | None:
        if v is not None and (v.tzinfo is None or v.utcoffset() is None):
            raise ValueError("approved_at must be timezone-aware")
        return v

    @field_validator("created_at", "updated_at")
    @classmethod
    def validate_tz(cls, v: datetime) -> datetime:
        if v.tzinfo is None or v.utcoffset() is None:
            raise ValueError("timestamps must be timezone-aware")
        return v


class ClassifiedSourceTerm(BaseModel):
    """Discovered source term combined with its current analytical mapping state."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    project_id: str = Field(min_length=1)
    term_type: TermType
    source_value: str = Field(min_length=1)
    occurrence_count: int = Field(ge=0, default=1)
    publication_count: int = Field(ge=0, default=1)
    analytical_category_id: str | None = None
    analytical_category_name: str | None = None
    approval_state: ClassificationApprovalState = ClassificationApprovalState.PENDING
    approved_by: str | None = None
    approved_at: datetime | None = None
    mapping_id: UUID | None = None


class QACriterionAssessmentSummary(BaseModel):
    """Snapshot of an individual QA criterion evaluation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    criterion_id: UUID
    question_text: str = Field(min_length=1)
    response_value: str = Field(min_length=1)
    justification: str | None = None


class QAProfileSummary(BaseModel):
    """Aggregated QA evaluation profile without arbitrary score flattening."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    assessment_id: UUID
    template_id: UUID
    reviewer_id: str = Field(min_length=1)
    criteria_assessments: list[QACriterionAssessmentSummary] = Field(default_factory=list)


class ExtractionEvidenceReference(BaseModel):
    """Explicit, non-heuristic traceability reference to Phase 9 extraction evidence."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    reference_id: UUID = Field(default_factory=uuid4)
    project_id: str = Field(min_length=1)
    publication_id: UUID
    revision_id: UUID
    group_key: str | None = None
    group_item_id: UUID | None = None  # Durable identity for 1:N repeating group items
    field_key: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("created_at")
    @classmethod
    def validate_tz(cls, v: datetime) -> datetime:
        if v.tzinfo is None or v.utcoffset() is None:
            raise ValueError("created_at must be timezone-aware")
        return v


class AnalyticalRelation(BaseModel):
    """In-memory synthesized analytical unit linked to a durable Phase 9 repeating-group item."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    relation_id: UUID = Field(default_factory=uuid4)
    project_id: str = Field(min_length=1)
    publication_id: UUID
    latest_revision_id: UUID
    group_item_id: UUID  # Durable identity matching Phase 9 ExtractedGroupItemState.group_item_id
    item_index: int = Field(ge=1)
    source_practice: str = Field(min_length=1)
    analytical_lean_category_id: str | None = None
    source_effect: str = Field(min_length=1)
    analytical_energy_category_id: str | None = None
    direction: RelationDirection = RelationDirection.CANNOT_DETERMINE
    magnitude: float | None = None
    original_unit: str | None = None
    converted_value: ConvertedValue | None = None
    evidence_character: EvidenceCharacter = EvidenceCharacter.EMPIRICAL
    qa_profile: QAProfileSummary | None = None
    context_summary: str | None = None
    approval_state: ClassificationApprovalState = ClassificationApprovalState.PENDING
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("created_at", "updated_at")
    @classmethod
    def validate_tz(cls, v: datetime) -> datetime:
        if v.tzinfo is None or v.utcoffset() is None:
            raise ValueError("timestamps must be timezone-aware")
        return v


class MatrixCell(BaseModel):
    """Aggregated evidence cell for a Lean Category × Energy Effect Category intersection."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    lean_category_id: str
    lean_category_name: str
    energy_category_id: str
    energy_category_name: str
    relation_count: int = Field(ge=0, default=0)
    publication_count: int = Field(ge=0, default=0)
    direction_distribution: dict[str, int] = Field(default_factory=dict)
    evidence_character_distribution: dict[str, int] = Field(default_factory=dict)


class SynthesisMatrix(BaseModel):
    """Aggregated M × N analytical matrix for a project."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    project_id: str = Field(min_length=1)
    lean_categories: list[LeanPracticeCategory] = Field(default_factory=list)
    energy_categories: list[EnergyEffectCategory] = Field(default_factory=list)
    cells: list[MatrixCell] = Field(default_factory=list)
    total_relations: int = Field(ge=0, default=0)
    total_publications: int = Field(ge=0, default=0)
    unclassified_relations_count: int = Field(ge=0, default=0)


class AnalyticalRelationDetail(BaseModel):
    """Detailed view of an analytical relation with publication info, QA profile, and provenance."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    relation: AnalyticalRelation
    publication_title: str | None = None
    publication_year: int | None = None
    source_quote: str | None = None
    source_page: str | None = None
    source_section: str | None = None
    qa_profile: QAProfileSummary | None = None


class MatrixCellDetail(BaseModel):
    """Detailed drill-down response for an individual matrix cell."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    lean_category: LeanPracticeCategory
    energy_category: EnergyEffectCategory
    relation_count: int = Field(ge=0, default=0)
    publication_count: int = Field(ge=0, default=0)
    direction_distribution: dict[str, int] = Field(default_factory=dict)
    evidence_character_distribution: dict[str, int] = Field(default_factory=dict)
    relations: list[AnalyticalRelationDetail] = Field(default_factory=list)


class MechanismOriginType(StrEnum):
    """Origin attribution for mechanism pathways."""

    SOURCE_REPORTED = "source_reported"
    REVIEW_SYNTHESIZED = "review_synthesized"


class AnalyticalMechanismCategory(BaseModel):
    """Standardized analytical mechanism taxonomy category."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    category_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    project_id: str = Field(default="", min_length=0)
    description: str | None = None
    display_order: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("created_at", "updated_at")
    @classmethod
    def validate_tz(cls, v: datetime) -> datetime:
        if v.tzinfo is None or v.utcoffset() is None:
            raise ValueError("timestamps must be timezone-aware")
        return v


class MechanismPathway(BaseModel):
    """Pathway linking a Lean–EE analytical relation to an analytical mechanism category."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    pathway_id: UUID = Field(default_factory=uuid4)
    project_id: str = Field(min_length=1)
    analytical_relation_id: UUID
    group_item_id: UUID
    publication_id: UUID
    latest_revision_id: UUID
    source_mechanism_text: str | None = None
    analytical_mechanism_category_id: str | None = None
    is_review_synthesized: bool = False
    approval_state: ClassificationApprovalState = ClassificationApprovalState.PENDING
    approved_by: str | None = None
    approved_at: datetime | None = None
    notes: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("approved_at")
    @classmethod
    def validate_approved_at(cls, v: datetime | None) -> datetime | None:
        if v is not None and (v.tzinfo is None or v.utcoffset() is None):
            raise ValueError("approved_at must be timezone-aware")
        return v

    @field_validator("created_at", "updated_at")
    @classmethod
    def validate_tz(cls, v: datetime) -> datetime:
        if v.tzinfo is None or v.utcoffset() is None:
            raise ValueError("timestamps must be timezone-aware")
        return v


class MechanismPathwayDetail(BaseModel):
    """Detailed view of a mechanism pathway with relation, publication, and QA provenance."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    pathway: MechanismPathway
    publication_title: str | None = None
    publication_year: int | None = None
    source_practice: str = Field(min_length=1)
    source_effect: str = Field(min_length=1)
    analytical_lean_category_id: str | None = None
    analytical_lean_category_name: str | None = None
    analytical_energy_category_id: str | None = None
    analytical_energy_category_name: str | None = None
    analytical_mechanism_category_name: str | None = None
    direction: RelationDirection = RelationDirection.CANNOT_DETERMINE
    evidence_character: EvidenceCharacter = EvidenceCharacter.EMPIRICAL
    qa_profile: QAProfileSummary | None = None


class MechanismSynthesisPathway(BaseModel):
    """Aggregated synthesis chain: Lean Category -> Mechanism Category -> Energy Category."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    lean_category_id: str
    lean_category_name: str
    mechanism_category_id: str
    mechanism_category_name: str
    energy_category_id: str
    energy_category_name: str
    pathway_count: int = Field(ge=0, default=0)
    publication_count: int = Field(ge=0, default=0)
    relation_count: int = Field(ge=0, default=0)
    pathways: list[MechanismPathwayDetail] = Field(default_factory=list)


class MechanismWorkspaceStats(BaseModel):
    """Statistical summary of mechanism synthesis progress."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    total_pathways: int = Field(ge=0, default=0)
    mapped_count: int = Field(ge=0, default=0)
    unmapped_count: int = Field(ge=0, default=0)
    approved_count: int = Field(ge=0, default=0)
    total_publications: int = Field(ge=0, default=0)


class ContextCategory(BaseModel):
    """Researcher-created analytical context taxonomy category for moderating factors."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    category_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    project_id: str = Field(default="", min_length=0)
    description: str | None = None
    display_order: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("created_at", "updated_at")
    @classmethod
    def validate_tz(cls, v: datetime) -> datetime:
        if v.tzinfo is None or v.utcoffset() is None:
            raise ValueError("timestamps must be timezone-aware")
        return v


class ContextAssignment(BaseModel):
    """Assignment of source context evidence (E11 moderating_conditions) to an analytical context category."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    assignment_id: UUID = Field(default_factory=uuid4)
    project_id: str = Field(min_length=1)
    analytical_relation_id: UUID
    group_item_id: UUID
    publication_id: UUID
    latest_revision_id: UUID
    source_context_text: str  # The exact E11 moderating conditions text
    analytical_context_category_id: str | None = None  # Researcher-created category
    context_impact: str = Field(min_length=1)  # ENABLE, STRENGTHEN, WEAKEN, CONDITION
    approval_state: ClassificationApprovalState = ClassificationApprovalState.PENDING
    approved_by: str | None = None
    approved_at: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("created_at", "updated_at", "approved_at")
    @classmethod
    def validate_tz(cls, v: datetime | None) -> datetime | None:
        if v is None:
            return None
        if v.tzinfo is None or v.utcoffset() is None:
            raise ValueError("timestamps must be timezone-aware")
        return v


class ContextWorkspaceData(BaseModel):
    """Complete dataset for the Context Synthesis Workspace."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    project_id: str = Field(min_length=1)
    categories: list[ContextCategory] = Field(default_factory=list)
    assignments: list[ContextAssignment] = Field(default_factory=list)
    stats: dict[str, int]


class MechanismWorkspaceData(BaseModel):
    """Complete dataset for the Mechanism Synthesis Workspace."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    project_id: str = Field(min_length=1)
    categories: list[AnalyticalMechanismCategory] = Field(default_factory=list)
    pathways: list[MechanismPathwayDetail] = Field(default_factory=list)
    synthesis_chains: list[MechanismSynthesisPathway] = Field(default_factory=list)
    stats: MechanismWorkspaceStats
