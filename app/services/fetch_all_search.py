"""Provider-agnostic "fetch all available results" orchestration (v0.6.5).

One fetch-all job paginates every selected provider independently and
sequentially until, per provider:

* the provider reports no further cursor/page (end of results),
* the provider stops making progress (repeated cursor, empty page while
  claiming more results),
* a technical limit is reached (provider hard cap such as the Semantic
  Scholar relevance-search ~1000 result ceiling, or this service's own
  safety limits on pages/records/wall-clock time),
* an unrecoverable provider error occurs (client-level retries and
  Retry-After backoff are exhausted first).

The loop relies exclusively on the uniform ``SearchProvider.search_with_raw``
contract returning ``ProviderSearchOutput`` (``next_cursor`` / ``has_more`` /
``total_count`` / warnings), so OpenAlex (opaque cursor), Crossref (opaque
cursor) and Semantic Scholar (offset-as-cursor) share one code path and any
future provider is supported without provider-specific branches.

Rate limiting: pages are fetched strictly sequentially, providers are
processed one at a time, and every HTTP call goes through the existing
provider clients with their pacing (e.g. Semantic Scholar 1 rps), tenacity
retry policy and ``Retry-After`` handling. Fetch-all never issues parallel
requests for the same provider.

Progress & cancellation: job state lives in this in-process registry; the
status endpoint reads cheap dictionary lookups (it intentionally does not use
the slow extraction ``/progress`` endpoint). Cancellation is cooperative: a
flag is checked between page fetches so already-fetched records are kept.

Known limitation (accepted for v0.6.5): the platform stores no resumable
per-provider cursors between requests, so a fetch-all job restarts pagination
from the first page. Records are de-duplicated by ``(provider, source_id)``
within the whole job (no record is added or snapshotted twice), but records
already downloaded in earlier executions of the same UI session may travel
over the wire once more.
"""

from __future__ import annotations

import asyncio
import inspect
import os
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal, Protocol, cast
from uuid import UUID, uuid4

import httpx

from app.api.dto.search_strategy import (
    FetchAllProviderProgressResponse,
    FetchAllStartResponse,
    FetchAllStatusResponse,
    ProviderQueryResponse,
    SearchProviderErrorResponse,
    SearchStrategyExecutionRequest,
    SearchStrategyExecutionResponse,
)
from app.domain.publication import Publication
from app.domain.search import SearchQuery, SearchRun, SearchRunStatus
from app.normalization import normalize_publication
from app.providers.search.base import ProviderSearchOutput
from app.rendering import get_query_renderer
from app.repositories.search_result_snapshot_repository import (
    SearchResultSnapshot,
    default_search_result_snapshot_repository,
)
from app.services.live_search import LiveSearchService, build_search_query
from app.services.search_engine import SearchProvider
from app.services.search_strategy_support import (
    map_search_result_record,
    matches_execution_constraints,
    publication_source_id,
)


class FetchAllJobAlreadyRunningError(RuntimeError):
    """Raised when starting a job while the project already has an active one."""


class UnknownFetchAllJobError(KeyError):
    """Raised when referencing a job id that does not exist (or was pruned)."""


def _env_int(name: str, default: int) -> int:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


# Safety limits guarding against runaway pagination. Each provider page call
# returns up to ``max_results`` (100) records, so these caps bound both the
# request count and the accumulated record count per provider.
DEFAULT_MAX_PAGES_PER_PROVIDER = _env_int("FETCH_ALL_MAX_PAGES_PER_PROVIDER", 200)
DEFAULT_MAX_RECORDS_PER_PROVIDER = _env_int("FETCH_ALL_MAX_RECORDS_PER_PROVIDER", 5000)
DEFAULT_MAX_SECONDS = _env_int("FETCH_ALL_MAX_SECONDS", 900)
MAX_FINISHED_JOBS_KEPT = 20

ProviderFactory = Callable[
    [SearchStrategyExecutionRequest, httpx.AsyncClient],
    list[SearchProvider],
]


