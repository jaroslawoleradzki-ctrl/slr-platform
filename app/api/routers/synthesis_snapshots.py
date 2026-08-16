"""API Router for Phase 10: Synthesis Snapshots (Task 10.7).

Endpoints:
- POST /projects/{projectId}/synthesis/snapshots   -> create immutable snapshot
- GET  /projects/{projectId}/synthesis/snapshots   -> list snapshots (version ASC)
- GET  /projects/{projectId}/synthesis/snapshots/{version}/export?format=json|csv
"""

from typing import Any

from fastapi import APIRouter, HTTPException, status

from app.api.dto.synthesis import (
    AnalyticalRelationDTO,
    CategoryDTO,
    ContextAssignmentDTO,
    ContextCategoryDTO,
    CreateSnapshotRequestDTO,
    MechanismPathwayDTO,
    QACriterionAssessmentSummaryDTO,
    QAProfileSummaryDTO,
    ResearchGapDTO,
    ResearchGapLinkDTO,
    SnapshotExportDTO,
    SynthesisSnapshotContentDTO,
    SynthesisSnapshotDetailDTO,
    SynthesisSnapshotDTO,
    TermMappingDTO,
)
from app.domain.synthesis import (
    AnalyticalRelation,
    ContextAssignment,
    ContextCategory,
    MechanismPathway,
    QAProfileSummary,
    ResearchGap,
    ResearchGapLink,
    SynthesisSnapshot,
    SynthesisSnapshotContent,
    TermMapping,
)
from app.repositories.project_repository import ProjectNotFoundError
from app.services.synthesis_snapshot_service import (
    SnapshotExportError,
    SnapshotNotFoundError,
    SynthesisSnapshotService,
    default_synthesis_snapshot_service,
)

router = APIRouter(prefix="/projects/{projectId}/synthesis", tags=["Synthesis Snapshots"])


def _get_snapshot_service() -> SynthesisSnapshotService:
    return default_synthesis_snapshot_service()


# -------------------------------------------------------------------------
# Content converters (domain -> DTO)
# -------------------------------------------------------------------------


def _qa_profile_to_dto(qa: QAProfileSummary | None) -> QAProfileSummaryDTO | None:
    if qa is None:
        return None
    return QAProfileSummaryDTO(
        assessment_id=qa.assessment_id,
        template_id=qa.template_id,
        reviewer_id=qa.reviewer_id,
        criteria_assessments=[
            QACriterionAssessmentSummaryDTO(
                criterion_id=c.criterion_id,
                question_text=c.question_text,
                response_value=c.response_value,
                justification=c.justification,
            )
            for c in qa.criteria_assessments
        ],
    )


def _relation_to_dto(rel: AnalyticalRelation) -> AnalyticalRelationDTO:
    converted = None
    if rel.converted_value is not None:
        from app.api.dto.synthesis import ConvertedValueDTO

        converted = ConvertedValueDTO(
            transformed_value=rel.converted_value.transformed_value,
            transformed_unit=rel.converted_value.transformed_unit,
            conversion_rule=rel.converted_value.conversion_rule,
        )
    return AnalyticalRelationDTO(
        relation_id=rel.relation_id,
        project_id=rel.project_id,
        publication_id=rel.publication_id,
        latest_revision_id=rel.latest_revision_id,
        group_item_id=rel.group_item_id,
        item_index=rel.item_index,
        source_practice=rel.source_practice,
        analytical_lean_category_id=rel.analytical_lean_category_id,
        source_effect=rel.source_effect,
        analytical_energy_category_id=rel.analytical_energy_category_id,
        direction=rel.direction.value,
        magnitude=rel.magnitude,
        original_unit=rel.original_unit,
        converted_value=converted,
        evidence_character=rel.evidence_character.value,
        context_summary=rel.context_summary,
        approval_state=rel.approval_state.value,
        created_at=rel.created_at,
        updated_at=rel.updated_at,
    )


