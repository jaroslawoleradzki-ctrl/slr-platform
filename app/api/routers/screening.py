from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.dto.screening import (
    ScreeningCriterionCreateRequest,
    ScreeningCriterionListResponse,
    ScreeningCriterionResponse,
    ScreeningCriterionUpdateRequest,
    ScreeningDecisionCreateRequest,
    ScreeningDecisionListResponse,
    ScreeningDecisionResponse,
    TitleAbstractDecisionRequest,
    TitleAbstractScreeningListResponse,
    TitleAbstractScreeningOverviewResponse,
    TitleAbstractScreeningRecordResponse,
)
from app.domain.screening import ScreeningCriterion, ScreeningStage
from app.repositories.project_publication_repository import ProjectNotFoundError
from app.repositories.screening_criterion_repository import (
    CriterionNotFoundError,
    ScreeningCriterionRepository,
    default_screening_criterion_repository,
)
from app.repositories.screening_decision_repository import (
    DecisionNotFoundError,
)
from app.services.screening_decision_service import (
    CriterionAssessmentInput,
    ScreeningDecisionService,
)
from app.services.title_abstract_screening_service import (
    ScreeningPublicationNotEligibleError,
    ScreeningWorkflowNotReadyError,
    TitleAbstractScreeningService,
    TitleAbstractScreeningStatus,
)

router = APIRouter(prefix="/projects", tags=["screening"])


def get_screening_repository() -> ScreeningCriterionRepository:
    return default_screening_criterion_repository()


def get_screening_decision_service() -> ScreeningDecisionService:
    return ScreeningDecisionService()


def get_title_abstract_screening_service() -> TitleAbstractScreeningService:
    return TitleAbstractScreeningService()


def _workflow_error(exc: Exception) -> HTTPException:
    if isinstance(exc, ProjectNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, ScreeningWorkflowNotReadyError):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "screening_input_not_ready",
                "readiness_status": exc.readiness_status.value,
            },
        )
    if isinstance(exc, ScreeningPublicationNotEligibleError):
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Publication is not in the canonical screening input set.",
        )
    if isinstance(exc, ValueError):
        return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Unable to process the title and abstract screening workflow.",
    )


@router.get(
    "/{project_id}/screening/title-abstract",
    response_model=TitleAbstractScreeningOverviewResponse,
)
def get_title_abstract_overview(
    project_id: str,
    reviewer_id: str = Query(..., min_length=1),
    service: TitleAbstractScreeningService = Depends(get_title_abstract_screening_service),
) -> TitleAbstractScreeningOverviewResponse:
    try:
        return TitleAbstractScreeningOverviewResponse.from_read_model(service.get_overview(project_id, reviewer_id))
    except Exception as exc:
        raise _workflow_error(exc) from exc


@router.get(
    "/{project_id}/screening/title-abstract/records",
    response_model=TitleAbstractScreeningListResponse,
)
def list_title_abstract_records(
    project_id: str,
    reviewer_id: str = Query(..., min_length=1),
    screening_status: TitleAbstractScreeningStatus | None = Query(default=None, alias="status"),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    service: TitleAbstractScreeningService = Depends(get_title_abstract_screening_service),
) -> TitleAbstractScreeningListResponse:
    try:
        return TitleAbstractScreeningListResponse.from_read_model(
            service.list_records(
                project_id,
                reviewer_id,
                status_filter=screening_status,
                offset=offset,
                limit=limit,
            )
        )
    except Exception as exc:
        raise _workflow_error(exc) from exc


@router.get(
    "/{project_id}/screening/title-abstract/records/{publication_id}",
    response_model=TitleAbstractScreeningRecordResponse,
)
def get_title_abstract_record(
    project_id: str,
    publication_id: UUID,
    reviewer_id: str = Query(..., min_length=1),
    service: TitleAbstractScreeningService = Depends(get_title_abstract_screening_service),
) -> TitleAbstractScreeningRecordResponse:
    try:
        return TitleAbstractScreeningRecordResponse.from_read_model(
            service.get_record(project_id, publication_id, reviewer_id)
        )
    except Exception as exc:
        raise _workflow_error(exc) from exc


@router.post(
    "/{project_id}/screening/title-abstract/decisions",
    response_model=ScreeningDecisionResponse,
    status_code=status.HTTP_201_CREATED,
)
def record_title_abstract_decision(
    project_id: str,
    payload: TitleAbstractDecisionRequest,
    service: TitleAbstractScreeningService = Depends(get_title_abstract_screening_service),
) -> ScreeningDecisionResponse:
    try:
        decision = service.record_decision(
            project_id,
            payload.publication_id,
            payload.reviewer_id,
            payload.outcome,
            payload.rationale,
            [
                CriterionAssessmentInput(
                    criterion_id=item.criterion_id,
                    assessment_value=item.assessment_value,
                    notes=item.notes,
                )
                for item in payload.criterion_assessments
            ],
        )
        return ScreeningDecisionResponse.from_domain(decision)
    except Exception as exc:
        raise _workflow_error(exc) from exc


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
            evaluation_mode=payload.evaluation_mode,
            metadata_rule=payload.metadata_rule,
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
            evaluation_mode=payload.evaluation_mode,
            metadata_rule=payload.metadata_rule,
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


