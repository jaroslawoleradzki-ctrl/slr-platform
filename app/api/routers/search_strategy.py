from datetime import datetime, timezone

from fastapi import APIRouter, status

from app.api.dto.search_strategy import (
    SearchStrategyExecutionRequest,
    SearchStrategyExecutionResponse,
)

router = APIRouter(prefix="/projects", tags=["search strategy"])


@router.post(
    "/{project_id}/search-strategy/executions",
    response_model=SearchStrategyExecutionResponse,
    status_code=status.HTTP_200_OK,
)
def execute_search_strategy(
    project_id: str,
    payload: SearchStrategyExecutionRequest,
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
    return SearchStrategyExecutionResponse(
        project_id=project_id,
        rendered_query=rendered_query,
        providers=list(payload.providers),
        publication_year_from=payload.publication_year_from,
        publication_year_to=payload.publication_year_to,
        executed_at=datetime.now(timezone.utc),
    )