def _pathway_to_dto(pathway: MechanismPathway) -> MechanismPathwayDTO:
    return MechanismPathwayDTO(
        pathway_id=pathway.pathway_id,
        project_id=pathway.project_id,
        analytical_relation_id=pathway.analytical_relation_id,
        group_item_id=pathway.group_item_id,
        publication_id=pathway.publication_id,
        latest_revision_id=pathway.latest_revision_id,
        source_mechanism_text=pathway.source_mechanism_text,
        analytical_mechanism_category_id=pathway.analytical_mechanism_category_id,
        is_review_synthesized=pathway.is_review_synthesized,
        approval_state=pathway.approval_state.value,
        approved_by=pathway.approved_by,
        approved_at=pathway.approved_at,
        notes=pathway.notes,
        created_at=pathway.created_at,
        updated_at=pathway.updated_at,
    )


def _context_assignment_to_dto(assignment: ContextAssignment) -> ContextAssignmentDTO:
    return ContextAssignmentDTO(
        assignment_id=assignment.assignment_id,
        project_id=assignment.project_id,
        analytical_relation_id=assignment.analytical_relation_id,
        group_item_id=assignment.group_item_id,
        publication_id=assignment.publication_id,
        latest_revision_id=assignment.latest_revision_id,
        source_context_text=assignment.source_context_text,
        analytical_context_category_id=assignment.analytical_context_category_id,
        context_impact=assignment.context_impact,
        approval_state=assignment.approval_state.value,
        approved_by=assignment.approved_by,
        approved_at=assignment.approved_at,
        created_at=assignment.created_at,
        updated_at=assignment.updated_at,
    )


def _gap_to_dto(gap: ResearchGap) -> ResearchGapDTO:
    return ResearchGapDTO(
        gap_id=gap.gap_id,
        project_id=gap.project_id,
        gap_type=gap.gap_type.value,
        title=gap.title,
        rationale=gap.rationale,
        researcher_id=gap.researcher_id,
        created_at=gap.created_at,
        updated_at=gap.updated_at,
    )


def _link_to_dto(link: ResearchGapLink) -> ResearchGapLinkDTO:
    return ResearchGapLinkDTO(
        link_id=link.link_id,
        project_id=link.project_id,
        gap_id=link.gap_id,
        link_type=link.link_type.value,
        target_id=link.target_id,
        group_item_id=link.group_item_id,
        publication_id=link.publication_id,
        latest_revision_id=link.latest_revision_id,
        created_at=link.created_at,
    )


def _term_mapping_to_dto(mapping: TermMapping) -> TermMappingDTO:
    return TermMappingDTO(
        mapping_id=mapping.mapping_id,
        project_id=mapping.project_id,
        term_type=mapping.term_type.value,
        source_value=mapping.source_value,
        analytical_category_id=mapping.analytical_category_id,
        approval_state=mapping.approval_state.value,
        approved_by=mapping.approved_by,
        approved_at=mapping.approved_at,
    )


def _category_to_dto(category: Any) -> CategoryDTO:
    return CategoryDTO(
        category_id=category.category_id,
        name=category.name,
        project_id=category.project_id,
        description=category.description,
        display_order=category.display_order,
    )


def _context_category_to_dto(category: ContextCategory) -> ContextCategoryDTO:
    return ContextCategoryDTO(
        category_id=category.category_id,
        name=category.name,
        project_id=category.project_id,
        description=category.description,
        display_order=category.display_order,
    )


def _content_to_dto(content: SynthesisSnapshotContent) -> SynthesisSnapshotContentDTO:
    return SynthesisSnapshotContentDTO(
        project_id=content.project_id,
        relations=[_relation_to_dto(r) for r in content.relations],
        mechanism_pathways=[_pathway_to_dto(p) for p in content.mechanism_pathways],
        context_assignments=[_context_assignment_to_dto(a) for a in content.context_assignments],
        research_gaps=[_gap_to_dto(g) for g in content.research_gaps],
        research_gap_links=[_link_to_dto(link) for link in content.research_gap_links],
        term_mappings=[_term_mapping_to_dto(m) for m in content.term_mappings],
        lean_categories=[_category_to_dto(c) for c in content.lean_categories],
        energy_categories=[_category_to_dto(c) for c in content.energy_categories],
        mechanism_categories=[_category_to_dto(c) for c in content.mechanism_categories],
        context_categories=[_context_category_to_dto(c) for c in content.context_categories],
        qa_profiles=[p for q in content.qa_profiles if (p := _qa_profile_to_dto(q)) is not None],
    )


