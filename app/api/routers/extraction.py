"""API Router for Data Extraction Project Configuration & Eligibility (Phase 9.3)."""

from fastapi import APIRouter, HTTPException, Query, status

from app.api.dto.extraction import (
    ExtractionEligibilityListResponseDTO,
    ExtractionEligibilityResultDTO,
    ProjectExtractionConfigurationRequestDTO,
    ProjectExtractionConfigurationResponseDTO,
)
from app.domain.extraction import (
    ExtractionConfigurationLockedError,
)
from app.repositories.extraction_template_repository import (
    ExtractionTemplateNotFoundError,
)
from app.repositories.project_repository import (
    ProjectNotFoundError,
)
from app.services.extraction_configuration_service import (
    ExtractionConfigurationService,
    default_extraction_configuration_service,
)
from app.services.extraction_eligibility_service import (
    ExtractionEligibilityService,
    default_extraction_eligibility_service,
)

router = APIRouter(prefix="/api/v1/projects", tags=["extraction"])


def _get_config_service() -> ExtractionConfigurationService:
    return default_extraction_configuration_service()


def _get_eligibility_service() -> ExtractionEligibilityService:
    return default_extraction_eligibility_service()


@router.get(
    "/{project_id}/extraction/configuration",
    response_model=ProjectExtractionConfigurationResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Get project data extraction configuration",
)
def get_project_extraction_configuration(project_id: str) -> ProjectExtractionConfigurationResponseDTO:
    service = _get_config_service()
    config = service.get_configuration(project_id)
    if config is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project '{project_id}' has no extraction configuration.",
        )
    return ProjectExtractionConfigurationResponseDTO(
        project_id=config.project_id,
        template_id=config.template_id,
        template_version=config.template_version,
        configured_at=config.configured_at.isoformat(),
        updated_at=config.updated_at.isoformat(),
    )


@router.put(
    "/{project_id}/extraction/configuration",
    response_model=ProjectExtractionConfigurationResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Set or update project data extraction configuration",
)
def set_project_extraction_configuration(
    project_id: str, request: ProjectExtractionConfigurationRequestDTO
) -> ProjectExtractionConfigurationResponseDTO:
    service = _get_config_service()
    try:
        config = service.set_configuration(project_id, request.template_id, request.template_version)
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ExtractionTemplateNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ExtractionConfigurationLockedError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    return ProjectExtractionConfigurationResponseDTO(
        project_id=config.project_id,
        template_id=config.template_id,
        template_version=config.template_version,
        configured_at=config.configured_at.isoformat(),
        updated_at=config.updated_at.isoformat(),
    )


@router.get(
    "/{project_id}/extraction/eligibility",
    response_model=ExtractionEligibilityListResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Get publication eligibility list for data extraction",
)
def get_project_extraction_eligibility(
    project_id: str, reviewer_id: str = Query(default="", description="Optional reviewer ID filter for single-reviewer mode")
) -> ExtractionEligibilityListResponseDTO:
    service = _get_eligibility_service()
    results = service.get_eligible_publications(project_id, reviewer_id=reviewer_id)

    dtos = [
        ExtractionEligibilityResultDTO(
            publication_id=r.publication_id,
            status=r.status.value,
            is_eligible=r.is_eligible,
            reason_details=r.reason_details,
        )
        for r in results
    ]
    eligible_count = sum(1 for r in results if r.is_eligible)

    return ExtractionEligibilityListResponseDTO(
        project_id=project_id,
        total_publications=len(results),
        eligible_count=eligible_count,
        items=dtos,
    )
