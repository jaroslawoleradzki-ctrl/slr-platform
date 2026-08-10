from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dto.screening import (
    ScreeningCriterionCreateRequest,
    ScreeningCriterionListResponse,
    ScreeningCriterionResponse,
    ScreeningCriterionUpdateRequest,
)
from app.domain.screening import ScreeningCriterion
from app.repositories.screening_criterion_repository import (
    CriterionNotFoundError,
    ScreeningCriterionRepository,
    default_screening_criterion_repository,
)

router = APIRouter(prefix="/projects", tags=["screening"])


def get_screening_repository() -> ScreeningCriterionRepository:
    return default_screening_criterion_repository()


@router.post(
    "/{project_id}/screening/criteria",
    response_model=ScreeningCriterionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new screening criterion for a project",
    description="Creates and persists a new configurable screening criterion scoped to the specified project.",
)
def create_screening_criterion(
    project_id: str,
    payload: ScreeningCriterionCreateRequest,
    repo: ScreeningCriterionRepository = Depends(get_screening_repository),
) -> ScreeningCriterionResponse:
    try:
        criterion = ScreeningCriterion(
            project_id=project_id,
            name=payload.name,
            description=payload.description,
            criterion_type=payload.criterion_type,
            screening_stage=payload.screening_stage,
            display_order=payload.display_order,
            is_active=payload.is_active,
            is_required=payload.is_required,
        )
        saved = repo.create(criterion)
        return ScreeningCriterionResponse.from_domain(saved)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating screening criterion: {str(exc)}",
        ) from exc


@router.get(
    "/{project_id}/screening/criteria",
    response_model=ScreeningCriterionListResponse,
    status_code=status.HTTP_200_OK,
    summary="List all screening criteria for a project",
    description="Returns all screening criteria for a project in deterministic display order.",
)
def list_screening_criteria(
    project_id: str,
    active_only: bool = False,
    repo: ScreeningCriterionRepository = Depends(get_screening_repository),
) -> ScreeningCriterionListResponse:
    try:
        criteria = repo.list_by_project(project_id, active_only=active_only)
        items = [ScreeningCriterionResponse.from_domain(c) for c in criteria]
        return ScreeningCriterionListResponse(items=items, total=len(items))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error listing screening criteria: {str(exc)}",
        ) from exc


@router.get(
    "/{project_id}/screening/criteria/{criterion_id}",
    response_model=ScreeningCriterionResponse,
    status_code=status.HTTP_200_OK,
    summary="Get a specific screening criterion",
    description="Retrieves a specific screening criterion by project_id and criterion_id.",
)
def get_screening_criterion(
    project_id: str,
    criterion_id: UUID,
    repo: ScreeningCriterionRepository = Depends(get_screening_repository),
) -> ScreeningCriterionResponse:
    try:
        criterion = repo.get(project_id, criterion_id)
        return ScreeningCriterionResponse.from_domain(criterion)
    except CriterionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving screening criterion: {str(exc)}",
        ) from exc


@router.put(
    "/{project_id}/screening/criteria/{criterion_id}",
    response_model=ScreeningCriterionResponse,
    status_code=status.HTTP_200_OK,
    summary="Update an existing screening criterion",
    description="Updates editable domain attributes of a screening criterion without changing identity or project ownership.",
)
def update_screening_criterion(
    project_id: str,
    criterion_id: UUID,
    payload: ScreeningCriterionUpdateRequest,
    repo: ScreeningCriterionRepository = Depends(get_screening_repository),
) -> ScreeningCriterionResponse:
    try:
        # Verify existence and project ownership first
        repo.get(project_id, criterion_id)

        updated_domain = ScreeningCriterion(
            criterion_id=criterion_id,
            project_id=project_id,
            name=payload.name,
            description=payload.description,
            criterion_type=payload.criterion_type,
            screening_stage=payload.screening_stage,
            display_order=payload.display_order,
            is_active=payload.is_active,
            is_required=payload.is_required,
        )
        saved = repo.update(updated_domain)
        return ScreeningCriterionResponse.from_domain(saved)
    except CriterionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating screening criterion: {str(exc)}",
        ) from exc


@router.patch(
    "/{project_id}/screening/criteria/{criterion_id}/deactivate",
    response_model=ScreeningCriterionResponse,
    status_code=status.HTTP_200_OK,
    summary="Deactivate a screening criterion",
    description="Deactivates a screening criterion (is_active=False), preserving historical decision references.",
)
def deactivate_screening_criterion(
    project_id: str,
    criterion_id: UUID,
    repo: ScreeningCriterionRepository = Depends(get_screening_repository),
) -> ScreeningCriterionResponse:
    try:
        deactivated = repo.deactivate(project_id, criterion_id)
        return ScreeningCriterionResponse.from_domain(deactivated)
    except CriterionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deactivating screening criterion: {str(exc)}",
        ) from exc