# --- Screening Decision REST Endpoints ---


@router.post(
    "/{project_id}/screening/decisions",
    response_model=ScreeningDecisionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Record a screening decision for a publication",
    description="Records a new append-only screening decision for a publication, validating publication existence, active criteria, stage compatibility, and required assessments.",
)
def record_screening_decision(
    project_id: str,
    payload: ScreeningDecisionCreateRequest,
    service: ScreeningDecisionService = Depends(get_screening_decision_service),
) -> ScreeningDecisionResponse:
    if payload.stage is ScreeningStage.TITLE_ABSTRACT:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "title_abstract_workflow_required",
                "dedicated_endpoint": f"/projects/{project_id}/screening/title-abstract/decisions",
            },
        )
    try:
        assessment_inputs = [
            CriterionAssessmentInput(
                criterion_id=a.criterion_id,
                assessment_value=a.assessment_value,
                notes=a.notes,
            )
            for a in payload.criterion_assessments
        ]

        saved = service.record_decision(
            project_id=project_id,
            publication_id=payload.publication_id,
            stage=payload.stage,
            outcome=payload.outcome,
            reviewer_id=payload.reviewer_id,
            rationale=payload.rationale,
            assessment_inputs=assessment_inputs,
        )
        return ScreeningDecisionResponse.from_domain(saved)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error recording screening decision: {str(exc)}",
        ) from exc


@router.get(
    "/{project_id}/screening/decisions/latest",
    response_model=ScreeningDecisionResponse,
    status_code=status.HTTP_200_OK,
    summary="Get the latest screening decision for a publication, stage, and reviewer",
    description="Retrieves the most recent decision record for a publication, stage, and reviewer tuple.",
)
def get_latest_screening_decision(
    project_id: str,
    publication_id: UUID = Query(..., description="Publication identifier."),
    stage: ScreeningStage = Query(..., description="Screening stage."),
    reviewer_id: str = Query(..., description="Reviewer identifier."),
    service: ScreeningDecisionService = Depends(get_screening_decision_service),
) -> ScreeningDecisionResponse:
    try:
        decision = service.get_latest_decision(
            project_id=project_id,
            publication_id=publication_id,
            stage=stage,
            reviewer_id=reviewer_id,
        )
        if decision is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No decision found for publication '{publication_id}' on stage '{stage.value}' by reviewer '{reviewer_id}'.",
            )
        return ScreeningDecisionResponse.from_domain(decision)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving latest decision: {str(exc)}",
        ) from exc


@router.get(
    "/{project_id}/screening/decisions/history",
    response_model=ScreeningDecisionListResponse,
    status_code=status.HTTP_200_OK,
    summary="List screening decision history for a publication and stage",
    description="Returns full append-only decision history for a publication and stage.",
)
def list_screening_decision_history(
    project_id: str,
    publication_id: UUID = Query(..., description="Publication identifier."),
    stage: ScreeningStage = Query(..., description="Screening stage."),
    reviewer_id: str | None = Query(default=None, description="Optional reviewer filter."),
    service: ScreeningDecisionService = Depends(get_screening_decision_service),
) -> ScreeningDecisionListResponse:
    try:
        history = service.list_history(
            project_id=project_id,
            publication_id=publication_id,
            stage=stage,
            reviewer_id=reviewer_id,
        )
        items = [ScreeningDecisionResponse.from_domain(d) for d in history]
        return ScreeningDecisionListResponse(items=items, total=len(items))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error listing decision history: {str(exc)}",
        ) from exc


@router.get(
    "/{project_id}/screening/decisions/{decision_id}",
    response_model=ScreeningDecisionResponse,
    status_code=status.HTTP_200_OK,
    summary="Get a specific screening decision by ID",
    description="Retrieves a specific screening decision record by project_id and decision_id.",
)
def get_screening_decision(
    project_id: str,
    decision_id: UUID,
    service: ScreeningDecisionService = Depends(get_screening_decision_service),
) -> ScreeningDecisionResponse:
    try:
        decision = service.get_decision(project_id, decision_id)
        return ScreeningDecisionResponse.from_domain(decision)
    except DecisionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving screening decision: {str(exc)}",
        ) from exc
