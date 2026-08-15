"""API Router for Phase 10 Data Synthesis and Terminology Classification."""

from fastapi import APIRouter, HTTPException, Response, status

from app.api.dto.synthesis import (
    ApproveTermMappingRequestDTO,
    CategoryDTO,
    ClassificationWorkspaceStatsDTO,
    ClassifiedSourceTermDTO,
    CreateCategoryRequestDTO,
    SetTermMappingRequestDTO,
    TerminologyClassificationWorkspaceDTO,
    TermMappingDTO,
    UpdateCategoryRequestDTO,
)
from app.domain.synthesis import TermType
from app.repositories.project_repository import ProjectNotFoundError
from app.services.synthesis_classification_service import (
    CategoryConflictError,
    CategoryNotFoundError,
    MappingNotFoundError,
    SynthesisClassificationService,
    default_synthesis_classification_service,
)

router = APIRouter(prefix="/projects/{projectId}/synthesis", tags=["Synthesis"])


def _get_service() -> SynthesisClassificationService:
    return default_synthesis_classification_service()


@router.get("/classifications", response_model=TerminologyClassificationWorkspaceDTO)
def get_classifications_workspace(projectId: str):
    """Retrieves discovered source terms, categories, and analytical mappings."""
    service = _get_service()
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
    service = _get_service()
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
    service = _get_service()
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
    service = _get_service()
    try:
        service.delete_lean_category(projectId, categoryId)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except ProjectNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e


@router.post("/categories/energy", response_model=CategoryDTO, status_code=status.HTTP_201_CREATED)
def create_energy_category(projectId: str, req: CreateCategoryRequestDTO):
    """Creates a new Energy analytical category."""
    service = _get_service()
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
    service = _get_service()
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
    service = _get_service()
    try:
        service.delete_energy_category(projectId, categoryId)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except ProjectNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e


@router.put("/classifications", response_model=TermMappingDTO)
def set_term_mapping(projectId: str, req: SetTermMappingRequestDTO):
    """Sets or updates an analytical category mapping for an empirical source term."""
    service = _get_service()
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
    service = _get_service()
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