@dataclass
class FetchAllProviderState:
    """Mutable progress of one provider inside one fetch-all job."""

    name: str
    status: str = "pending"
    fetched_count: int = 0
    kept_count: int = 0
    pages_fetched: int = 0
    total_reported: int | None = None
    limit_reached: bool = False
    message: str | None = None
    rendered_query: str = ""
    warnings: list[str] = field(default_factory=list)
    lossless: bool = True
    search_run_id: UUID | None = None
    kept_records: list[tuple[Publication, str]] = field(default_factory=list)

    def to_response(self) -> FetchAllProviderProgressResponse:
        return FetchAllProviderProgressResponse(
            provider=self.name,
            status=cast(
                Literal[
                    "pending", "running", "complete", "partial", "cancelled", "failed"
                ],
                self.status,
            ),
            fetched_count=self.fetched_count,
            kept_count=self.kept_count,
            pages_fetched=self.pages_fetched,
            total_reported=self.total_reported,
            limit_reached=self.limit_reached,
            message=self.message,
        )


@dataclass
class FetchAllJob:
    job_id: str
    project_id: str
    strategy: SearchStrategyExecutionRequest
    query: SearchQuery
    started_at: datetime
    status: str = "running"
    cancel_requested: bool = False
    finished_at: datetime | None = None
    message: str | None = None
    providers: list[FetchAllProviderState] = field(default_factory=list)
    task: asyncio.Task[None] | None = None
    result: SearchStrategyExecutionResponse | None = None


class SnapshotRepositoryLike(Protocol):
    def save(self, snapshot: SearchResultSnapshot) -> SearchResultSnapshot: ...


