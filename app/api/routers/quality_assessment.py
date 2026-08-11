from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dto.quality_assessment import (
    ProjectQualityAssessmentConfigurationRequest,
    ProjectQualityAssessmentConfigurationResponse,
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
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
