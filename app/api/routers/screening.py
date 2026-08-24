from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.dto.conflict_resolution import (
    ConflictResolutionHistoryResponse,
    ConflictResolutionRequest,
    ConflictResolutionResponse,
)
from app.api.dto.multi_reviewer_screening import (
    ReviewerAssignmentResponse,
    ReviewerRosterRequest,
    ScreeningConflictMetricsResponse,
    ScreeningConflictPageResponse,
    ScreeningConflictResponse,
)
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
from app.api.dto.screening_reporting import (
    ExclusionReasonAggregationResponse,
    MultiReviewerStageMetricsResponse,
    ProjectOutcomeSummaryResponse,
    ScreeningAuditEventResponse,
    ScreeningAuditPageResponse,
    ScreeningAuditResolutionEventResponse,
    ScreeningReportResponse,
    ScreeningTransitionResponse,
    StageProgressResponse,
)
from app.domain.screening import ScreeningCriterion, ScreeningOutcome, ScreeningStage
from app.repositories.project_publication_repository import ProjectNotFoundError
from app.repositories.screening_criterion_repository import (
    CriterionNotFoundError,
    ScreeningCriterionRepository,
    default_screening_criterion_repository,
)
from app.repositories.screening_decision_repository import (
    DecisionNotFoundError,
)
from app.services.conflict_resolution_service import (
    ConflictResolutionPublicationNotFoundError,
    ConflictResolutionService,
    ConflictResolutionStaleError,
)
from app.services.multi_reviewer_screening_service import (
    MultiReviewerScreeningService,
    ScreeningConflictStatus,
)
from app.services.screening_decision_service import (
    CriterionAssessmentInput,
    ScreeningDecisionService,
)
from app.services.screening_reporting_service import AuditResolutionEvent, ScreeningReportingService
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


def get_screening_reporting_service() -> ScreeningReportingService:
    return ScreeningReportingService()


def get_multi_reviewer_screening_service() -> MultiReviewerScreeningService:
    return MultiReviewerScreeningService()


def get_conflict_resolution_service() -> ConflictResolutionService:
    return ConflictResolutionService()


@router.get("/{project_id}/screening/reviewers", response_model=list[ReviewerAssignmentResponse])
def list_screening_reviewers(
    project_id: str,
    stage: ScreeningStage = Query(...),
    service: MultiReviewerScreeningService = Depends(get_multi_reviewer_screening_service),
):
    return [ReviewerAssignmentResponse.from_domain(item) for item in service.roster(project_id, stage)]


@router.put("/{project_id}/screening/reviewers", response_model=list[ReviewerAssignmentResponse])
def replace_screening_reviewers(
    project_id: str,
    payload: ReviewerRosterRequest,
    stage: ScreeningStage = Query(...),
    service: MultiReviewerScreeningService = Depends(get_multi_reviewer_screening_service),
):
    try:
        return [
            ReviewerAssignmentResponse.from_domain(item)
            for item in service.roster(project_id, stage, payload.reviewer_ids)
        ]
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc


@router.get("/{project_id}/screening/conflicts", response_model=ScreeningConflictPageResponse)
def list_screening_conflicts(
    project_id: str,
    stage: ScreeningStage = Query(...),
    conflict_status: ScreeningConflictStatus | None = Query(None, alias="status"),
    viewer_reviewer_id: str | None = Query(None),
    adjudication: bool = Query(False),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    service: MultiReviewerScreeningService = Depends(get_multi_reviewer_screening_service),
):
    try:
        items, total = service.conflicts(
            project_id,
            stage,
            status=conflict_status,
            viewer_reviewer_id=viewer_reviewer_id.strip() if viewer_reviewer_id else None,
            reveal_decisions=adjudication,
            offset=offset,
            limit=limit,
        )
        return ScreeningConflictPageResponse(
            total=total,
            offset=offset,
            limit=limit,
            items=[ScreeningConflictResponse.from_domain(item) for item in items],
        )
    except Exception as exc:
        raise _workflow_error(exc) from exc