def _snapshot_to_list_dto(snapshot: SynthesisSnapshot) -> SynthesisSnapshotDTO:
    return SynthesisSnapshotDTO(
        snapshot_id=snapshot.snapshot_id,
        project_id=snapshot.project_id,
        version=snapshot.version,
        actor=snapshot.actor,
        extraction_dataset_hash=snapshot.extraction_dataset_hash,
        classification_version=snapshot.classification_version,
        content_hash=snapshot.content_hash,
        created_at=snapshot.created_at,
    )


def _snapshot_to_detail_dto(snapshot: SynthesisSnapshot) -> SynthesisSnapshotDetailDTO:
    return SynthesisSnapshotDetailDTO(
        snapshot_id=snapshot.snapshot_id,
        project_id=snapshot.project_id,
        version=snapshot.version,
        actor=snapshot.actor,
        extraction_dataset_hash=snapshot.extraction_dataset_hash,
        classification_version=snapshot.classification_version,
        content_hash=snapshot.content_hash,
        created_at=snapshot.created_at,
        content=_content_to_dto(snapshot.content),
    )


def _snapshot_to_export_dto(snapshot: SynthesisSnapshot, exported: dict[str, Any]) -> SnapshotExportDTO:
    return SnapshotExportDTO(
        snapshot_id=snapshot.snapshot_id,
        project_id=snapshot.project_id,
        version=snapshot.version,
        actor=snapshot.actor,
        created_at=snapshot.created_at,
        format=exported["format"],
        extraction_dataset_hash=snapshot.extraction_dataset_hash,
        classification_version=snapshot.classification_version,
        content_hash=snapshot.content_hash,
        content=_content_to_dto(snapshot.content) if exported.get("content") is not None else None,
        content_csv=exported.get("content_csv"),
    )


# -------------------------------------------------------------------------
# Endpoints
# -------------------------------------------------------------------------


@router.post("/snapshots", response_model=SynthesisSnapshotDetailDTO, status_code=status.HTTP_201_CREATED)
def create_snapshot(projectId: str, req: CreateSnapshotRequestDTO):
    """Explicitly creates a new immutable snapshot of the synthesis state."""
    service = _get_snapshot_service()
    try:
        snapshot = service.create_snapshot(project_id=projectId, actor=req.actor)
        return _snapshot_to_detail_dto(snapshot)
    except ProjectNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.get("/snapshots", response_model=list[SynthesisSnapshotDTO])
def list_snapshots(projectId: str):
    """Lists synthesis snapshots for a project ordered by version ascending."""
    service = _get_snapshot_service()
    try:
        snapshots = service.list_snapshots(project_id=projectId)
        return [_snapshot_to_list_dto(s) for s in snapshots]
    except ProjectNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e


@router.get("/snapshots/{version}", response_model=SynthesisSnapshotDetailDTO)
def get_snapshot(projectId: str, version: int):
    """Retrieves a single synthesis snapshot with its frozen content."""
    service = _get_snapshot_service()
    try:
        snapshot = service.get_snapshot_by_version(project_id=projectId, version=version)
        return _snapshot_to_detail_dto(snapshot)
    except ProjectNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except SnapshotNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e


@router.get("/snapshots/{version}/export", response_model=SnapshotExportDTO)
def export_snapshot(projectId: str, version: int, format: str = "json"):
    """Exports a snapshot as JSON (full) or CSV (relations matrix)."""
    service = _get_snapshot_service()
    try:
        exported = service.export_snapshot(project_id=projectId, version=version, fmt=format)
        snapshot = service.get_snapshot_by_version(project_id=projectId, version=version)
        return _snapshot_to_export_dto(snapshot, exported)
    except ProjectNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except SnapshotNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except SnapshotExportError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
