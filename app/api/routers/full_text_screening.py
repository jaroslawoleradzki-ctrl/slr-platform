from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.dto.full_text_screening import (
    FullTextAvailabilityRequest,
    FullTextAvailabilityResponse,
    FullTextDecisionRequest,
    FullTextOverviewResponse,
    FullTextScreeningListResponse,
    FullTextScreeningRecordResponse,
)
from app.api.dto.screening import ScreeningDecisionResponse
from app.repositories.project_publication_repository import ProjectNotFoundError
from app.services.full_text_screening_service import (
    FullTextPublicationNotEligibleError,
    FullTextScreeningService,
    FullTextScreeningStatus,
    FullTextWorkflowNotReadyError,
)
from app.services.screening_decision_service import CriterionAssessmentInput

router = APIRouter(prefix="/projects", tags=["screening"])


def get_full_text_screening_service() -> FullTextScreeningService:
    return FullTextScreeningService()


def _workflow_error(exc: Exception) -> HTTPException:
    if isinstance(exc, ProjectNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, FullTextWorkflowNotReadyError):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "full_text_not_ready", "readiness_status": exc.readiness_status.value},
        )
    if isinstance(exc, FullTextPublicationNotEligibleError):
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Publication is not currently eligible for Full Text screening.",
        )
    if isinstance(exc, ValueError):
        return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc))
    return HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Unable to process the Full Text screening workflow.")


@router.get("/{project_id}/screening/full-text", response_model=FullTextOverviewResponse)
def get_full_text_overview(
    project_id: str, reviewer_id: str = Query(..., min_length=1),
    service: FullTextScreeningService = Depends(get_full_text_screening_service),
) -> FullTextOverviewResponse:
    try:
        return FullTextOverviewResponse.from_read_model(service.get_overview(project_id, reviewer_id))
    except Exception as exc:
        raise _workflow_error(exc) from exc


@router.get("/{project_id}/screening/full-text/records", response_model=FullTextScreeningListResponse)
def list_full_text_records(
    project_id: str, reviewer_id: str = Query(..., min_length=1),
    screening_status: FullTextScreeningStatus | None = Query(default=None, alias="status"),
    offset: int = Query(default=0, ge=0), limit: int = Query(default=50, ge=1, le=100),
    service: FullTextScreeningService = Depends(get_full_text_screening_service),
) -> FullTextScreeningListResponse:
    try:
        return FullTextScreeningListResponse.from_read_model(
            service.list_records(project_id, reviewer_id, status_filter=screening_status, offset=offset, limit=limit)
        )
    except Exception as exc:
        raise _workflow_error(exc) from exc


@router.get("/{project_id}/screening/full-text/records/{publication_id}", response_model=FullTextScreeningRecordResponse)
def get_full_text_record(
    project_id: str, publication_id: UUID, reviewer_id: str = Query(..., min_length=1),
    service: FullTextScreeningService = Depends(get_full_text_screening_service),
) -> FullTextScreeningRecordResponse:
    try:
        return FullTextScreeningRecordResponse.from_read_model(service.get_record(project_id, publication_id, reviewer_id))
    except Exception as exc:
        raise _workflow_error(exc) from exc


@router.put("/{project_id}/screening/full-text/records/{publication_id}/availability", response_model=FullTextAvailabilityResponse)
def save_full_text_availability(
    project_id: str, publication_id: UUID, payload: FullTextAvailabilityRequest,
    service: FullTextScreeningService = Depends(get_full_text_screening_service),
) -> FullTextAvailabilityResponse:
    try:
        availability = service.save_availability(project_id, publication_id, payload.reviewer_id, payload.status, payload.external_url, payload.notes)
        return FullTextAvailabilityResponse.from_domain(availability)
    except Exception as exc:
        raise _workflow_error(exc) from exc


@router.post("/{project_id}/screening/full-text/decisions", response_model=ScreeningDecisionResponse, status_code=status.HTTP_201_CREATED)
def record_full_text_decision(
    project_id: str, payload: FullTextDecisionRequest,
    service: FullTextScreeningService = Depends(get_full_text_screening_service),
) -> ScreeningDecisionResponse:
    try:
        decision = service.record_decision(
            project_id, payload.publication_id, payload.reviewer_id, payload.outcome, payload.rationale,
            [CriterionAssessmentInput(criterion_id=item.criterion_id, assessment_value=item.assessment_value, notes=item.notes) for item in payload.criterion_assessments],
            payload.exclusion_reason_criterion_ids,
        )
        return ScreeningDecisionResponse.from_domain(decision)
    except Exception as exc:
        raise _workflow_error(exc) from exc