@router.get("/{project_id}/screening/conflict-metrics", response_model=ScreeningConflictMetricsResponse)
def get_screening_conflict_metrics(
    project_id: str,
    stage: ScreeningStage = Query(...),
    service: MultiReviewerScreeningService = Depends(get_multi_reviewer_screening_service),
):
    try:
        metrics = service.metrics(project_id, stage)
        return ScreeningConflictMetricsResponse(
            incomplete=metrics.incomplete,
            agreement=metrics.agreement,
            conflict=metrics.conflict,
            resolved=metrics.resolved,
            stale_resolution=metrics.stale_resolution,
            agreement_rate=metrics.agreement_rate,
            resolution_rate=metrics.resolution_rate,
        )
    except Exception as exc:
        raise _workflow_error(exc) from exc


@router.post(
    "/{project_id}/screening/conflict-resolutions",
    response_model=ConflictResolutionResponse,
    status_code=status.HTTP_201_CREATED,
)
def record_conflict_resolution(
    project_id: str,
    payload: ConflictResolutionRequest,
    service: ConflictResolutionService = Depends(get_conflict_resolution_service),
):
    try:
        return ConflictResolutionResponse.from_domain(
            service.resolve(
                project_id,
                payload.publication_id,
                payload.stage,
                payload.resolved_outcome,
                payload.resolver_id,
                payload.rationale,
                payload.expected_decision_set_key,
            ),
            is_current=True,
        )
    except ConflictResolutionStaleError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "decision_set_changed",
                "detail": str(exc),
                "expected_key": exc.expected_key,
                "current_key": exc.current_key,
            },
        ) from exc
    except ConflictResolutionPublicationNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except Exception as exc:
        raise _workflow_error(exc) from exc


@router.get(
    "/{project_id}/screening/conflict-resolutions/{publication_id}/history",
    response_model=ConflictResolutionHistoryResponse,
)
def conflict_resolution_history(
    project_id: str,
    publication_id: UUID,
    stage: ScreeningStage = Query(...),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    service: ConflictResolutionService = Depends(get_conflict_resolution_service),
):
    try:
        key, values = service.history(project_id, publication_id, stage)
        links = service.history_links([item.resolution_id for item in values])
        page = values[offset : offset + limit]
        return ConflictResolutionHistoryResponse(
            publication_id=publication_id,
            stage=stage,
            current_decision_set_key=key,
            total=len(values),
            offset=offset,
            limit=limit,
            resolutions=[
                ConflictResolutionResponse.from_domain(
                    item,
                    is_current=item.decision_set_key == key,
                    reviewer_outcomes=links.get(item.resolution_id, ()),
                )
                for item in page
            ],
        )
    except ConflictResolutionPublicationNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except Exception as exc:
        raise _workflow_error(exc) from exc


