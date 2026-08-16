"""Phase 10: Core Data Synthesis / Evidence Synthesis domain models.

Pure Python domain objects, enums, value objects, and relation models
establishing deterministic evidence synthesis, terminology classification,
and QA profile integration.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.domain.extraction import (
    ExtractedValueState,
    ExtractionCompletenessStatus,
    ExtractionRevision,
)


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


class ResearchGapType(StrEnum):
    """Researcher-identified research gap dimensions (Task 10.6)."""

    THEMATIC = "thematic"  # Under-studied practices/effects/combinations
    MECHANISM = "mechanism"  # Reported effects without plausible mechanism explanations
    METHODOLOGICAL = "methodological"  # Recurring study design or measurement limitations
    CONTEXTUAL = "contextual"  # Missing evidence in specific industries, countries, or scales
    INCONSISTENT_EVIDENCE = "inconsistent_evidence"  # Conflicting results not explained by context/methodology


class ResearchGapLinkType(StrEnum):
    """Type of synthesis evidence artifact linked to a research gap."""

    ANALYTICAL_RELATION = "analytical_relation"
    MECHANISM_PATHWAY = "mechanism_pathway"
    CONTEXT_FACTOR_LINK = "context_factor_link"


class ResearchGap(BaseModel):
    """Researcher-authored analytical conclusion identifying a research gap.

    A gap is a human interpretation backed by traceable evidence links.
    Publication count alone never establishes a gap; low publication count
    is evidence input, not a conclusion. No automated scoring or ranking.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    gap_id: UUID = Field(default_factory=uuid4)
    project_id: str = Field(min_length=1)
    gap_type: ResearchGapType
    title: str = Field(min_length=1)
    rationale: str = Field(min_length=1)  # Researcher-authored justification for the gap
    researcher_id: str = Field(min_length=1)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("created_at", "updated_at")
    @classmethod
    def validate_tz(cls, v: datetime) -> datetime:
        if v.tzinfo is None or v.utcoffset() is None:
            raise ValueError("timestamps must be timezone-aware")
        return v


class ResearchGapLink(BaseModel):
    """Traceable evidence link from a research gap to a synthesis artifact.

    Enforces the traceability chain:
    ResearchGap -> ResearchGapLink -> AnalyticalRelation / MechanismPathway /
    ContextFactorLink -> group_item_id -> latest eligible COMPLETE extraction
    revision -> source evidence -> publication -> criterion-level QA profile.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    link_id: UUID = Field(default_factory=uuid4)
    project_id: str = Field(min_length=1)
    gap_id: UUID
    link_type: ResearchGapLinkType
    target_id: UUID  # relation_id / pathway_id / context link assignment_id
    group_item_id: UUID
    publication_id: UUID
    latest_revision_id: UUID
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("created_at")
    @classmethod
    def validate_tz(cls, v: datetime) -> datetime:
        if v.tzinfo is None or v.utcoffset() is None:
            raise ValueError("created_at must be timezone-aware")
        return v


class ResearchGapDetail(BaseModel):
    """A research gap with its supporting evidence links."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    gap: ResearchGap
    links: list[ResearchGapLink] = Field(default_factory=list)


class ResearchGapWorkspaceStats(BaseModel):
    """Deterministic count-only summary of research gap workspace (no scoring)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    total_gaps: int = Field(ge=0, default=0)
    thematic_count: int = Field(ge=0, default=0)
    mechanism_count: int = Field(ge=0, default=0)
    methodological_count: int = Field(ge=0, default=0)
    contextual_count: int = Field(ge=0, default=0)
    inconsistent_evidence_count: int = Field(ge=0, default=0)
    linked_publication_count: int = Field(ge=0, default=0)


class ResearchGapWorkspaceData(BaseModel):
    """Complete dataset for the Research Gap Synthesis Workspace."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    project_id: str = Field(min_length=1)
    gaps: list[ResearchGapDetail] = Field(default_factory=list)
    stats: ResearchGapWorkspaceStats


