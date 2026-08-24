from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.dto.quality_assessment import (
    ProjectQualityAssessmentConfigurationRequest,
    ProjectQualityAssessmentConfigurationResponse,
    QualityAssessmentDto,
    QualityAssessmentOverviewResponse,
    QualityAssessmentRecordDetailResponse,
    QualityAssessmentRecordListResponse,
    SaveQualityAssessmentRequest,
    TemplateResponse,
    ToolResponse,
)
from app.repositories.project_repository import ProjectNotFoundError
from app.services.quality_assessment_configuration_service import (
    CrossToolTemplateMismatchError,
    InactiveTemplateSelectionError,
    InactiveToolSelectionError,
    QualityAssessmentConfigurationService,
    TemplateVersionNotFoundError,
    ToolNotFoundError,
    default_quality_assessment_configuration_service,
)
from app.services.quality_assessment_execution_service import (
    CriterionResponseInput,
    MissingRequiredQualityCriterionResponseError,
    NoQualityAssessmentConfigurationError,
    PublicationNotEligibleForQualityAssessmentError,
    PublicationNotFoundError,
    QualityAssessmentExecutionService,
    QualityAssessmentStatusFilter,
    default_quality_assessment_execution_service,
)

router = APIRouter(tags=["Quality Assessment"])


def get_config_service() -> QualityAssessmentConfigurationService:
    service = default_quality_assessment_configuration_service()
    service.seed_built_in_catalog()
    return service


@router.get(
    "/quality-assessment/tools",
    response_model=list[ToolResponse],
    status_code=status.HTTP_200_OK,
)
def list_quality_assessment_tools(
    service: Annotated[
        QualityAssessmentConfigurationService, Depends(get_config_service)
    ],
) -> list[ToolResponse]:
    """Retrieve global list of active Quality Assessment tools."""
    tools = service.list_tools(is_active_only=True)
    return [ToolResponse.from_domain(t) for t in tools]


