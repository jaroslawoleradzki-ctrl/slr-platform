"""API Router for Phase 10 Data Synthesis, Terminology Classification, and Analytical Matrix."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Response, status

from app.api.dto.synthesis import (
    AnalyticalRelationDetailDTO,
    AnalyticalRelationDTO,
    ApproveTermMappingRequestDTO,
    CategoryDTO,
    ClassificationWorkspaceStatsDTO,
    ClassifiedSourceTermDTO,
    ConvertedValueDTO,
    ConvertUnitRequestDTO,
    CreateCategoryRequestDTO,
    MatrixCellDetailDTO,
    MatrixCellDTO,
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
