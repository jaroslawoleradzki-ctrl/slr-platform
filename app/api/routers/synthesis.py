"""API Router for Phase 10 Data Synthesis, Terminology Classification, and Analytical Matrix."""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Response, status

from app.api.dto.synthesis import (
    AnalyticalRelationDetailDTO,
    AnalyticalRelationDTO,
    ApproveMechanismPathwayRequestDTO,
    ApproveTermMappingRequestDTO,
    AssignMechanismCategoryRequestDTO,
    CategoryDTO,
    ClassificationWorkspaceStatsDTO,
    ClassifiedSourceTermDTO,
    ConvertedValueDTO,
    ConvertUnitRequestDTO,
    CreateCategoryRequestDTO,
    MatrixCellDetailDTO,
    MatrixCellDTO,
    MechanismPathwayDetailDTO,
    MechanismPathwayDTO,
    MechanismSynthesisPathwayDTO,
    MechanismWorkspaceDataDTO,
    MechanismWorkspaceStatsDTO,
    QACriterionAssessmentSummaryDTO,
    QAProfileSummaryDTO,
    SetTermMappingRequestDTO,
    SynthesisMatrixDTO,
    TerminologyClassificationWorkspaceDTO,
    TermMappingDTO,
    UpdateCategoryRequestDTO,
)
from app.domain.synthesis import (
    AnalyticalRelation,
    ConvertedValue,
    MechanismPathway,
    MechanismPathwayDetail,
    QAProfileSummary,
    TermType,
)
from app.repositories.project_repository import ProjectNotFoundError
from app.services.synthesis_classification_service import (
    CategoryConflictError,
    CategoryNotFoundError,
    MappingNotFoundError,
    SynthesisClassificationService,
    default_synthesis_classification_service,
)
from app.services.synthesis_matrix_service import (
    RelationNotFoundError,
    SynthesisMatrixService,
    UnitConversionError,
    default_synthesis_matrix_service,
)
from app.services.synthesis_mechanism_service import (
    MechanismAssignmentError,
    MechanismCategoryConflictError,
    MechanismCategoryNotFoundError,
    MechanismPathwayNotFoundError,
    SynthesisMechanismService,
    default_synthesis_mechanism_service,
)

router = APIRouter(prefix="/projects/{projectId}/synthesis", tags=["Synthesis"])


def _get_classification_service() -> SynthesisClassificationService:
    return default_synthesis_classification_service()


def _get_matrix_service() -> SynthesisMatrixService:
    return default_synthesis_matrix_service()


def _converted_value_to_dto(cv: ConvertedValue | None) -> ConvertedValueDTO | None:
    if cv is None:
        return None
    return ConvertedValueDTO(
        transformed_value=cv.transformed_value,
        transformed_unit=cv.transformed_unit,
        conversion_rule=cv.conversion_rule,
    )


def _category_to_dto(cat: Any) -> CategoryDTO:
    return CategoryDTO(
        category_id=cat.category_id,
        name=cat.name,
        project_id=getattr(cat, "project_id", ""),
        description=cat.description,
        display_order=cat.display_order,
    )


def _relation_to_dto(rel: AnalyticalRelation) -> AnalyticalRelationDTO:
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
        converted_value=_converted_value_to_dto(rel.converted_value),
        evidence_character=rel.evidence_character.value,
        context_summary=rel.context_summary,
        approval_state=rel.approval_state.value,
        created_at=rel.created_at,
        updated_at=rel.updated_at,
    )


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


# -------------------------------------------------------------------------
# Classification Workspace Endpoints
# -------------------------------------------------------------------------