class FetchAllSearchService:
    """Owns fetch-all jobs: start, progress reads and cooperative cancellation."""

    def __init__(
        self,
        *,
        provider_factory: ProviderFactory | None = None,
        snapshot_repository: SnapshotRepositoryLike | None = None,
        run_id_factory: Callable[[], UUID] = uuid4,
        clock: Callable[[], float] = time.monotonic,
        max_pages_per_provider: int = DEFAULT_MAX_PAGES_PER_PROVIDER,
        max_records_per_provider: int = DEFAULT_MAX_RECORDS_PER_PROVIDER,
        max_seconds: float = DEFAULT_MAX_SECONDS,
        poll_interval_seconds: float = 0.05,
    ) -> None:
        if max_pages_per_provider < 1:
            raise ValueError("max_pages_per_provider must be at least 1")
        if max_records_per_provider < 1:
            raise ValueError("max_records_per_provider must be at least 1")
        if max_seconds < 0:
            raise ValueError("max_seconds must not be negative")
        self._provider_factory: ProviderFactory = (
            provider_factory or LiveSearchService._build_providers
        )
        self._snapshot_repository = snapshot_repository
        self._run_id_factory = run_id_factory
        self._clock = clock
        self._max_pages_per_provider = max_pages_per_provider
        self._max_records_per_provider = max_records_per_provider
        self._max_seconds = max_seconds
        self._poll_interval_seconds = poll_interval_seconds
        self._jobs: dict[str, FetchAllJob] = {}
        self._active_by_project: dict[str, str] = {}

    # ------------------------------------------------------------------ API

    def start(
        self,
        project_id: str,
        strategy: SearchStrategyExecutionRequest,
    ) -> FetchAllStartResponse:
        active_job_id = self._active_by_project.get(project_id)
        if active_job_id is not None:
            raise FetchAllJobAlreadyRunningError(project_id)
        job = FetchAllJob(
            job_id=str(uuid4()),
            project_id=project_id,
            strategy=strategy,
            query=build_search_query(strategy),
            started_at=datetime.now(timezone.utc),
        )
        self._jobs[job.job_id] = job
        self._prune_finished_jobs()
        self._active_by_project[project_id] = job.job_id
        job.task = asyncio.create_task(self._run(job))
        return FetchAllStartResponse(job_id=job.job_id, project_id=project_id)

    def get_status(self, job_id: str) -> FetchAllStatusResponse:
        job = self._require_job(job_id)
        providers = [state.to_response() for state in job.providers]
        return FetchAllStatusResponse(
            job_id=job.job_id,
            project_id=job.project_id,
            status=cast(
                Literal["running", "completed", "cancelled", "failed"],
                job.status,
            ),
            started_at=job.started_at,
            finished_at=job.finished_at,
            providers=providers,
            fetched_total=sum(state.fetched_count for state in job.providers),
            kept_total=sum(state.kept_count for state in job.providers),
            message=job.message,
            result=job.result,
        )

    def request_cancel(self, job_id: str) -> FetchAllStatusResponse:
        job = self._require_job(job_id)
        if job.status == "running":
            job.cancel_requested = True
        return self.get_status(job_id)

    async def wait(self, job_id: str, timeout: float = 60.0) -> FetchAllJob:
        """Await job completion without cancelling its task; aids tests."""

        job = self._require_job(job_id)
        deadline = time.monotonic() + timeout
        while job.status == "running":
            if time.monotonic() >= deadline:
                raise TimeoutError(f"fetch-all job {job_id} did not finish in time")
            await asyncio.sleep(self._poll_interval_seconds)
        return job

    def active_job_for_project(self, project_id: str) -> FetchAllJob | None:
        job_id = self._active_by_project.get(project_id)
        if job_id is None:
            return None
        job = self._jobs.get(job_id)
        if job is None or job.status != "running":
            return None
        return job

    # -------------------------------------------------------------- internals

    def _require_job(self, job_id: str) -> FetchAllJob:
        try:
            return self._jobs[job_id]
        except KeyError as exc:
            raise UnknownFetchAllJobError(job_id) from exc

    def _prune_finished_jobs(self) -> None:
        finished = [
            (job.started_at, job_id, job.project_id)
            for job_id, job in self._jobs.items()
            if job.status != "running"
        ]
        if len(finished) <= MAX_FINISHED_JOBS_KEPT:
            return
        finished.sort()
        excess = len(finished) - MAX_FINISHED_JOBS_KEPT
        for _, job_id, project_id in finished[:excess]:
            self._jobs.pop(job_id, None)
            if self._active_by_project.get(project_id) == job_id:
                self._active_by_project.pop(project_id, None)

    def _snapshot_repo(self) -> SnapshotRepositoryLike:
        if self._snapshot_repository is None:
            self._snapshot_repository = default_search_result_snapshot_repository()
        return self._snapshot_repository

    async def _run(self, job: FetchAllJob) -> None:
        started_clock = self._clock()
        try:
            async with httpx.AsyncClient(timeout=30.0) as http_client:
                providers = self._provider_factory(job.strategy, http_client)
                if inspect.isawaitable(providers):
                    providers = await providers
                job.providers = [FetchAllProviderState(name=p.name) for p in providers]
                for provider, state in zip(providers, job.providers, strict=True):
                    if job.cancel_requested:
                        state.status = "cancelled"
                        continue
                    await self._run_single_provider(job, provider, state, started_clock)
            self._finalize_job(job)
        except Exception as error:  # pragma: no cover - defensive last resort
            job.status = "failed"
            job.message = f"{type(error).__name__}: {error}"
            job.finished_at = datetime.now(timezone.utc)
        finally:
            self._release_project_slot(job)

    def _release_project_slot(self, job: FetchAllJob) -> None:
        if self._active_by_project.get(job.project_id) == job.job_id:
            self._active_by_project.pop(job.project_id, None)

    async def _run_single_provider(
        self,
        job: FetchAllJob,
        provider: SearchProvider,
        state: FetchAllProviderState,
        started_clock: float,
    ) -> None:
        renderer = get_query_renderer(provider.name)
        rendered = renderer.render(job.query)
        search_run = SearchRun(
            run_id=self._run_id_factory(),
            query_id=job.query.query_id,
            query_version=job.query.version,
            provider=provider.name,
            rendered_query=rendered.query_string,
            is_lossless=rendered.is_lossless,
            warnings=list(rendered.warnings),
            status=SearchRunStatus.RUNNING,
            started_at=datetime.now(timezone.utc),
        )
        state.rendered_query = rendered.query_string
        state.lossless = rendered.is_lossless
        state.warnings = list(rendered.warnings)
        state.search_run_id = search_run.run_id
        state.status = "running"

        snapshot_repository = self._snapshot_repo()
        seen_source_ids: set[str] = set()
        seen_cursors: set[str] = set()
        cursor = "*"

        while True:
            if job.cancel_requested:
                state.status = "cancelled"
                break
            elapsed = self._clock() - started_clock
            if (
                state.pages_fetched >= self._max_pages_per_provider
                or state.fetched_count >= self._max_records_per_provider
                or elapsed >= self._max_seconds
            ):
                state.status = "partial"
                state.limit_reached = True
                state.message = "Stopped by the fetch-all safety limit before the provider reported its final page."
                break
            try:
                output = await provider.search_with_raw(
                    search_run=search_run,
                    search_query=job.query,
                    cursor=cursor,
                )
            except Exception as error:
                state.message = f"{type(error).__name__}: {error}"
                state.status = "partial" if state.fetched_count > 0 else "failed"
                break

            state.pages_fetched += 1
            self._merge_output_metadata(state, output)
            for publication in output.publications:
                normalized = normalize_publication(publication)
                source_id = publication_source_id(normalized)
                if source_id in seen_source_ids:
                    continue
                seen_source_ids.add(source_id)
                state.fetched_count += 1
                if matches_execution_constraints(normalized, job.strategy):
                    snapshot = snapshot_repository.save(
                        SearchResultSnapshot.create(
                            project_id=job.project_id,
                            search_run_id=search_run.run_id,
                            provider=provider.name,
                            source_id=source_id,
                            publication=normalized,
                        )
                    )
                    state.kept_records.append((normalized, str(snapshot.snapshot_id)))
                    state.kept_count += 1

            next_cursor = output.next_cursor
            if next_cursor is None:
                state.status = "complete"
                if (
                    state.total_reported is not None
                    and state.fetched_count < state.total_reported
                ):
                    state.limit_reached = True
                    state.message = (
                        f"Provider reported {state.total_reported} matching records but "
                        f"stopped offering further pages after {state.fetched_count} "
                        f"(provider-side retrieval cap)."
                    )
                break
            if not output.publications:
                state.status = "complete"
                state.message = "Provider returned an empty page while claiming more results; stopped safely."
                break
            if next_cursor == cursor or next_cursor in seen_cursors:
                state.status = "complete"
                state.message = "Provider repeated its pagination cursor; stopped safely."
                break
            seen_cursors.add(cursor)
            cursor = next_cursor

    def _merge_output_metadata(
        self,
        state: FetchAllProviderState,
        output: ProviderSearchOutput,
    ) -> None:
        for warning in output.warnings:
            if warning not in state.warnings:
                state.warnings.append(warning)
        if output.is_lossless is False:
            state.lossless = False
        if output.total_count is not None:
            if state.total_reported is None:
                state.total_reported = output.total_count
            elif output.total_count != state.total_reported:
                state.warnings.append(
                    f"Provider changed its reported total from {state.total_reported} "
                    f"to {output.total_count} during fetch-all; keeping the first value."
                )

    def _finalize_job(self, job: FetchAllJob) -> None:
        cancelled_any = any(state.status == "cancelled" for state in job.providers)
        partial_any = any(state.status == "partial" for state in job.providers)
        if job.cancel_requested or cancelled_any:
            job.status = "cancelled"
        else:
            # Providers that failed early are reported per provider; the job
            # itself completed with the remaining results preserved.
            job.status = "completed"
        if partial_any:
            job.message = (
                "Fetch-all finished with incomplete provider coverage; "
                "see per-provider statuses."
            )
        results = []
        for state in job.providers:
            for publication, snapshot_id in state.kept_records:
                results.append(
                    map_search_result_record(
                        publication,
                        provider=state.name,
                        result_id=snapshot_id,
                    )
                )
        total_count = sum(
            state.total_reported
            if state.total_reported is not None
            else state.fetched_count
            for state in job.providers
        )
        job.result = SearchStrategyExecutionResponse(            project_id=job.project_id,
            rendered_query=job.query.to_boolean_query(),
            provider_queries=[
                ProviderQueryResponse(
                    provider=state.name,
                    rendered_query=state.rendered_query,
                    is_lossless=state.lossless,
                    warnings=list(state.warnings),
                )
                for state in job.providers
            ],
            providers=[state.name for state in job.providers],
            publication_year_from=job.strategy.publication_year_from,
            publication_year_to=job.strategy.publication_year_to,
            executed_at=job.started_at,
            total_count=max(total_count, len(results)),
            returned_count=len(results),
            next_cursor=None,
            has_more=bool(partial_any or cancelled_any),
            results=results,
            provider_errors=[
                SearchProviderErrorResponse(
                    provider=cast(
                        Literal["openalex", "crossref", "semantic_scholar"],
                        state.name,
                    ),
                    message=(
                        f"Fetch-all stopped early ({state.status}): {state.message}"
                    ),
                )
                for state in job.providers
                if state.status in {"failed", "partial"} and state.message is not None
            ],
        )
        job.finished_at = datetime.now(timezone.utc)


fetch_all_service = FetchAllSearchService()
