from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Literal, cast
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from app.api.dto.search_strategy import (
    BibliographicImportHistoryResponse,
    BibliographicImportResponse,
    FetchAllStartResponse,
    FetchAllStatusResponse,
    ManualSourceDatabase,
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
from app.domain.search import SearchStrategy
from app.normalization import normalize_publication
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
    SearchRunAudit,
    SqliteSearchResultSnapshotRepository,
    default_search_result_snapshot_repository,
)
from app.repositories.search_strategy_repository import (
    SearchStrategyNotFoundError,
    SearchStrategyRepository,
    default_search_strategy_repository,
)
from app.repositories.transaction_manager import SqliteTransactionManager
from app.services.fetch_all_search import (
    FetchAllJobAlreadyRunningError,
    FetchAllSearchService,
    UnknownFetchAllJobError,
    fetch_all_service,
)
from app.services.live_search import (
    LiveSearchExecutor,
    live_search_service,
)
from app.services.project_import_service import ProjectImportService
from app.services.search_strategy_support import (
    map_search_result_record,
    matches_execution_constraints,
    publication_doi,
    publication_source_id,
)
from app.services.sources_summary_service import SourcesSummaryService

router = APIRouter(prefix="/projects", tags=["search strategy"])


def get_live_search_executor() -> LiveSearchExecutor:
    return live_search_service


def get_fetch_all_search_service() -> FetchAllSearchService:
    return fetch_all_service


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

    query = execution.canonical_query

    runs_by_id = {
        provider_result.search_run.run_id: provider_result.search_run for provider_result in execution.provider_results
    }
    publications_by_provider = []
    for publication in execution.merged_publications:
        if not matches_execution_constraints(publication, payload):
            continue
        run_id = publication.provenance[0].run_id if publication.provenance else None
        if run_id is None or run_id not in runs_by_id:
            continue
        publications_by_provider.append((runs_by_id[run_id], publication))
    results = []
    for search_run, publication in publications_by_provider:
        source_id = publication_source_id(publication)
        snapshot = snapshot_repository.save(
            SearchResultSnapshot.create(
                project_id=project_id,
                search_run_id=search_run.run_id,
                provider=search_run.provider,
                source_id=source_id,
                publication=publication,
            )
        )
        results.append(
            map_search_result_record(publication, provider=search_run.provider, result_id=str(snapshot.snapshot_id))
        )
    provider_errors = [
        SearchProviderErrorResponse(
            provider=cast(
                Literal["openalex", "crossref", "semantic_scholar"],
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
    deduplicated_by_run = {provider_result.search_run.run_id: 0 for provider_result in execution.provider_results}
    seen_dois: set[str] = set()
    for provider_result in execution.provider_results:
        for publication in provider_result.publications or []:
            doi = publication_doi(publication)
            if doi is None:
                continue
            if doi in seen_dois:
                deduplicated_by_run[provider_result.search_run.run_id] += 1
            else:
                seen_dois.add(doi)

    save_audit = getattr(snapshot_repository, "save_audit", None)
    if callable(save_audit):
        for provider_result in execution.provider_results:
            run = provider_result.search_run
            if run.started_at is None or run.finished_at is None:
                continue
            save_audit(
                SearchRunAudit(
                    search_run_id=run.run_id,
                    project_id=project_id,
                    canonical_query_id=query.query_id,
                    canonical_version=query.version,
                    canonical_hash=query.canonical_hash,
                    provider=run.provider,
                    physical_endpoint=run.physical_endpoint or "unknown",
                    physical_query=run.rendered_query,
                    translation_lossless=run.is_lossless,
                    translation_warnings=tuple(run.warnings),
                    retrieved_count=run.records_retrieved,
                    canonical_accepted_count=run.canonical_accepted_count,
                    canonical_rejected_count=run.canonical_rejected_count,
                    canonical_indeterminate_count=run.canonical_indeterminate_count,
                    deduplicated_count=deduplicated_by_run[run.run_id],
                    started_at=run.started_at,
                    finished_at=run.finished_at,
                )
            )
    provider_queries = [
        ProviderQueryResponse(
            provider=provider_result.search_run.provider,
            rendered_query=provider_result.search_run.rendered_query,
            canonical_query_id=query.query_id,
            canonical_version=query.version,
            canonical_hash=query.canonical_hash,
            physical_endpoint=provider_result.search_run.physical_endpoint,
            is_lossless=provider_result.search_run.is_lossless,
            warnings=provider_result.search_run.warnings,
            retrieved_count=provider_result.search_run.records_retrieved,
            canonical_accepted_count=provider_result.search_run.canonical_accepted_count,
            canonical_rejected_count=provider_result.search_run.canonical_rejected_count,
            canonical_indeterminate_count=provider_result.search_run.canonical_indeterminate_count,
            deduplicated_count=deduplicated_by_run[provider_result.search_run.run_id],
        )
        for provider_result in execution.provider_results
    ]
    return SearchStrategyExecutionResponse(
        project_id=project_id,
        rendered_query=query.to_boolean_query(),
        canonical_query_id=query.query_id,
        canonical_version=query.version,
        canonical_hash=query.canonical_hash,
        provider_queries=provider_queries,
        providers=list(payload.providers),
        publication_year_from=payload.publication_year_from,
        publication_year_to=payload.publication_year_to,
        executed_at=datetime.now(timezone.utc),
        total_count=total_count,
        returned_count=len(results),
        retrieved_count=sum(result.search_run.records_retrieved for result in execution.provider_results),
        canonical_accepted_count=sum(
            result.search_run.canonical_accepted_count for result in execution.provider_results
        ),
        canonical_rejected_count=sum(
            result.search_run.canonical_rejected_count for result in execution.provider_results
        ),
        canonical_indeterminate_count=sum(
            result.search_run.canonical_indeterminate_count for result in execution.provider_results
        ),
        deduplicated_count=max(
            0,
            sum(len(result.publications or []) for result in execution.provider_results)
            - len(execution.merged_publications),
        ),
        next_cursor=next_cursor,
        has_more=any(provider_result.has_more for provider_result in successful_provider_results),
        results=results,
        provider_errors=provider_errors,
    )


@router.post(
    "/{project_id}/search-strategy/executions/fetch-all",
    response_model=FetchAllStartResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_fetch_all_search(
    project_id: str,
    payload: SearchStrategyExecutionRequest,
    project_repository: ProjectPublicationRepository = Depends(get_project_publication_repository),
    fetch_all: FetchAllSearchService = Depends(get_fetch_all_search_service),
) -> FetchAllStartResponse:
    """Start a background job that pages every selected provider to its end.

    The request body is the same strategy execution contract; any ``cursor``
    value is deliberately ignored because each provider is paginated from its
    first page. Only one fetch-all job may run per project at a time.
    """

    try:
        project_repository.get_publications(project_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    try:
        return fetch_all.start(project_id, payload)
    except FetchAllJobAlreadyRunningError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A fetch-all job is already running for this project.",
        ) from exc


@router.get(
    "/{project_id}/search-strategy/executions/fetch-all/{job_id}",
    response_model=FetchAllStatusResponse,
    status_code=status.HTTP_200_OK,
)
def get_fetch_all_search_status(
    project_id: str,
    job_id: str,
    fetch_all: FetchAllSearchService = Depends(get_fetch_all_search_service),
) -> FetchAllStatusResponse:
    """Return cheap in-memory progress for one fetch-all job.

    This endpoint is intentionally independent of the slow extraction
    ``/progress`` read model; it performs dictionary lookups only and embeds
    the full result payload once the job reaches a terminal state.
    """

    try:
        status_response = fetch_all.get_status(job_id)
    except UnknownFetchAllJobError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Unknown fetch-all job.",
        ) from exc
    if status_response.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Unknown fetch-all job.",
        )
    return status_response


@router.post(
    "/{project_id}/search-strategy/executions/fetch-all/{job_id}/cancel",
    response_model=FetchAllStatusResponse,
    status_code=status.HTTP_200_OK,
)
def cancel_fetch_all_search(
    project_id: str,
    job_id: str,
    fetch_all: FetchAllSearchService = Depends(get_fetch_all_search_service),
) -> FetchAllStatusResponse:
    """Cooperatively stop further page fetching while keeping fetched records."""

    try:
        status_response = fetch_all.request_cancel(job_id)
    except UnknownFetchAllJobError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Unknown fetch-all job.",
        ) from exc
    if status_response.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Unknown fetch-all job.",
        )
    if status_response.status == "running":
        return status_response
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=f"Fetch-all job already finished with status '{status_response.status}'.",
    )