@router.get("/classifications", response_model=TerminologyClassificationWorkspaceDTO)
def get_classifications_workspace(projectId: str):
    """Retrieves discovered source terms, categories, and analytical mappings."""
    service = _get_classification_service()
    try:
        data = service.get_workspace_classifications(projectId)
        return TerminologyClassificationWorkspaceDTO(
            project_id=data["project_id"],
            lean_categories=[
                CategoryDTO(
                    category_id=c.category_id,
                    name=c.name,
                    project_id=c.project_id,
                    description=c.description,
                    display_order=c.display_order,
                )
                for c in data["lean_categories"]
            ],
            energy_categories=[
                CategoryDTO(
                    category_id=c.category_id,
                    name=c.name,
                    project_id=c.project_id,
                    description=c.description,
                    display_order=c.display_order,
                )
                for c in data["energy_categories"]
            ],
            lean_terms=[
                ClassifiedSourceTermDTO(
                    project_id=t.project_id,
                    term_type=t.term_type.value,
                    source_value=t.source_value,
                    occurrence_count=t.occurrence_count,
                    publication_count=t.publication_count,
                    analytical_category_id=t.analytical_category_id,
                    analytical_category_name=t.analytical_category_name,
                    approval_state=t.approval_state.value,
                    approved_by=t.approved_by,
                    approved_at=t.approved_at,
                    mapping_id=t.mapping_id,
                )
                for t in data["lean_terms"]
            ],
            energy_terms=[
                ClassifiedSourceTermDTO(
                    project_id=t.project_id,
                    term_type=t.term_type.value,
                    source_value=t.source_value,
                    occurrence_count=t.occurrence_count,
                    publication_count=t.publication_count,
                    analytical_category_id=t.analytical_category_id,
                    analytical_category_name=t.analytical_category_name,
                    approval_state=t.approval_state.value,
                    approved_by=t.approved_by,
                    approved_at=t.approved_at,
                    mapping_id=t.mapping_id,
                )
                for t in data["energy_terms"]
            ],
            stats=ClassificationWorkspaceStatsDTO(
                total_lean_terms=data["stats"]["total_lean_terms"],
                total_energy_terms=data["stats"]["total_energy_terms"],
                total_terms=data["stats"]["total_terms"],
                mapped_count=data["stats"]["mapped_count"],
                approved_count=data["stats"]["approved_count"],
            ),
        )
    except ProjectNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e


