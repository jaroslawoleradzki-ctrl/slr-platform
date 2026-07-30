from datetime import datetime, timezone
from functools import lru_cache
from typing import Literal, cast
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dto.search_strategy import (
    SearchProviderErrorResponse,
    SearchResultRecordResponse,
    SearchResultsImportRequest,
    SearchResultsImportResponse,
    SearchStrategyExecutionRequest,
    SearchStrategyExecutionResponse,
    SearchStrategyPutRequest,
)
from app.domain.author import Author
from app.domain.identifiers import Identifier, IdentifierType
from app.domain.provenance import ProvenanceEntry
from app.domain.publication import DocumentType, Publication
from app.domain.search import SearchStrategy
from app.normalization.doi import normalize_doi
from app.repositories.project_publication_repository import (
    ProjectNotFoundError,
    ProjectPublicationRepository,
    demo_project_publication_repository,
)
from app.repositories.search_strategy_repository import (
    SearchStrategyNotFoundError,
    SearchStrategyRepository,
    default_search_strategy_repository,
)
from app.services.live_search import (
    LiveSearchExecutor,
    build_search_query,
    live_search_service,
)

router = APIRouter(prefix="/projects", tags=["search strategy"])

_PUBLICATION_TYPE_DOMAIN_MAP = {
    "article": DocumentType.JOURNAL_ARTICLE,
    "review": DocumentType.REVIEW,
    "conference_paper": DocumentType.CONFERENCE_PAPER,
    "book_chapter": DocumentType.BOOK_CHAPTER,
}


def get_live_search_executor() -> LiveSearchExecutor:
    return live_search_service


def get_project_publication_repository() -> ProjectPublicationRepository:
    return demo_project_publication_repository


@lru_cache(maxsize=1)
def get_search_strategy_repository() -> SearchStrategyRepository:
    return default_search_strategy_repository()


@router.get(
    "/{project_id}/search-strategy",
    response_model=SearchStrategy,
    status_code=status.HTTP_200_OK,
)
def get_search_strategy(
    project_id: str,
    repository: SearchStrategyRepository = Depends(get_search_strategy_repository),
) -> SearchStrategy:
    """Read the complete persisted strategy for a project."""

    try:
        return repository.get(project_id)
    except SearchStrategyNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.put(
    "/{project_id}/search-strategy",
    response_model=SearchStrategy,
    status_code=status.HTTP_200_OK,
)
def put_search_strategy(
    project_id: str,
    payload: SearchStrategyPutRequest,
    strategy_repository: SearchStrategyRepository = Depends(
        get_search_strategy_repository
    ),
    project_repository: ProjectPublicationRepository = Depends(
        get_project_publication_repository
    ),
) -> SearchStrategy:
    """Validate and atomically replace one project's persisted strategy."""

    try:
        project_repository.get_publications(project_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    try:
        existing_strategy = strategy_repository.get(project_id)
    except SearchStrategyNotFoundError:
        existing_strategy = None

    strategy = SearchStrategy(
        strategy_id=(
            payload.strategy_id
            or (existing_strategy.strategy_id if existing_strategy else uuid4())
        ),
        project_id=project_id,
        name=payload.name,
        description=payload.description,
        research_questions=payload.research_questions,
        concept_groups=payload.concept_groups,
        group_operator=payload.group_operator,
        constraints=payload.constraints,
        providers=[str(provider) for provider in payload.providers],
        queries=payload.queries,
        version=payload.version,
        created_at=(
            payload.created_at
            or (
                existing_strategy.created_at
                if existing_strategy
                else payload.creation_time()
            )
        ),
        updated_at=datetime.now(timezone.utc),
    )
    return strategy_repository.save(strategy)


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


def _matches_execution_constraints(
    publication: Publication,
    payload: SearchStrategyExecutionRequest,
) -> bool:
    if (
        publication.publication_year is None
        or publication.publication_year < payload.publication_year_from
        or publication.publication_year > payload.publication_year_to
    ):
        return False
    if payload.languages and publication.language not in payload.languages:
        return False
    if payload.publication_types and publication.document_type not in {
        _PUBLICATION_TYPE_DOMAIN_MAP[value]
        for value in payload.publication_types
    }:
        return False
    if payload.open_access and publication.open_access is not True:
        return False
    return True


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
        if _matches_execution_constraints(publication, payload)
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
    successful_provider_results = [
        provider_result
        for provider_result in execution.provider_results
        if provider_result.error is None
    ]
    total_count = sum(
        provider_result.total_count
        if provider_result.total_count is not None
        else len(provider_result.publications or [])
        for provider_result in successful_provider_results
    )
    next_cursor = (
        successful_provider_results[0].next_cursor
        if len(successful_provider_results) == 1
        else None
    )
    query = build_search_query(payload)
    return SearchStrategyExecutionResponse(
        project_id=project_id,
        rendered_query=query.to_boolean_query(),
        providers=list(payload.providers),
        publication_year_from=payload.publication_year_from,
        publication_year_to=payload.publication_year_to,
        executed_at=datetime.now(timezone.utc),
        total_count=total_count,
        returned_count=len(results),
        next_cursor=next_cursor,
        has_more=any(
            provider_result.has_more
            for provider_result in successful_provider_results
        ),
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