@router.post(
    "/{project_id}/search-strategy/executions/fetch-all/resume",
    response_model=FetchAllStartResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def resume_fetch_all_search(
    project_id: str,
    project_repository: ProjectPublicationRepository = Depends(get_project_publication_repository),
    fetch_all: FetchAllSearchService = Depends(get_fetch_all_search_service),
) -> FetchAllStartResponse:
    """Resume a previous fetch-all search run from its persisted checkpoints."""

    try:
        project_repository.get_publications(project_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    try:
        return fetch_all.start_resume_job(project_id)
    except FetchAllJobAlreadyRunningError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A fetch-all job is already running for this project.",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.post(
    "/{project_id}/search-strategy/executions/fetch-all/{job_id}/resume",
    response_model=FetchAllStartResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def resume_specific_fetch_all_search(
    project_id: str,
    job_id: str,
    project_repository: ProjectPublicationRepository = Depends(get_project_publication_repository),
    fetch_all: FetchAllSearchService = Depends(get_fetch_all_search_service),
) -> FetchAllStartResponse:
    """Resume a specific fetch-all search job from its persisted checkpoints."""

    try:
        project_repository.get_publications(project_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    try:
        return fetch_all.start_resume_job(project_id, job_id=job_id)
    except FetchAllJobAlreadyRunningError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A fetch-all job is already running for this project.",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


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
    source_database: ManualSourceDatabase | None = Form(default=None),
    source_label: str | None = Form(default=None),
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
            publications = [
                normalize_publication(map_ris_record(record, source="ris", source_database=source_database or "ris"))
                for record in parsed_ris
            ]
        else:
            parsed_bibtex = parse_bibtex(content)
            publications = [
                normalize_publication(
                    map_bibtex_record(record, source="bibtex", source_database=source_database or "bibtex")
                )
                for record in parsed_bibtex
            ]

        if not publications:
            raise ValueError("The uploaded file contains no bibliographic records.")

        import_result, history_record = import_service.import_bibliographic_publications(
            project_id=project_id,
            filename=file.filename,
            file_format="RIS" if suffix == ".ris" else "BibTeX",
            publications=publications,
            source_database=source_database,
            source_label=source_label,
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