@router.post("/categories/lean", response_model=CategoryDTO, status_code=status.HTTP_201_CREATED)
def create_lean_category(projectId: str, req: CreateCategoryRequestDTO):
    """Creates a new Lean analytical category."""
    service = _get_classification_service()
    try:
        created = service.create_lean_category(
            project_id=projectId,
            category_id=req.category_id,
            name=req.name,
            description=req.description,
            display_order=req.display_order,
        )
        return CategoryDTO(
            category_id=created.category_id,
            name=created.name,
            project_id=created.project_id,
            description=created.description,
            display_order=created.display_order,
        )
    except ProjectNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except (ValueError, CategoryConflictError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.put("/categories/lean/{categoryId}", response_model=CategoryDTO)
def update_lean_category(projectId: str, categoryId: str, req: UpdateCategoryRequestDTO):
    """Updates an existing Lean analytical category."""
    service = _get_classification_service()
    try:
        updated = service.update_lean_category(
            project_id=projectId,
            category_id=categoryId,
            name=req.name,
            description=req.description,
            display_order=req.display_order,
        )
        return CategoryDTO(
            category_id=updated.category_id,
            name=updated.name,
            project_id=updated.project_id,
            description=updated.description,
            display_order=updated.display_order,
        )
    except (ProjectNotFoundError, CategoryNotFoundError) as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.delete("/categories/lean/{categoryId}", status_code=status.HTTP_204_NO_CONTENT)
def delete_lean_category(projectId: str, categoryId: str):
    """Deletes a Lean analytical category."""
    service = _get_classification_service()
    try:
        service.delete_lean_category(projectId, categoryId)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except ProjectNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e


@router.post("/categories/energy", response_model=CategoryDTO, status_code=status.HTTP_201_CREATED)
def create_energy_category(projectId: str, req: CreateCategoryRequestDTO):
    """Creates a new Energy analytical category."""
    service = _get_classification_service()
    try:
        created = service.create_energy_category(
            project_id=projectId,
            category_id=req.category_id,
            name=req.name,
            description=req.description,
            display_order=req.display_order,
        )
        return CategoryDTO(
            category_id=created.category_id,
            name=created.name,
            project_id=created.project_id,
            description=created.description,
            display_order=created.display_order,
        )
    except ProjectNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except (ValueError, CategoryConflictError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.put("/categories/energy/{categoryId}", response_model=CategoryDTO)
def update_energy_category(projectId: str, categoryId: str, req: UpdateCategoryRequestDTO):
    """Updates an existing Energy analytical category."""
    service = _get_classification_service()
    try:
        updated = service.update_energy_category(
            project_id=projectId,
            category_id=categoryId,
            name=req.name,
            description=req.description,
            display_order=req.display_order,
        )
        return CategoryDTO(
            category_id=updated.category_id,
            name=updated.name,
            project_id=updated.project_id,
            description=updated.description,
            display_order=updated.display_order,
        )
    except (ProjectNotFoundError, CategoryNotFoundError) as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.delete("/categories/energy/{categoryId}", status_code=status.HTTP_204_NO_CONTENT)
def delete_energy_category(projectId: str, categoryId: str):
    """Deletes an Energy analytical category."""
    service = _get_classification_service()
    try:
        service.delete_energy_category(projectId, categoryId)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except ProjectNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e


@router.put("/classifications", response_model=TermMappingDTO)
def set_term_mapping(projectId: str, req: SetTermMappingRequestDTO):
    """Sets or updates an analytical category mapping for an empirical source term."""
    service = _get_classification_service()
    try:
        ttype = TermType(req.term_type)
        mapping = service.set_term_mapping(
            project_id=projectId,
            term_type=ttype,
            source_value=req.source_value,
            analytical_category_id=req.analytical_category_id,
        )
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
    except (ProjectNotFoundError, CategoryNotFoundError) as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.post("/classifications/approve", response_model=TermMappingDTO)
def approve_term_mapping(projectId: str, req: ApproveTermMappingRequestDTO):
    """Explicitly approves an analytical term mapping by a researcher."""
    service = _get_classification_service()
    try:
        ttype = TermType(req.term_type)
        approved = service.approve_term_mapping(
            project_id=projectId,
            term_type=ttype,
            source_value=req.source_value,
            reviewer_id=req.reviewer_id,
        )
        return TermMappingDTO(
            mapping_id=approved.mapping_id,
            project_id=approved.project_id,
            term_type=approved.term_type.value,
            source_value=approved.source_value,
            analytical_category_id=approved.analytical_category_id,
            approval_state=approved.approval_state.value,
            approved_by=approved.approved_by,
            approved_at=approved.approved_at,
        )
    except (ProjectNotFoundError, MappingNotFoundError) as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


# -------------------------------------------------------------------------
# Task 10.3: Lean–EE Analytical Matrix Endpoints
# -------------------------------------------------------------------------


@router.get("/matrix", response_model=SynthesisMatrixDTO)
def get_synthesis_matrix(projectId: str):
    """Retrieves the aggregated Lean Category × Energy Effect Category analytical matrix."""
    service = _get_matrix_service()
    try:
        matrix = service.get_matrix(projectId)
        return SynthesisMatrixDTO(
            project_id=matrix.project_id,
            lean_categories=[
                CategoryDTO(
                    category_id=c.category_id,
                    name=c.name,
                    project_id=c.project_id,
                    description=c.description,
                    display_order=c.display_order,
                )
                for c in matrix.lean_categories
            ],
            energy_categories=[
                CategoryDTO(
                    category_id=c.category_id,
                    name=c.name,
                    project_id=c.project_id,
                    description=c.description,
                    display_order=c.display_order,
                )
                for c in matrix.energy_categories
            ],
            cells=[
                MatrixCellDTO(
                    lean_category_id=cell.lean_category_id,
                    lean_category_name=cell.lean_category_name,
                    energy_category_id=cell.energy_category_id,
                    energy_category_name=cell.energy_category_name,
                    relation_count=cell.relation_count,
                    publication_count=cell.publication_count,
                    direction_distribution=cell.direction_distribution,
                    evidence_character_distribution=cell.evidence_character_distribution,
                )
                for cell in matrix.cells
            ],
            total_relations=matrix.total_relations,
            total_publications=matrix.total_publications,
            unclassified_relations_count=matrix.unclassified_relations_count,
        )
    except ProjectNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e


@router.get("/matrix/cell-detail", response_model=MatrixCellDetailDTO)
def get_matrix_cell_detail(
    projectId: str,
    leanCategoryId: str = Query(..., min_length=1),
    energyCategoryId: str = Query(..., min_length=1),
):
    """Retrieves detailed drill-down information and relations for a matrix cell."""
    service = _get_matrix_service()
    try:
        detail = service.get_matrix_cell_detail(
            project_id=projectId,
            lean_category_id=leanCategoryId,
            energy_category_id=energyCategoryId,
        )
        return MatrixCellDetailDTO(
            lean_category=CategoryDTO(
                category_id=detail.lean_category.category_id,
                name=detail.lean_category.name,
                project_id=detail.lean_category.project_id,
                description=detail.lean_category.description,
                display_order=detail.lean_category.display_order,
            ),
            energy_category=CategoryDTO(
                category_id=detail.energy_category.category_id,
                name=detail.energy_category.name,
                project_id=detail.energy_category.project_id,
                description=detail.energy_category.description,
                display_order=detail.energy_category.display_order,
            ),
            relation_count=detail.relation_count,
            publication_count=detail.publication_count,
            direction_distribution=detail.direction_distribution,
            evidence_character_distribution=detail.evidence_character_distribution,
            relations=[
                AnalyticalRelationDetailDTO(
                    relation=_relation_to_dto(r.relation),
                    publication_title=r.publication_title,
                    publication_year=r.publication_year,
                    source_quote=r.source_quote,
                    source_page=r.source_page,
                    source_section=r.source_section,
                    qa_profile=_qa_profile_to_dto(r.qa_profile),
                )
                for r in detail.relations
            ],
        )
    except (ProjectNotFoundError, CategoryNotFoundError) as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e


@router.post("/relations/{relationId}/convert-unit", response_model=ConvertedValueDTO)
def preview_unit_conversion(projectId: str, relationId: UUID, req: ConvertUnitRequestDTO):
    """Calculates preview physical unit conversion without saving."""
    service = _get_matrix_service()
    try:
        converted = service.calculate_unit_conversion(
            project_id=projectId,
            relation_id=relationId,
            target_unit=req.target_unit,
        )
        return ConvertedValueDTO(
            transformed_value=converted.transformed_value,
            transformed_unit=converted.transformed_unit,
            conversion_rule=converted.conversion_rule,
        )
    except (ProjectNotFoundError, RelationNotFoundError) as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except UnitConversionError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.post("/relations/{relationId}/save-converted-unit", response_model=AnalyticalRelationDTO)
def save_converted_unit(projectId: str, relationId: UUID, req: ConvertUnitRequestDTO):
    """Explicitly calculates and saves researcher-approved unit conversion."""
    service = _get_matrix_service()
    try:
        updated_relation = service.save_converted_value(
            project_id=projectId,
            relation_id=relationId,
            target_unit=req.target_unit,
        )
        return _relation_to_dto(updated_relation)
    except (ProjectNotFoundError, RelationNotFoundError) as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except UnitConversionError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


# =========================================================
# Task 10.4: Mechanism Synthesis & Impact Pathways
# =========================================================


def _get_mechanism_service() -> SynthesisMechanismService:
    return default_synthesis_mechanism_service()


def _mechanism_pathway_to_dto(p: MechanismPathway) -> MechanismPathwayDTO:
    return MechanismPathwayDTO(
        pathway_id=p.pathway_id,
        project_id=p.project_id,
        analytical_relation_id=p.analytical_relation_id,
        group_item_id=p.group_item_id,
        publication_id=p.publication_id,
        latest_revision_id=p.latest_revision_id,
        source_mechanism_text=p.source_mechanism_text,
        analytical_mechanism_category_id=p.analytical_mechanism_category_id,
        is_review_synthesized=p.is_review_synthesized,
        approval_state=p.approval_state.value,
        approved_by=p.approved_by,
        approved_at=p.approved_at,
        notes=p.notes,
        created_at=p.created_at,
        updated_at=p.updated_at,
    )


def _mechanism_pathway_detail_to_dto(d: MechanismPathwayDetail) -> MechanismPathwayDetailDTO:
    return MechanismPathwayDetailDTO(
        pathway=_mechanism_pathway_to_dto(d.pathway),
        publication_title=d.publication_title,
        publication_year=d.publication_year,
        source_practice=d.source_practice,
        source_effect=d.source_effect,
        analytical_lean_category_id=d.analytical_lean_category_id,
        analytical_lean_category_name=d.analytical_lean_category_name,
        analytical_energy_category_id=d.analytical_energy_category_id,
        analytical_energy_category_name=d.analytical_energy_category_name,
        analytical_mechanism_category_name=d.analytical_mechanism_category_name,
        direction=d.direction.value,
        evidence_character=d.evidence_character.value,
        qa_profile=_qa_profile_to_dto(d.qa_profile),
    )


@router.get("/mechanisms", response_model=MechanismWorkspaceDataDTO)
def get_mechanism_workspace(projectId: str):
    """Retrieves complete dataset for the Mechanism Synthesis Workspace."""
    service = _get_mechanism_service()
    try:
        data = service.get_mechanism_workspace_data(project_id=projectId)
        return MechanismWorkspaceDataDTO(
            project_id=data.project_id,
            categories=[_category_to_dto(c) for c in data.categories],
            pathways=[_mechanism_pathway_detail_to_dto(p) for p in data.pathways],
            synthesis_chains=[
                MechanismSynthesisPathwayDTO(
                    lean_category_id=c.lean_category_id,
                    lean_category_name=c.lean_category_name,
                    mechanism_category_id=c.mechanism_category_id,
                    mechanism_category_name=c.mechanism_category_name,
                    energy_category_id=c.energy_category_id,
                    energy_category_name=c.energy_category_name,
                    pathway_count=c.pathway_count,
                    publication_count=c.publication_count,
                    relation_count=c.relation_count,
                    pathways=[_mechanism_pathway_detail_to_dto(p) for p in c.pathways],
                )
                for c in data.synthesis_chains
            ],
            stats=MechanismWorkspaceStatsDTO(
                total_pathways=data.stats.total_pathways,
                mapped_count=data.stats.mapped_count,
                unmapped_count=data.stats.unmapped_count,
                approved_count=data.stats.approved_count,
                total_publications=data.stats.total_publications,
            ),
        )
    except ProjectNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e


@router.get("/mechanisms/categories", response_model=list[CategoryDTO])
def list_mechanism_categories(projectId: str):
    """Lists all analytical mechanism taxonomy categories for a project."""
    service = _get_mechanism_service()
    try:
        categories = service.list_categories(project_id=projectId)
        return [_category_to_dto(c) for c in categories]
    except ProjectNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e


@router.post("/mechanisms/categories", response_model=CategoryDTO, status_code=status.HTTP_201_CREATED)
def create_mechanism_category(projectId: str, req: CreateCategoryRequestDTO):
    """Creates a new analytical mechanism taxonomy category."""
    service = _get_mechanism_service()
    try:
        category = service.create_category(
            project_id=projectId,
            category_id=req.category_id,
            name=req.name,
            description=req.description,
            display_order=req.display_order,
        )
        return _category_to_dto(category)
    except ProjectNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except MechanismCategoryConflictError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)) from e


