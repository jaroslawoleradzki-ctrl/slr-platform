from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dto.search_strategy import (
    SearchStrategyExecutionRequest,
    SearchStrategyExecutionResponse,
)
from app.repositories.project_publication_repository import ProjectNotFoundError
from app.services.controlled_search_result_source import (
    SearchResultSource,
    controlled_search_result_source,
)

router = APIRouter(prefix="/projects", tags=["search strategy"])


def get_search_result_source() -> SearchResultSource:
    return controlled_search_result_source


@router.post(
    "/{project_id}/search-strategy/executions",
    response_model=SearchStrategyExecutionResponse,
    status_code=status.HTTP_200_OK,
)
def execute_search_strategy(
    project_id: str,
    payload: SearchStrategyExecutionRequest,
    result_source: SearchResultSource = Depends(get_search_result_source),
) -> SearchStrategyExecutionResponse:
    """Validate a user strategy for provider execution.

    Search result retrieval and presentation belong to Phase 6.7.2. This endpoint
    is intentionally stateless and returns the backend-authoritative validated
    execution contract for Module 1.
    """

    rendered_query = " AND ".join(
        f"({' OR '.join(f'\"{term}\"' for term in group.terms)})"
        for group in payload.concept_groups
    )
    try:
        results = result_source.search(project_id, payload)
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return SearchStrategyExecutionResponse(
        project_id=project_id,
        rendered_query=rendered_query,
        providers=list(payload.providers),
        publication_year_from=payload.publication_year_from,
        publication_year_to=payload.publication_year_to,
        executed_at=datetime.now(timezone.utc),
        result_count=len(results),
        results=results,
    )