class ResearchGapEvidenceCandidate(BaseModel):
    """Candidate synthesis artifact eligible for linking to a research gap."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    link_type: ResearchGapLinkType
    target_id: UUID
    group_item_id: UUID
    publication_id: UUID
    latest_revision_id: UUID
    traceable: bool = False  # True only when it traces to an eligible COMPLETE revision
    label: str = Field(min_length=1)
    publication_title: str | None = None
    publication_year: int | None = None
    qa_profile: QAProfileSummary | None = None  # Criterion-level QA for researcher inspection


# ---------------------------------------------------------------------------
# Task 10.7: Synthesis Snapshots (Reproducibility & Snapshot Engine)
# ---------------------------------------------------------------------------

_DATASET_HASH_BYTES = 64


def _canonical_json_bytes(value: Any) -> bytes:
    """Serializes a value into deterministic canonical JSON bytes (sorted keys)."""

    def _default(obj: Any) -> Any:
        if isinstance(obj, UUID):
            return str(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, BaseModel):
            return obj.model_dump(mode="json")
        raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")

    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        default=_default,
    ).encode("utf-8")


def sha256_hexdigest(data: bytes) -> str:
    """Returns the lowercase SHA-256 hex digest of the given bytes."""
    return hashlib.sha256(data).hexdigest()


def canonicalize_extraction_value(value: ExtractedValueState) -> dict[str, Any]:
    """Canonical, deterministic representation of a single extracted value."""
    return {
        "field_key": value.field_key,
        "status": value.status.value,
        "origin": value.origin.value if value.origin is not None else None,
        "text_value": value.text_value,
        "int_value": value.int_value,
        "float_value": value.float_value,
        "bool_value": value.bool_value,
        "unit_value": value.unit_value,
        "json_value": value.json_value,
        "source_page": value.source_page,
        "source_section": value.source_section,
        "source_locator": value.source_locator,
        "source_quote": value.source_quote,
        "reviewer_note": value.reviewer_note,
    }


def build_extraction_dataset_items(revisions: list[ExtractionRevision]) -> list[dict[str, Any]]:
    """Builds canonical extraction item dicts from eligible COMPLETE revisions.

    DRAFT / IN_PROGRESS / NEEDS_REVIEW revisions never contribute to the
    extraction dataset identity (dataset hashing and snapshot reproducibility
    are strictly tied to eligible COMPLETE extraction evidence).
    """
    items: list[dict[str, Any]] = []
    for rev in revisions:
        if rev.completeness_status != ExtractionCompletenessStatus.COMPLETE:
            continue
        for gi in rev.group_items:
            items.append(
                {
                    "publication_id": str(rev.publication_id),
                    "revision_id": str(rev.revision_id),
                    "group_item_id": str(gi.group_item_id),
                    "group_key": gi.group_key,
                    "item_index": gi.item_index,
                    "completeness_status": ExtractionCompletenessStatus.COMPLETE.value,
                    "values": [canonicalize_extraction_value(v) for v in gi.values],
                }
            )
    return items


def compute_extraction_dataset_hash(items: list[dict[str, Any]]) -> str:
    """Deterministic SHA-256 of the eligible COMPLETE extraction dataset.

    Ordering-insensitive: items are sorted by (publication_id, group_item_id)
    and each item's values are sorted by field_key before hashing, so the same
    logical input dataset always yields the same hash regardless of database or
    query ordering. Only items whose ``completeness_status`` is ``complete``
    contribute to the dataset identity.
    """
    eligible = [item for item in items if item.get("completeness_status") == ExtractionCompletenessStatus.COMPLETE.value]
    normalized: list[dict[str, Any]] = []
    for item in sorted(eligible, key=lambda i: (str(i["publication_id"]), str(i["group_item_id"]))):
        normalized.append(
            {
                "publication_id": item["publication_id"],
                "group_item_id": item["group_item_id"],
                "group_key": item["group_key"],
                "item_index": item["item_index"],
                "values": sorted(item["values"], key=lambda v: v["field_key"]),
            }
        )
    return sha256_hexdigest(_canonical_json_bytes(normalized))


def compute_classification_version(
    *,
    lean_categories: list[LeanPracticeCategory] | None = None,
    energy_categories: list[EnergyEffectCategory] | None = None,
    mechanism_categories: list[AnalyticalMechanismCategory] | None = None,
    context_categories: list[ContextCategory] | None = None,
    term_mappings: list[TermMapping] | None = None,
    qa_configs: list[Any] | None = None,
) -> str:
    """Deterministic SHA-256 over canonicalized classification rules and QA configurations.

    Canonicalizes categories (sorted by category_id), term mappings (sorted by
    term_type then source_value), and QA configurations (sorted by template_id).
    The same classification rule set always yields the same version string.
    """
    payload: dict[str, Any] = {
        "lean_categories": sorted(
            (
                {"category_id": c.category_id, "name": c.name, "description": c.description, "display_order": c.display_order}
                for c in (lean_categories or [])
            ),
            key=lambda c: c["category_id"],
        ),
        "energy_categories": sorted(
            (
                {"category_id": c.category_id, "name": c.name, "description": c.description, "display_order": c.display_order}
                for c in (energy_categories or [])
            ),
            key=lambda c: c["category_id"],
        ),
        "mechanism_categories": sorted(
            (
                {"category_id": c.category_id, "name": c.name, "description": c.description, "display_order": c.display_order}
                for c in (mechanism_categories or [])
            ),
            key=lambda c: c["category_id"],
        ),
        "context_categories": sorted(
            (
                {"category_id": c.category_id, "name": c.name, "description": c.description, "display_order": c.display_order}
                for c in (context_categories or [])
            ),
            key=lambda c: c["category_id"],
        ),
        "term_mappings": sorted(
            (
                {
                    "term_type": m.term_type.value,
                    "source_value": m.source_value,
                    "analytical_category_id": m.analytical_category_id,
                    "approval_state": m.approval_state.value,
                    "approved_by": m.approved_by,
                }
                for m in (term_mappings or [])
            ),
            key=lambda m: (m["term_type"], m["source_value"]),
        ),
    }
    if qa_configs:
        payload["qa_configs"] = sorted(
            (
                {
                    "template_id": str(getattr(q, "template_id", "")),
                    "name": getattr(q, "name", ""),
                    "version": getattr(q, "version", ""),
                    "criteria": sorted(
                        (
                            {
                                "criterion_id": str(c.criterion_id),
                                "question": c.question,
                                "guidance": c.guidance,
                                "is_required": c.is_required,
                                "display_order": c.display_order,
                            }
                            for c in getattr(q, "criteria", [])
                        ),
                        key=lambda c: c["criterion_id"],
                    ),
                }
                for q in qa_configs
            ),
            key=lambda q: q["template_id"],
        )
    return sha256_hexdigest(_canonical_json_bytes(payload))


class SynthesisSnapshotContent(BaseModel):
    """Immutable assembled synthesis state captured by a snapshot.

    Stores the full analytical synthesis state (relations, mechanism pathways,
    context assignments, research gaps with links, term mappings, category
    taxonomies, and criterion-level QA profiles) so that an exported snapshot
    allows complete external reconstruction of the synthesis matrices.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    project_id: str = Field(min_length=1)
    relations: list[AnalyticalRelation] = Field(default_factory=list)
    mechanism_pathways: list[MechanismPathway] = Field(default_factory=list)
    context_assignments: list[ContextAssignment] = Field(default_factory=list)
    research_gaps: list[ResearchGap] = Field(default_factory=list)
    research_gap_links: list[ResearchGapLink] = Field(default_factory=list)
    term_mappings: list[TermMapping] = Field(default_factory=list)
    lean_categories: list[LeanPracticeCategory] = Field(default_factory=list)
    energy_categories: list[EnergyEffectCategory] = Field(default_factory=list)
    mechanism_categories: list[AnalyticalMechanismCategory] = Field(default_factory=list)
    context_categories: list[ContextCategory] = Field(default_factory=list)
    qa_profiles: list[QAProfileSummary] = Field(default_factory=list)


