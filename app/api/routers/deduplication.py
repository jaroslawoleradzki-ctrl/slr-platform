import logging
from time import perf_counter
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.routing import APIRoute
from starlette.types import Message, Receive, Scope, Send

from app.api.dto.deduplication import (
    DuplicateGroupDecisionRequest,
    DuplicateGroupDecisionResponse,
    DuplicateGroupListResponse,
    DuplicateGroupMergeRequest,
    DuplicateGroupMergeResponse,
)
from app.repositories.duplicate_review_decision_repository import GroupNotFoundError
from app.repositories.project_publication_repository import ProjectNotFoundError
from app.services.duplicate_diagnostics import request_correlation
from app.services.project_duplicate_service import (
    ProjectDuplicateService,
    project_duplicate_service,
)

logger = logging.getLogger(__name__)


class DuplicateTimingRoute(APIRoute):
    async def handle(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["method"] != "GET" or not self.path.endswith("/duplicate-groups"):
            await super().handle(scope, receive, send)
            return
        started = perf_counter()
        correlation_id = uuid4().hex
        token = request_correlation.set(correlation_id)
        response_status = 500
        response_bytes = 0

        async def measured_send(message: Message) -> None:
            nonlocal response_status, response_bytes
            if message["type"] == "http.response.start":
                response_status = message["status"]
            elif message["type"] == "http.response.body":
                response_bytes += len(message.get("body", b""))
            await send(message)
            if message["type"] == "http.response.body" and not message.get("more_body", False):
                logger.info(
                    "duplicate_groups_response_complete correlation_id=%s status=%d response_bytes=%d duration_ms=%.3f",
                    correlation_id, response_status, response_bytes, (perf_counter() - started) * 1000,
                )

        try:
            await super().handle(scope, receive, measured_send)
        finally:
            request_correlation.reset(token)


router = APIRouter(prefix="/projects", tags=["deduplication"], route_class=DuplicateTimingRoute)


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
    started = perf_counter()
    correlation_id = request_correlation.get()
    try:
        result = service.get_candidate_duplicate_groups(project_id)
    except ProjectNotFoundError as exc:
        logger.info(
            "duplicate_groups_http correlation_id=%s status=404 duration_ms=%.3f",
            correlation_id,
            (perf_counter() - started) * 1000,
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project '{project_id}' not found.",
        ) from exc
    except Exception as exc:
        logger.error(
            "duplicate_groups_http correlation_id=%s status=500 error_type=%s duration_ms=%.3f",
            correlation_id,
            type(exc).__name__,
            (perf_counter() - started) * 1000,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving duplicate groups: {str(exc)}",
        ) from exc
    logger.info(
        "duplicate_groups_http correlation_id=%s status=200 duration_ms=%.3f",
        correlation_id,
        (perf_counter() - started) * 1000,
    )
    return result


@router.post(
    "/{project_id}/duplicate-groups/{group_id}/decision",
    response_model=DuplicateGroupDecisionResponse,
    status_code=status.HTTP_200_OK,
    summary="Record reviewer decision for a candidate duplicate group",
    description=(
        "Records or overwrites a human review decision (APPROVE or REJECT) for a candidate duplicate group. "
        "Decisions are stored durably in SQLite database and do not modify underlying publication records or trigger merges."
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
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error recording decision: {str(exc)}",
        ) from exc


@router.post(
    "/{project_id}/duplicate-groups/{group_id}/merge",
    response_model=DuplicateGroupMergeResponse,
    status_code=status.HTTP_200_OK,
    summary="Execute a canonical technical merge for an approved duplicate group",
    description=(
        "Persists a canonical record in an existing member row and supersedes the other source rows. "
        "Requires an APPROVE reviewer decision."
    ),
)
def merge_duplicate_group(
    project_id: str,
    group_id: str,
    payload: DuplicateGroupMergeRequest | None = None,
    service: ProjectDuplicateService = Depends(get_duplicate_service),
) -> DuplicateGroupMergeResponse:
    try:
        return service.merge_group(
            project_id=project_id,
            group_id=group_id,
            rationale=payload.rationale if payload is not None else None,
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
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error merging group: {str(exc)}",
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
