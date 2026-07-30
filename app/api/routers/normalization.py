from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dto.normalization import NormalizationResponse
from app.api.routers.search_strategy import (
    get_normalization_execution_repository,
    get_project_publication_repository,
)
from app.repositories.project_publication_repository import (
    ProjectNotFoundError,
    ProjectPublicationRepository,
)
from app.repositories.normalization_execution_repository import NormalizationExecutionRepository
from app.services.normalization_service import NormalizationExecution, normalize_project

router = APIRouter(prefix="/projects", tags=["normalization"])


def _response(execution: NormalizationExecution) -> NormalizationResponse:
    return NormalizationResponse(
        run_id=execution.run_id,
        project_id=execution.project_id,
        status=execution.status,
        processed_records=execution.processed_records,
        clean_records=execution.clean_records,
        warnings_count=execution.warnings_count,
        errors_count=execution.errors_count,
        rules_applied=list(execution.rules_applied),
        audit_trail=list(execution.audit_trail),
        started_at=execution.started_at,
        completed_at=execution.completed_at,
        executed_at=execution.executed_at,
        error_message=execution.error_message,
    )


@router.post(
    "/{project_id}/normalization",
    response_model=NormalizationResponse,
    status_code=status.HTTP_200_OK,
)
def run_normalization(
    project_id: str,
    repository: ProjectPublicationRepository = Depends(get_project_publication_repository),
    execution_repository: NormalizationExecutionRepository = Depends(
        get_normalization_execution_repository
    ),
) -> NormalizationResponse:
    try:
        execution = normalize_project(repository, project_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    execution_repository.save(execution)
    return _response(execution)


@router.get(
    "/{project_id}/normalization",
    response_model=NormalizationResponse,
    status_code=status.HTTP_200_OK,
)
def get_normalization(
    project_id: str,
    repository: ProjectPublicationRepository = Depends(get_project_publication_repository),
    execution_repository: NormalizationExecutionRepository = Depends(
        get_normalization_execution_repository
    ),
) -> NormalizationResponse:
    try:
        repository.get_publications(project_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    execution = execution_repository.get_for_project(project_id)
    if execution is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Normalization not run")
    return _response(execution)