@router.get(
    "/quality-assessment/tools/{tool_id}/templates",
    response_model=list[TemplateResponse],
    status_code=status.HTTP_200_OK,
)
def list_quality_assessment_templates_for_tool(
    tool_id: str,
    service: Annotated[
        QualityAssessmentConfigurationService, Depends(get_config_service)
    ],
) -> list[TemplateResponse]:
    """Retrieve active template versions for a specific Quality Assessment tool."""
    try:
        templates = service.list_templates_for_tool(tool_id, is_active_only=True)
        return [TemplateResponse.from_domain(tmpl) for tmpl in templates]
    except ToolNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.get(
    "/projects/{project_id}/quality-assessment/configuration",
    response_model=ProjectQualityAssessmentConfigurationResponse,
    status_code=status.HTTP_200_OK,
)
def get_project_quality_assessment_configuration(
    project_id: str,
    service: Annotated[
        QualityAssessmentConfigurationService, Depends(get_config_service)
    ],
) -> ProjectQualityAssessmentConfigurationResponse:
    """Retrieve active Quality Assessment configuration for a project."""
    try:
        config = service.get_project_configuration(project_id)
        if config is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project '{project_id}' has no active Quality Assessment configuration.",
            )
        return ProjectQualityAssessmentConfigurationResponse.from_domain(config)
    except ProjectNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.put(
    "/projects/{project_id}/quality-assessment/configuration",
    response_model=ProjectQualityAssessmentConfigurationResponse,
    status_code=status.HTTP_200_OK,
)
def configure_project_quality_assessment(
    project_id: str,
    payload: ProjectQualityAssessmentConfigurationRequest,
    service: Annotated[
        QualityAssessmentConfigurationService, Depends(get_config_service)
    ],
) -> ProjectQualityAssessmentConfigurationResponse:
    """Set or update active Quality Assessment tool and template version for a project."""
    try:
        config = service.configure_project(
            project_id=project_id,
            tool_id=payload.tool_id,
            template_id=payload.template_id,
            confirm_template_change=payload.confirm_template_change,
        )
        return ProjectQualityAssessmentConfigurationResponse.from_domain(config)
    except ProjectNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except (ToolNotFoundError, TemplateVersionNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except (
        InactiveToolSelectionError,
        InactiveTemplateSelectionError,
        CrossToolTemplateMismatchError,
        ValueError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc


def get_execution_service() -> QualityAssessmentExecutionService:
    return default_quality_assessment_execution_service()


@router.get(
    "/projects/{project_id}/quality-assessment/overview",
    response_model=QualityAssessmentOverviewResponse,
    status_code=status.HTTP_200_OK,
)
def get_quality_assessment_overview(
    project_id: str,
    reviewer_id: str,
    service: Annotated[
        QualityAssessmentExecutionService, Depends(get_execution_service)
    ],
) -> QualityAssessmentOverviewResponse:
    """Retrieve Quality Assessment progress and readiness overview for a project and reviewer."""
    try:
        overview = service.get_overview(project_id=project_id, reviewer_id=reviewer_id)
        return QualityAssessmentOverviewResponse.from_domain(overview)
    except ProjectNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.get(
    "/projects/{project_id}/quality-assessment/records",
    response_model=QualityAssessmentRecordListResponse,
    status_code=status.HTTP_200_OK,
)
def list_quality_assessment_eligible_records(
    project_id: str,
    reviewer_id: str = Query(..., min_length=1),
    service: Annotated[
        QualityAssessmentExecutionService, Depends(get_execution_service)
    ] = None,  # type: ignore[assignment]
    filter_status: QualityAssessmentStatusFilter | None = Query(default=None, alias="status"),
    status_filter: QualityAssessmentStatusFilter | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> QualityAssessmentRecordListResponse:
    """List eligible publications for Quality Assessment with current assessment state."""
    if filter_status is not None and status_filter is not None:
        if filter_status != status_filter:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Conflicting query parameters provided: status='{filter_status.value}' and status_filter='{status_filter.value}'",
            )
        effective_filter = filter_status
    elif filter_status is not None:
        effective_filter = filter_status
    elif status_filter is not None:
        effective_filter = status_filter
    else:
        effective_filter = QualityAssessmentStatusFilter.ALL

    try:
        record_list = service.list_eligible_records(
            project_id=project_id,
            reviewer_id=reviewer_id,
            status_filter=effective_filter,
            page=page,
            page_size=page_size,
        )
        return QualityAssessmentRecordListResponse.from_domain(record_list)
    except ProjectNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.get(
    "/projects/{project_id}/quality-assessment/records/{publication_id}",
    response_model=QualityAssessmentRecordDetailResponse,
    status_code=status.HTTP_200_OK,
)
def get_quality_assessment_record_detail(
    project_id: str,
    publication_id: UUID,
    reviewer_id: str,
    service: Annotated[
        QualityAssessmentExecutionService, Depends(get_execution_service)
    ],
) -> QualityAssessmentRecordDetailResponse:
    """Retrieve detailed Quality Assessment view for a specific publication."""
    try:
        detail = service.get_record_detail(
            project_id=project_id,
            publication_id=publication_id,
            reviewer_id=reviewer_id,
        )
        return QualityAssessmentRecordDetailResponse.from_domain(detail)
    except (ProjectNotFoundError, PublicationNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except NoQualityAssessmentConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc


@router.post(
    "/projects/{project_id}/quality-assessment/assessments",
    response_model=QualityAssessmentDto,
    status_code=status.HTTP_201_CREATED,
)
def save_quality_assessment(
    project_id: str,
    payload: SaveQualityAssessmentRequest,
    service: Annotated[
        QualityAssessmentExecutionService, Depends(get_execution_service)
    ],
) -> QualityAssessmentDto:
    """Save an append-only Quality Assessment record for an eligible publication."""
    try:
        response_inputs = [
            CriterionResponseInput(
                criterion_id=r.criterion_id,
                response_value=r.response_value,
                justification=r.justification,
            )
            for r in payload.responses
        ]
        qa = service.save_assessment(
            project_id=project_id,
            publication_id=payload.publication_id,
            reviewer_id=payload.reviewer_id,
            response_inputs=response_inputs,
        )
        return QualityAssessmentDto.from_domain(qa)
    except ProjectNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except (
        PublicationNotEligibleForQualityAssessmentError,
        NoQualityAssessmentConfigurationError,
        MissingRequiredQualityCriterionResponseError,
        ValueError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc


@router.get(
    "/projects/{project_id}/quality-assessment/records/{publication_id}/history",
    response_model=list[QualityAssessmentDto],
    status_code=status.HTTP_200_OK,
)
def get_quality_assessment_history(
    project_id: str,
    publication_id: UUID,
    reviewer_id: str,
    service: Annotated[
        QualityAssessmentExecutionService, Depends(get_execution_service)
    ],
) -> list[QualityAssessmentDto]:
    """Retrieve full append-only assessment history for a publication and reviewer."""
    try:
        history = service.get_assessment_history(
            project_id=project_id,
            publication_id=publication_id,
            reviewer_id=reviewer_id,
        )
        return [QualityAssessmentDto.from_domain(qa) for qa in history]
    except ProjectNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
