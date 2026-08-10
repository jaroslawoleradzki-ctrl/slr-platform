from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Literal, cast
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from app.api.dto.search_strategy import (
    BibliographicImportHistoryResponse,
    BibliographicImportResponse,
    ProviderQueryResponse,
    SearchProviderErrorResponse,
    SearchResultRecordResponse,
    SearchResultsImportRequest,
    SearchResultsImportResponse,
    SearchStrategyExecutionRequest,
    SearchStrategyExecutionResponse,
    SearchStrategyPutRequest,
)
from app.api.dto.sources_summary import SourcesSummaryResponse
from app.domain.identifiers import IdentifierType
from app.domain.publication import DocumentType, Publication
from app.domain.search import SearchStrategy
from app.normalization import normalize_publication
from app.normalization.doi import normalize_doi
from app.providers.import_file.bibtex.mapper import map_bibtex_record
from app.providers.import_file.bibtex.parser import parse_bibtex
from app.providers.import_file.ris.mapper import map_ris_record
from app.providers.import_file.ris.parser import parse_ris
from app.repositories.import_history_repository import (
    ImportHistoryRepository,
    SqliteImportHistoryRepository,
    default_import_history_repository,
)
from app.repositories.normalization_execution_repository import (
    NormalizationExecutionRepository,
    SqliteNormalizationExecutionRepository,
    default_normalization_execution_repository,
)
from app.repositories.project_publication_repository import (
    DemoProjectPublicationRepository,
    ProjectNotFoundError,
    ProjectPublicationRepository,
    SqliteProjectPublicationRepository,
    default_project_publication_repository,
)
from app.repositories.search_result_snapshot_repository import (
    SearchResultSnapshot,
    SearchResultSnapshotRepository,
    SqliteSearchResultSnapshotRepository,
    default_search_result_snapshot_repository,
)
from app.repositories.search_strategy_repository import (
    SearchStrategyNotFoundError,
    SearchStrategyRepository,
    default_search_strategy_repository,
)
from app.repositories.transaction_manager import SqliteTransactionManager
from app.services.live_search import (
    LiveSearchExecutor,
    build_search_query,
    live_search_service,
)
from app.services.project_import_service import ProjectImportService
from app.services.sources_summary_service import SourcesSummaryService

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
    return default_project_publication_repository()


def get_import_history_repository() -> ImportHistoryRepository:
    return default_import_history_repository()


def get_normalization_execution_repository() -> NormalizationExecutionRepository:
    return default_normalization_execution_repository()


def get_search_result_snapshot_repository() -> SearchResultSnapshotRepository:
    return default_search_result_snapshot_repository()


