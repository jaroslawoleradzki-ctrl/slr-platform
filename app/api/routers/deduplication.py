from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dto.deduplication import DuplicateGroupListResponse
from app.repositories.project_publication_repository import ProjectNotFoundError
from app.services.project_duplicate_service import (
    ProjectDuplicateService,
    project_duplicate_service,
)

router = APIRouter(prefix="/projects", tags=["deduplication"])


def get_duplicate_service() -> ProjectDuplicateService:
    return project_duplicate_service


@router.get(
    "/{project_id}/duplicate-groups",
    response_model=DuplicateGroupListResponse,
    status_code=status.HTTP_200_OK,
    summary="Get candidate duplicate groups for human review",
    description=(
        "Returns read-only candidate duplicate groups detected by strong canonical identifiers "
        "(DOI, PMID, OpenAlex ID). Does not modify records or write domain decisions."
    ),
)
def get_project_duplicate_groups(
    project_id: str,
    service: ProjectDuplicateService = Depends(get_duplicate_service),
) -> DuplicateGroupListResponse:
    try:
        return service.get_candidate_duplicate_groups(project_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project '{project_id}' not found.",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving duplicate groups: {str(exc)}",
        ) from exc