@router.put("/mechanisms/categories/{categoryId}", response_model=CategoryDTO)
def update_mechanism_category(projectId: str, categoryId: str, req: UpdateCategoryRequestDTO):
    """Updates an existing analytical mechanism taxonomy category."""
    service = _get_mechanism_service()
    try:
        category = service.update_category(
            project_id=projectId,
            category_id=categoryId,
            name=req.name,
            description=req.description,
            display_order=req.display_order,
        )
        return _category_to_dto(category)
    except (ProjectNotFoundError, MechanismCategoryNotFoundError) as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)) from e


@router.delete("/mechanisms/categories/{categoryId}", status_code=status.HTTP_204_NO_CONTENT)
def delete_mechanism_category(projectId: str, categoryId: str):
    """Deletes an analytical mechanism taxonomy category, unclassifying linked pathways."""
    service = _get_mechanism_service()
    try:
        deleted = service.delete_category(project_id=projectId, category_id=categoryId)
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Mechanism category '{categoryId}' not found",
            )
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except ProjectNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e


@router.post("/mechanisms/pathways/{pathwayId}/assign", response_model=MechanismPathwayDTO)
def assign_mechanism_pathway(projectId: str, pathwayId: UUID, req: AssignMechanismCategoryRequestDTO):
    """Assigns an analytical mechanism category and synthesis notes to a pathway."""
    service = _get_mechanism_service()
    try:
        pathway = service.assign_mechanism_category(
            project_id=projectId,
            pathway_id=pathwayId,
            category_id=req.category_id,
            is_review_synthesized=req.is_review_synthesized,
            notes=req.notes,
        )
        return _mechanism_pathway_to_dto(pathway)
    except (ProjectNotFoundError, MechanismPathwayNotFoundError, MechanismCategoryNotFoundError) as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e