def get_project_import_service(
    pub_repo: ProjectPublicationRepository = Depends(get_project_publication_repository),
    history_repo: ImportHistoryRepository = Depends(get_import_history_repository),
    norm_repo: NormalizationExecutionRepository = Depends(get_normalization_execution_repository),
) -> ProjectImportService:
    tx_manager = None
    if isinstance(history_repo, SqliteImportHistoryRepository):
        tx_manager = SqliteTransactionManager(history_repo._database_path)
    elif isinstance(pub_repo, SqliteProjectPublicationRepository):
        tx_manager = SqliteTransactionManager(pub_repo._database_path)
    elif isinstance(norm_repo, SqliteNormalizationExecutionRepository):
        tx_manager = SqliteTransactionManager(norm_repo._database_path)

    return ProjectImportService(
        publication_repository=pub_repo,
        import_history_repository=history_repo,
        normalization_repository=norm_repo,
        transaction_manager=tx_manager,
        snapshot_repository=(
            None
            if isinstance(pub_repo, DemoProjectPublicationRepository)
            else (
                SqliteSearchResultSnapshotRepository(pub_repo._database_path)
                if isinstance(pub_repo, SqliteProjectPublicationRepository)
                else default_search_result_snapshot_repository()
            )
        ),
    )


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
    strategy_repository: SearchStrategyRepository = Depends(get_search_strategy_repository),
    project_repository: ProjectPublicationRepository = Depends(get_project_publication_repository),
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
        strategy_id=(payload.strategy_id or (existing_strategy.strategy_id if existing_strategy else uuid4())),
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
            payload.created_at or (existing_strategy.created_at if existing_strategy else payload.creation_time())
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
    result_id: str | None = None,
) -> SearchResultRecordResponse:
    return SearchResultRecordResponse(
        id=result_id or str(publication.record_id),
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
        _PUBLICATION_TYPE_DOMAIN_MAP[value] for value in payload.publication_types
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
    snapshot_repository: SearchResultSnapshotRepository = Depends(get_search_result_snapshot_repository),
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
        (provider_result.search_run, publication)
        for provider_result in execution.provider_results
        if provider_result.publications is not None
        for publication in provider_result.publications
        if _matches_execution_constraints(publication, payload)
    ]
    results = []
    for search_run, publication in publications_by_provider:
        source_id = _source_id(publication)
        snapshot = snapshot_repository.save(
            SearchResultSnapshot.create(
                project_id=project_id,
                search_run_id=search_run.run_id,
                provider=search_run.provider,
                source_id=source_id,
                publication=publication,
            )
        )
        results.append(_map_result(publication, provider=search_run.provider, result_id=str(snapshot.snapshot_id)))
    provider_errors = [
        SearchProviderErrorResponse(
            provider=cast(
                Literal["openalex", "crossref"],
                provider_result.search_run.provider,
            ),
            message=(f"{type(provider_result.error).__name__}: {provider_result.error}"),
        )
        for provider_result in execution.provider_results
        if provider_result.error is not None
    ]
    successful_provider_results = [
        provider_result for provider_result in execution.provider_results if provider_result.error is None
    ]
    total_count = sum(
        provider_result.total_count
        if provider_result.total_count is not None
        else len(provider_result.publications or [])
        for provider_result in successful_provider_results
    )
    next_cursor = successful_provider_results[0].next_cursor if len(successful_provider_results) == 1 else None
    query = build_search_query(payload)
    provider_queries = [
        ProviderQueryResponse(
            provider=provider_result.search_run.provider,
            rendered_query=provider_result.search_run.rendered_query,
            is_lossless=provider_result.search_run.is_lossless,
            warnings=provider_result.search_run.warnings,
        )
        for provider_result in execution.provider_results
    ]
    return SearchStrategyExecutionResponse(
        project_id=project_id,
        rendered_query=query.to_boolean_query(),
        provider_queries=provider_queries,
        providers=list(payload.providers),
        publication_year_from=payload.publication_year_from,
        publication_year_to=payload.publication_year_to,
        executed_at=datetime.now(timezone.utc),
        total_count=total_count,
        returned_count=len(results),
        next_cursor=next_cursor,
        has_more=any(provider_result.has_more for provider_result in successful_provider_results),
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
    repository: ProjectPublicationRepository = Depends(get_project_publication_repository),
    import_service: ProjectImportService = Depends(get_project_import_service),
) -> SearchResultsImportResponse:
    """Append the explicitly selected result records to the Working Collection."""

    try:
        existing_publications = repository.get_publications(project_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    if not payload.records:
        return SearchResultsImportResponse(
            project_id=project_id,
            imported_count=0,
            skipped_count=0,
            total_requested=0,
            working_collection_count=len(existing_publications),
        )

    # 1. Grupowanie rekordów wg dostawcy (record.provider)
    grouped_records: dict[str, list[SearchResultRecordResponse]] = {}
    for record in payload.records:
        grouped_records.setdefault(record.provider, []).append(record)

    total_imported = 0
    total_skipped = 0
    total_requested = 0
    final_working_count = len(existing_publications)

    try:
        # Pętla po poszczególnych niepustych grupach dostawców
        for provider_name, records_group in grouped_records.items():
            is_single_provider = len(grouped_records) == 1
            group_total_available = payload.total_available if is_single_provider else None

            group_result = import_service.import_provider_results_group(
                project_id=project_id,
                provider_name=provider_name,
                records_group=records_group,
                query=payload.query,
                group_total_available=group_total_available,
            )

            total_imported += group_result.imported_count
            total_skipped += group_result.skipped_count
            total_requested += len(records_group)
            final_working_count = group_result.working_collection_count
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
        imported_count=total_imported,
        skipped_count=total_skipped,
        total_requested=total_requested,
        working_collection_count=final_working_count,
    )