@router.get("/{project_id}/screening/report", response_model=ScreeningReportResponse)
def get_screening_report(
    project_id: str,
    reviewer_id: str = Query(..., min_length=1),
    service: ScreeningReportingService = Depends(get_screening_reporting_service),
    multi_reviewer_service: MultiReviewerScreeningService = Depends(get_multi_reviewer_screening_service),
) -> ScreeningReportResponse:
    try:
        input_set, title_abstract, full_text, transitions, reasons = service.report(project_id, reviewer_id)
        title_metrics = multi_reviewer_service.metrics(project_id, ScreeningStage.TITLE_ABSTRACT)
        full_text_metrics = multi_reviewer_service.metrics(project_id, ScreeningStage.FULL_TEXT)

        def project_summary(stage: ScreeningStage) -> ProjectOutcomeSummaryResponse:
            records, _ = multi_reviewer_service.conflicts(project_id, stage, limit=100000)
            values = {"include": 0, "exclude": 0, "uncertain": 0, "pending": 0}
            for record in records:
                if record.status is ScreeningConflictStatus.AGREEMENT:
                    values[record.source_decisions[0].outcome.value] += 1
                elif record.status is ScreeningConflictStatus.RESOLVED and record.resolution:
                    values[record.resolution.resolved_outcome.value] += 1
                else:
                    values["pending"] += 1
            return ProjectOutcomeSummaryResponse(stage=stage.value, total=len(records), **values)

        return ScreeningReportResponse(
            project_id=project_id,
            reviewer_id=reviewer_id.strip(),
            ready=input_set.ready,
            readiness_status=input_set.readiness_status.value,
            working_collection_count=input_set.working_collection_count,
            canonical_records_count=input_set.canonical_records_count,
            title_abstract=StageProgressResponse.from_domain(title_abstract) if title_abstract else None,
            full_text=StageProgressResponse.from_domain(full_text) if full_text else None,
            transitions=ScreeningTransitionResponse.from_domain(transitions) if transitions else None,
            full_text_exclusion_reasons=[ExclusionReasonAggregationResponse.from_domain(item) for item in reasons],
            title_abstract_multi_reviewer=MultiReviewerStageMetricsResponse(
                incomplete=title_metrics.incomplete,
                agreement=title_metrics.agreement,
                conflict=title_metrics.conflict,
                resolved=title_metrics.resolved,
                stale_resolution=title_metrics.stale_resolution,
                agreement_rate=title_metrics.agreement_rate,
                resolution_rate=title_metrics.resolution_rate,
            )
            if input_set.ready
            else None,
            full_text_multi_reviewer=MultiReviewerStageMetricsResponse(
                incomplete=full_text_metrics.incomplete,
                agreement=full_text_metrics.agreement,
                conflict=full_text_metrics.conflict,
                resolved=full_text_metrics.resolved,
                stale_resolution=full_text_metrics.stale_resolution,
                agreement_rate=full_text_metrics.agreement_rate,
                resolution_rate=full_text_metrics.resolution_rate,
            )
            if input_set.ready
            else None,
            title_abstract_project_outcomes=project_summary(ScreeningStage.TITLE_ABSTRACT) if input_set.ready else None,
            full_text_project_outcomes=project_summary(ScreeningStage.FULL_TEXT) if input_set.ready else None,
        )
    except Exception as exc:
        raise _workflow_error(exc) from exc


@router.get("/{project_id}/screening/audit", response_model=ScreeningAuditPageResponse)
def get_screening_audit(
    project_id: str,
    reviewer_id: str | None = Query(None),
    publication_id: UUID | None = Query(None),
    stage: ScreeningStage | None = Query(None),
    outcome: ScreeningOutcome | None = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    service: ScreeningReportingService = Depends(get_screening_reporting_service),
) -> ScreeningAuditPageResponse:
    try:
        items, total = service.audit(
            project_id,
            reviewer_id=reviewer_id.strip() if reviewer_id else None,
            publication_id=publication_id,
            stage=stage,
            outcome=outcome,
            offset=offset,
            limit=limit,
        )
        return ScreeningAuditPageResponse(
            total=total,
            offset=offset,
            limit=limit,
            items=[
                ScreeningAuditResolutionEventResponse.from_domain(item)
                if isinstance(item, AuditResolutionEvent)
                else ScreeningAuditEventResponse.from_domain(item)
                for item in items
            ],
        )
    except Exception as exc:
        raise _workflow_error(exc) from exc


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
        return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc))
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
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
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
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
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
    if payload.stage in (ScreeningStage.TITLE_ABSTRACT, ScreeningStage.FULL_TEXT):
        workflow = "title-abstract" if payload.stage is ScreeningStage.TITLE_ABSTRACT else "full-text"
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": f"{workflow.replace('-', '_')}_workflow_required",
                "dedicated_endpoint": f"/projects/{project_id}/screening/{workflow}/decisions",
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
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
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
