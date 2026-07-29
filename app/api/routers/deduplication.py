from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dto.deduplication import (
    DuplicateGroupDecisionRequest,
    DuplicateGroupDecisionResponse,
    DuplicateGroupListResponse,
)
from app.repositories.duplicate_review_decision_repository import GroupNotFoundError
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
        "Returns candidate duplicate groups detected by strong canonical identifiers "
        "(DOI, PMID, OpenAlex ID) along with their current review decision statuses."
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


@router.post(
    "/{project_id}/duplicate-groups/{group_id}/decision",
    response_model=DuplicateGroupDecisionResponse,
    status_code=status.HTTP_200_OK,
    summary="Record reviewer decision for a candidate duplicate group",
    description=(
        "Records or overwrites a human review decision (APPROVE or REJECT) for a candidate duplicate group. "
        "Decisions are maintained in runtime memory and do not modify underlying publication records or trigger merges."
    ),
)
def record_duplicate_group_decision(
    project_id: str,
    group_id: str,
    payload: DuplicateGroupDecisionRequest,
    service: ProjectDuplicateService = Depends(get_duplicate_service),
) -> DuplicateGroupDecisionResponse:
    try:
        return service.record_decision(
            project_id=project_id,
            group_id=group_id,
            decision=payload.decision.value,
            rationale=payload.rationale,
        )
    except ProjectNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project '{project_id}' not found.",
        ) from exc
    except GroupNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Duplicate group '{group_id}' not found in project '{project_id}'.",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error recording decision: {str(exc)}",
        ) from exc


@router.get(
    "/{project_id}/duplicate-groups/{group_id}/decision",
    response_model=DuplicateGroupDecisionResponse,
    status_code=status.HTTP_200_OK,
    summary="Get recorded decision for a candidate duplicate group",
    description="Returns the recorded decision status (APPROVE, REJECT, or PENDING) for a duplicate group.",
)
def get_duplicate_group_decision(
    project_id: str,
    group_id: str,
    service: ProjectDuplicateService = Depends(get_duplicate_service),
) -> DuplicateGroupDecisionResponse:
    try:
        return service.get_decision(project_id, group_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project '{project_id}' not found.",
        ) from exc
    except GroupNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Duplicate group '{group_id}' not found in project '{project_id}'.",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving decision: {str(exc)}",
        ) from exc