@router.post(
    "/{project_id}/imports",
    response_model=BibliographicImportResponse,
    status_code=status.HTTP_201_CREATED,
)
async def import_bibliographic_file(
    project_id: str,
    file: UploadFile | None = File(default=None),
    repository: ProjectPublicationRepository = Depends(get_project_publication_repository),
    import_service: ProjectImportService = Depends(get_project_import_service),
) -> BibliographicImportResponse:
    """Parse one RIS/BibTeX file and append its publications to a project."""

    if file is None or not file.filename:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="A single RIS or BibTeX file is required.",
        )

    suffix = Path(file.filename).suffix.casefold()
    if suffix not in {".ris", ".bib"}:
        await file.close()
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Unsupported file extension. Use .ris or .bib.",
        )

    try:
        repository.get_publications(project_id)
        raw_content = await file.read()
        if not raw_content.strip():
            raise ValueError("The uploaded file is empty.")
        content = raw_content.decode("utf-8-sig")

        if suffix == ".ris":
            parsed_ris = parse_ris(content)
            publications = [normalize_publication(map_ris_record(record, source="ris")) for record in parsed_ris]
        else:
            parsed_bibtex = parse_bibtex(content)
            publications = [
                normalize_publication(map_bibtex_record(record, source="bibtex")) for record in parsed_bibtex
            ]

        if not publications:
            raise ValueError("The uploaded file contains no bibliographic records.")

        import_result, history_record = import_service.import_bibliographic_publications(
            project_id=project_id,
            filename=file.filename,
            file_format="RIS" if suffix == ".ris" else "BibTeX",
            publications=publications,
        )
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except UnicodeDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="The uploaded file must be valid UTF-8 text.",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    finally:
        await file.close()

    return BibliographicImportResponse(
        import_id=history_record.import_id,
        records_count=history_record.records_count,
        warnings=list(history_record.warnings),
        status=cast(Literal["success", "warning"], history_record.status),
    )


@router.get(
    "/{project_id}/imports",
    response_model=list[BibliographicImportHistoryResponse],
    status_code=status.HTTP_200_OK,
)
def list_bibliographic_imports(
    project_id: str,
    project_repository: ProjectPublicationRepository = Depends(get_project_publication_repository),
    history_repository: ImportHistoryRepository = Depends(get_import_history_repository),
) -> list[BibliographicImportHistoryResponse]:
    """Return durable bibliographic import history for one project."""

    try:
        project_repository.get_publications(project_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return [
        BibliographicImportHistoryResponse(
            import_id=record.import_id,
            project_id=record.project_id,
            source_type=cast(Literal["file", "provider"], record.source_type),
            filename=record.filename,
            format=cast(Literal["RIS", "BibTeX"] | None, record.format),
            provider=record.provider,
            query=record.query,
            records_count=record.records_count,
            total_available=record.total_available,
            status=cast(Literal["success", "warning"], record.status),
            created_at=record.created_at,
            warnings=list(record.warnings),
        )
        for record in history_repository.list_for_project(project_id)
    ]


def get_sources_summary_service(
    pub_repo: ProjectPublicationRepository = Depends(get_project_publication_repository),
    history_repo: ImportHistoryRepository = Depends(get_import_history_repository),
) -> SourcesSummaryService:
    return SourcesSummaryService(
        publication_repository=pub_repo,
        import_history_repository=history_repo,
    )


@router.get(
    "/{project_id}/sources-summary",
    response_model=SourcesSummaryResponse,
    status_code=status.HTTP_200_OK,
)
def get_sources_summary(
    project_id: str,
    project_repository: ProjectPublicationRepository = Depends(get_project_publication_repository),
    service: SourcesSummaryService = Depends(get_sources_summary_service),
) -> SourcesSummaryResponse:
    """Return read model summary for Sources & Imports screen."""

    try:
        project_repository.count_by_project(project_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return service.get_sources_summary(project_id)