@router.post("/mechanisms/pathways/{pathwayId}/approve", response_model=MechanismPathwayDTO)
def approve_mechanism_pathway(projectId: str, pathwayId: UUID, req: ApproveMechanismPathwayRequestDTO):
    """Explicitly approves a mechanism pathway classification."""
    service = _get_mechanism_service()
    try:
        pathway = service.approve_mechanism_pathway(
            project_id=projectId,
            pathway_id=pathwayId,
            reviewer_id=req.reviewer_id,
        )
        return _mechanism_pathway_to_dto(pathway)
    except (ProjectNotFoundError, MechanismPathwayNotFoundError) as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except (MechanismAssignmentError, ValueError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.get("/mechanisms/synthesis", response_model=list[MechanismSynthesisPathwayDTO])
def get_mechanism_synthesis(projectId: str):
    """Retrieves aggregated mechanism synthesis chains: Lean -> Mechanism -> Energy."""
    service = _get_mechanism_service()
    try:
        data = service.get_mechanism_workspace_data(project_id=projectId)
        return [
            MechanismSynthesisPathwayDTO(
                lean_category_id=c.lean_category_id,
                lean_category_name=c.lean_category_name,
                mechanism_category_id=c.mechanism_category_id,
                mechanism_category_name=c.mechanism_category_name,
                energy_category_id=c.energy_category_id,
                energy_category_name=c.energy_category_name,
                pathway_count=c.pathway_count,
                publication_count=c.publication_count,
                relation_count=c.relation_count,
                pathways=[_mechanism_pathway_detail_to_dto(p) for p in c.pathways],
            )
            for c in data.synthesis_chains
        ]
    except ProjectNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