def compute_content_hash(content: SynthesisSnapshotContent) -> str:
    """Deterministic SHA-256 over canonicalized snapshot content.

    Lists are sorted by their canonical JSON representation so the content hash
    is insensitive to the ordering in which state was assembled.
    """
    payload = content.model_dump(mode="json")
    for key, value in payload.items():
        if isinstance(value, list):
            payload[key] = sorted(value, key=_canonical_json_bytes)
    return sha256_hexdigest(_canonical_json_bytes(payload))


class SynthesisSnapshot(BaseModel):
    """Immutable, reproducible synthesis snapshot artifact.

    Snapshots are append-only: a snapshot is never modified or deleted, and its
    ``content`` reflects the exact synthesis state at creation time (not a live
    pointer). Versioning is per-project, monotonic, and versions are never reused.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    snapshot_id: UUID = Field(default_factory=uuid4)
    project_id: str = Field(min_length=1)
    version: int = Field(ge=1)
    actor: str = Field(min_length=1)
    extraction_dataset_hash: str = Field(min_length=_DATASET_HASH_BYTES, max_length=_DATASET_HASH_BYTES)
    classification_version: str = Field(min_length=_DATASET_HASH_BYTES, max_length=_DATASET_HASH_BYTES)
    content_hash: str = Field(min_length=_DATASET_HASH_BYTES, max_length=_DATASET_HASH_BYTES)
    content: SynthesisSnapshotContent
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("created_at")
    @classmethod
    def validate_tz(cls, v: datetime) -> datetime:
        if v.tzinfo is None or v.utcoffset() is None:
            raise ValueError("created_at must be timezone-aware")
        return v
