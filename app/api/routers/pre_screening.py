from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.dto.pre_screening import (
    ImportedRecordResponse,
    ImportedRecordsPageResponse,
    PreScreeningRemovalRequest,
    PreScreeningRestoreRequest,
)
from app.repositories.project_publication_repository import ProjectNotFoundError
from app.services.pre_screening_review_service import (
    PreScreeningRecordNotFoundError,
    PreScreeningReviewService,
    default_pre_screening_review_service,
)

router = APIRouter(prefix="/projects", tags=["pre-screening"])


def get_pre_screening_review_service() -> PreScreeningReviewService:
    return default_pre_screening_review_service()


@router.get(
    "/{project_id}/imports/{import_id}/records",
    response_model=ImportedRecordsPageResponse,
    status_code=status.HTTP_200_OK,
)
def list_imported_records(
    project_id: str,
    import_id: UUID,
    search: str | None = Query(default=None),
    status_filter: str | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=500),
    service: PreScreeningReviewService = Depends(get_pre_screening_review_service),
) -> ImportedRecordsPageResponse:
    """List imported records for an import/retrieval execution with search and status filtering."""
    try:
        return service.list_imported_records(
            project_id=project_id,
            import_id=import_id,
            search=search,
            status_filter=status_filter,
            offset=offset,
            limit=limit,
        )
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc


@router.post(
    "/{project_id}/imports/{import_id}/records/{record_id}/remove",
    response_model=ImportedRecordResponse,
    status_code=status.HTTP_200_OK,
)
def remove_imported_record(
    project_id: str,
    import_id: UUID,
    record_id: UUID,
    payload: PreScreeningRemovalRequest,
    service: PreScreeningReviewService = Depends(get_pre_screening_review_service),
) -> ImportedRecordResponse:
    """Manually remove an imported record before formal screening corpus freeze."""
    try:
        return service.remove_record(
            project_id=project_id,
            import_id=import_id,
            record_id=record_id,
            reason=payload.reason,
            notes=payload.notes,
            reviewer_id=payload.reviewer_id,
        )
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except PreScreeningRecordNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc


@router.post(
    "/{project_id}/imports/{import_id}/records/{record_id}/restore",
    response_model=ImportedRecordResponse,
    status_code=status.HTTP_200_OK,
)
def restore_imported_record(
    project_id: str,
    import_id: UUID,
    record_id: UUID,
    payload: PreScreeningRestoreRequest,
    service: PreScreeningReviewService = Depends(get_pre_screening_review_service),
) -> ImportedRecordResponse:
    """Restore (undo) a previously removed imported record back to the retained corpus."""
    try:
        return service.restore_record(
            project_id=project_id,
            import_id=import_id,
            record_id=record_id,
            reviewer_id=payload.reviewer_id,
        )
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except PreScreeningRecordNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
