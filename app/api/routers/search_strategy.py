from datetime import datetime, timezone
from typing import Literal, cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dto.search_strategy import (
    SearchProviderErrorResponse,
    SearchResultRecordResponse,
    SearchResultsImportRequest,
    SearchResultsImportResponse,
    SearchStrategyExecutionRequest,
    SearchStrategyExecutionResponse,
)
from app.domain.author import Author
from app.domain.identifiers import Identifier, IdentifierType
from app.domain.provenance import ProvenanceEntry
from app.domain.publication import Publication
from app.normalization.doi import normalize_doi
from app.repositories.project_publication_repository import (
    ProjectNotFoundError,
    ProjectPublicationRepository,
    demo_project_publication_repository,
)
from app.services.live_search import (
    LiveSearchExecutor,
    build_search_query,
    live_search_service,
)

router = APIRouter(prefix="/projects", tags=["search strategy"])


def get_live_search_executor() -> LiveSearchExecutor:
    return live_search_service


def get_project_publication_repository() -> ProjectPublicationRepository:
    return demo_project_publication_repository


def _source_id(publication: Publication) -> str:
    if publication.provenance:
        return publication.provenance[0].source_record_id
    return str(publication.record_id)


def _doi(publication: Publication) -> str | None:
    for identifier in publication.identifiers:
        if identifier.type is IdentifierType.DOI:
            return normalize_doi(identifier.value) or identifier.value
    return None


def _map_result(
    publication: Publication,
    *,
    provider: str,
) -> SearchResultRecordResponse:
    return SearchResultRecordResponse(
        id=str(publication.record_id),
        title=publication.title,
        authors=[author.display_name for author in publication.authors],
        year=cast(int, publication.publication_year),
        provider=cast(Literal["openalex", "crossref"], provider),
        source_id=_source_id(publication),
        doi=_doi(publication),
    )


@router.post(
    "/{project_id}/search-strategy/executions",
    response_model=SearchStrategyExecutionResponse,
    status_code=status.HTTP_200_OK,
)
async def execute_search_strategy(
    project_id: str,
    payload: SearchStrategyExecutionRequest,
    executor: LiveSearchExecutor = Depends(get_live_search_executor),
) -> SearchStrategyExecutionResponse:
    """Execute the validated strategy through the selected live providers."""

    try:
        execution = await executor.execute(project_id, payload)
    except ProjectNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    publications_by_provider = [
        (provider_result.search_run.provider, publication)
        for provider_result in execution.provider_results
        if provider_result.publications is not None
        for publication in provider_result.publications
        if publication.publication_year is not None
        and payload.publication_year_from
        <= publication.publication_year
        <= payload.publication_year_to
    ]
    results = [
        _map_result(publication, provider=provider)
        for provider, publication in publications_by_provider
    ]
    provider_errors = [
        SearchProviderErrorResponse(
            provider=cast(
                Literal["openalex", "crossref"],
                provider_result.search_run.provider,
            ),
            message=(
                f"{type(provider_result.error).__name__}: {provider_result.error}"
            ),
        )
        for provider_result in execution.provider_results
        if provider_result.error is not None
    ]
    query = build_search_query(payload)
    return SearchStrategyExecutionResponse(
        project_id=project_id,
        rendered_query=query.to_boolean_query(),
        providers=list(payload.providers),
        publication_year_from=payload.publication_year_from,
        publication_year_to=payload.publication_year_to,
        executed_at=datetime.now(timezone.utc),
        result_count=len(results),
        results=results,
        provider_errors=provider_errors,
    )


@router.post(
    "/{project_id}/search-results/imports",
    response_model=SearchResultsImportResponse,
    status_code=status.HTTP_200_OK,
)
def import_search_results(
    project_id: str,
    payload: SearchResultsImportRequest,
    repository: ProjectPublicationRepository = Depends(
        get_project_publication_repository
    ),
) -> SearchResultsImportResponse:
    """Append the explicitly selected result records to the Working Collection."""

    try:
        publications = []
        for record in payload.records:
            identifiers = []
            if record.doi is not None:
                identifiers.append(
                    Identifier(type=IdentifierType.DOI, value=record.doi)
                )
            publications.append(
                Publication(
                    record_id=UUID(record.id),
                    title=record.title,
                    authors=[
                        Author(display_name=display_name)
                        for display_name in record.authors
                    ],
                    publication_year=record.year,
                    identifiers=identifiers,
                    provenance=[
                        ProvenanceEntry(
                            source=record.provider,
                            source_record_id=record.source_id,
                        )
                    ],
                )
            )
        import_result = repository.import_source_publications(
            project_id,
            publications,
        )
    except ProjectNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    return SearchResultsImportResponse(
        project_id=project_id,
        imported_count=import_result.imported_count,
        skipped_count=import_result.skipped_count,
        total_requested=len(payload.records),
        working_collection_count=import_result.working_collection_count,
    )
