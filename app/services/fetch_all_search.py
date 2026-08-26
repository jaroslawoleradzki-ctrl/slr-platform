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

Only an explicit provider end (no next cursor) proves completeness and maps
to status ``complete``. Progress-stopping anomalies - repeated cursor or an
empty page while more results were claimed - are reported as ``partial``
because they do not prove all available results were retrieved; the same
applies to safety-limit stops (``partial``) and errors after data
(``partial``, before data ``failed``).

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
from typing import Any, Literal, Protocol, cast
from uuid import UUID, uuid4

import httpx
from pydantic import ValidationError

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
    DuplicateSearchResultSnapshotError,
    SearchResultSnapshot,
    SearchRunAudit,
    default_search_result_snapshot_repository,
)
from app.repositories.search_run_checkpoint_repository import (
    SearchRunCheckpoint,
    SearchRunCheckpointRepository,
    default_search_run_checkpoint_repository,
)
from app.services.canonical_query_validator import (
    CanonicalMatchStatus,
    validate_canonical_query,
)
from app.services.live_search import LiveSearchService, build_search_query
from app.services.metadata_enrichment import MetadataEnrichmentService
from app.services.result_merger import ResultMerger
from app.services.search_engine import SearchProvider
from app.services.search_strategy_support import (
    map_search_result_record,
    matches_execution_constraints,
    publication_doi,
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

HIGH_INDETERMINATE_RATE_WARNING = (
    "High indeterminate rate: over 50% of candidates could not be fully evaluated because "
    "abstract or scoped fields were missing (commonly observed with Crossref); "
    "records were retained to protect recall."
)


def _reconcile_indeterminate_warning(state: FetchAllProviderState) -> None:
    """Ensure high-indeterminate warning strictly reflects the current counters."""
    is_high = (
        state.fetched_count > 0
        and (state.canonical_indeterminate_count / state.fetched_count) > 0.5
    )
    if is_high:
        if HIGH_INDETERMINATE_RATE_WARNING not in state.warnings:
            state.warnings.append(HIGH_INDETERMINATE_RATE_WARNING)
        elif state.warnings.count(HIGH_INDETERMINATE_RATE_WARNING) > 1:
            first_idx = state.warnings.index(HIGH_INDETERMINATE_RATE_WARNING)
            state.warnings = [
                w
                for idx, w in enumerate(state.warnings)
                if w != HIGH_INDETERMINATE_RATE_WARNING or idx == first_idx
            ]
    else:
        if HIGH_INDETERMINATE_RATE_WARNING in state.warnings:
            state.warnings = [w for w in state.warnings if w != HIGH_INDETERMINATE_RATE_WARNING]


@dataclass
class FetchAllProviderState:
    """Mutable progress of one provider inside one fetch-all job."""

    name: str
    status: str = "pending"
    fetched_count: int = 0
    kept_count: int = 0
    canonical_accepted_count: int = 0
    canonical_rejected_count: int = 0
    canonical_indeterminate_count: int = 0
    deduplicated_count: int = 0
    pages_fetched: int = 0
    total_reported: int | None = None
    limit_reached: bool = False
    resumable: bool = False
    message: str | None = None
    rendered_query: str = ""
    warnings: list[str] = field(default_factory=list)
    lossless: bool = True
    search_run_id: UUID | None = None
    cursor: str | None = None
    plan_metadata: dict[str, Any] | None = None
    kept_records: list[Publication] = field(default_factory=list)

    def to_response(self) -> FetchAllProviderProgressResponse:
        return FetchAllProviderProgressResponse(
            provider=self.name,
            status=cast(
                Literal["pending", "running", "complete", "partial", "cancelled", "failed"],
                self.status,
            ),
            fetched_count=self.fetched_count,
            kept_count=self.kept_count,
            canonical_accepted_count=self.canonical_accepted_count,
            canonical_rejected_count=self.canonical_rejected_count,
            canonical_indeterminate_count=self.canonical_indeterminate_count,
            deduplicated_count=self.deduplicated_count,
            pages_fetched=self.pages_fetched,
            total_reported=self.total_reported,
            limit_reached=self.limit_reached,
            resumable=self.resumable,
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
    resumed_from_job_id: str | None = None


class SnapshotRepositoryLike(Protocol):
    def save(self, snapshot: SearchResultSnapshot) -> SearchResultSnapshot: ...
    def get_for_search_run(
        self, project_id: str, search_run_id: UUID, *, connection: Any = None
    ) -> list[SearchResultSnapshot]: ...


class FetchAllSearchService:
    """Owns fetch-all jobs: start, progress reads, durable checkpointing, and resume."""

    def __init__(
        self,
        *,
        provider_factory: ProviderFactory | None = None,
        snapshot_repository: SnapshotRepositoryLike | None = None,
        checkpoint_repository: SearchRunCheckpointRepository | None = None,
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
        self._provider_factory: ProviderFactory = provider_factory or LiveSearchService._build_providers
        self._snapshot_repository = snapshot_repository
        self._checkpoint_repository = checkpoint_repository
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

    def start_resume_job(
        self,
        project_id: str,
        job_id: str | UUID | None = None,
    ) -> FetchAllStartResponse:
        active_job_id = self._active_by_project.get(project_id)
        if active_job_id is not None:
            raise FetchAllJobAlreadyRunningError(project_id)

        target_job_id: UUID | None = UUID(str(job_id)) if job_id is not None else None
        if target_job_id is not None:
            checkpoints = self._checkpoint_repo().get_checkpoints_for_job(target_job_id)
            if checkpoints and any(cp.project_id != project_id for cp in checkpoints):
                raise ValueError(f"Search job '{job_id}' does not belong to project '{project_id}'")
        else:
            checkpoints = self._checkpoint_repo().get_latest_job_checkpoints(project_id)

        if not checkpoints:
            raise ValueError(f"No resumable search checkpoints found for project '{project_id}'")

        # Verify at least one checkpoint is resumable
        has_resumable = any(cp.resumable for cp in checkpoints)
        if not has_resumable and all(cp.status == "complete" for cp in checkpoints):
            raise ValueError(f"All search runs for project '{project_id}' are already complete")

        # Determine strategy from existing memory job or checkpoint plan_metadata
        strategy: SearchStrategyExecutionRequest | None = None
        source_job_id = str(checkpoints[0].job_id)
        if source_job_id in self._jobs:
            strategy = self._jobs[source_job_id].strategy
        else:
            for cp in checkpoints:
                if cp.plan_metadata and "strategy" in cp.plan_metadata:
                    raw_strategy = cp.plan_metadata["strategy"]
                    try:
                        strategy = SearchStrategyExecutionRequest.model_validate(raw_strategy)
                        break
                    except (ValidationError, TypeError, ValueError) as exc:
                        raise ValueError(
                            f"Cannot resume search for project '{project_id}': "
                            "search strategy metadata in checkpoint is invalid"
                        ) from exc
        if strategy is None:
            raise ValueError(
                f"Cannot resume search for project '{project_id}': search strategy metadata is missing from checkpoints"
            )

        job = FetchAllJob(
            job_id=str(uuid4()),
            project_id=project_id,
            strategy=strategy,
            query=build_search_query(strategy),
            started_at=datetime.now(timezone.utc),
            resumed_from_job_id=source_job_id,
        )
        self._jobs[job.job_id] = job
        self._prune_finished_jobs()
        self._active_by_project[project_id] = job.job_id
        job.task = asyncio.create_task(self._run(job, resume_checkpoints=checkpoints))
        return FetchAllStartResponse(job_id=job.job_id, project_id=project_id)

    def get_status(self, job_id: str) -> FetchAllStatusResponse:
        job = self._jobs.get(job_id)
        if job is None:
            # Check if this job exists durably in the checkpoint repository
            try:
                checkpoints = self._checkpoint_repo().get_checkpoints_for_job(UUID(job_id))
            except Exception:
                checkpoints = []
            if not checkpoints:
                raise UnknownFetchAllJobError(job_id)
            # Reconstruct status response from checkpoints
            providers = [
                FetchAllProviderProgressResponse(
                    provider=cp.provider,
                    status=cast(
                        Literal["pending", "running", "complete", "partial", "cancelled", "failed"],
                        cp.status,
                    ),
                    fetched_count=cp.fetched_count,
                    kept_count=cp.canonical_accepted_count,
                    canonical_accepted_count=cp.canonical_accepted_count,
                    canonical_rejected_count=cp.canonical_rejected_count,
                    canonical_indeterminate_count=cp.canonical_indeterminate_count,
                    deduplicated_count=cp.deduplicated_count,
                    pages_fetched=cp.pages_fetched,
                    total_reported=None,
                    limit_reached=False,
                    resumable=cp.resumable,
                    message=None,
                )
                for cp in checkpoints
            ]
            all_complete = all(cp.status == "complete" for cp in checkpoints)
            any_cancelled = any(cp.status == "cancelled" for cp in checkpoints)
            any_failed = any(cp.status == "failed" for cp in checkpoints)
            any_resumable = any(cp.resumable for cp in checkpoints)
            job_status: Literal["running", "completed", "cancelled", "failed"] = (
                "completed" if all_complete else ("cancelled" if any_cancelled else ("failed" if any_failed else "completed"))
            )
            return FetchAllStatusResponse(
                job_id=job_id,
                project_id=checkpoints[0].project_id,
                status=job_status,
                started_at=checkpoints[0].created_at,
                finished_at=max(cp.updated_at for cp in checkpoints),
                providers=providers,
                fetched_total=sum(cp.fetched_count for cp in checkpoints),
                kept_total=sum(cp.canonical_accepted_count for cp in checkpoints),
                canonical_accepted_total=sum(cp.canonical_accepted_count for cp in checkpoints),
                canonical_rejected_total=sum(cp.canonical_rejected_count for cp in checkpoints),
                canonical_indeterminate_total=sum(cp.canonical_indeterminate_count for cp in checkpoints),
                deduplicated_total=sum(cp.deduplicated_count for cp in checkpoints),
                resumable=any_resumable,
                message=None,
                result=None,
            )

        providers = [state.to_response() for state in job.providers]
        is_resumable = any(state.resumable for state in job.providers)
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
            canonical_accepted_total=sum(state.canonical_accepted_count for state in job.providers),
            canonical_rejected_total=sum(state.canonical_rejected_count for state in job.providers),
            canonical_indeterminate_total=sum(state.canonical_indeterminate_count for state in job.providers),
            deduplicated_total=sum(state.deduplicated_count for state in job.providers),
            resumable=is_resumable,
            message=job.message,
            result=job.result,
        )

    def request_cancel(self, job_id: str) -> FetchAllStatusResponse:
        job = self._jobs.get(job_id)
        if job is not None and job.status == "running":
            job.cancel_requested = True
            for state in job.providers:
                if state.status == "running":
                    state.status = "cancelled"
                    state.resumable = True
                    self._save_checkpoint(job, state, state.cursor, resumable=True)
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
            (job.started_at, job_id, job.project_id) for job_id, job in self._jobs.items() if job.status != "running"
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

    def _checkpoint_repo(self) -> SearchRunCheckpointRepository:
        if self._checkpoint_repository is None:
            self._checkpoint_repository = default_search_run_checkpoint_repository()
        return self._checkpoint_repository

    def _save_checkpoint(
        self,
        job: FetchAllJob,
        state: FetchAllProviderState,
        cursor: str | None,
        resumable: bool = False,
    ) -> None:
        if state.search_run_id is None:
            state.search_run_id = self._run_id_factory()
        state.resumable = resumable
        _reconcile_indeterminate_warning(state)

        plan_meta: dict[str, Any] = {"strategy": job.strategy.model_dump(mode="json")}
        if job.resumed_from_job_id:
            plan_meta["resumed_from_job_id"] = job.resumed_from_job_id
        if state.plan_metadata:
            plan_meta.update(state.plan_metadata)
        if cursor and cursor.startswith("crossref-plan:"):
            from app.providers.search.crossref import CrossrefProvider
            try:
                q_idx, phys_cur = CrossrefProvider._decode_candidate_cursor(cursor)
                plan_meta["current_query_index"] = q_idx
                plan_meta["current_physical_cursor"] = phys_cur
            except Exception:
                pass

        checkpoint = SearchRunCheckpoint(

            search_run_id=state.search_run_id,
            project_id=job.project_id,
            job_id=UUID(job.job_id),
            provider=state.name,
            cursor=cursor,
            pages_fetched=state.pages_fetched,
            fetched_count=state.fetched_count,
            canonical_accepted_count=state.canonical_accepted_count,
            canonical_rejected_count=state.canonical_rejected_count,
            canonical_indeterminate_count=state.canonical_indeterminate_count,
            deduplicated_count=state.deduplicated_count,
            status=state.status,
            resumable=resumable,
            plan_metadata=plan_meta,
            warnings=tuple(state.warnings),
            created_at=job.started_at,
            updated_at=datetime.now(timezone.utc),
        )
        self._checkpoint_repo().save_checkpoint(checkpoint)

    async def _run(
        self,
        job: FetchAllJob,
        resume_checkpoints: list[SearchRunCheckpoint] | None = None,
    ) -> None:
        started_clock = self._clock()
        try:
            async with httpx.AsyncClient(timeout=30.0) as http_client:
                providers = self._provider_factory(job.strategy, http_client)
                if inspect.isawaitable(providers):
                    providers = await providers

                checkpoints_by_provider = {cp.provider: cp for cp in (resume_checkpoints or [])}
                job.providers = []
                get_snapshots = getattr(self._snapshot_repo(), "get_for_search_run", None)
                for p in providers:
                    cp = checkpoints_by_provider.get(p.name)
                    if cp is not None and cp.status == "complete" and not cp.resumable:
                        prev_records: list[Publication] = []
                        if callable(get_snapshots):
                            prev_records = [
                                s.publication
                                for s in get_snapshots(job.project_id, cp.search_run_id)
                                if s.provider.casefold() == p.name.casefold()
                            ]
                        state = FetchAllProviderState(
                            name=p.name,
                            status="complete",
                            fetched_count=cp.fetched_count,
                            kept_count=cp.canonical_accepted_count,
                            canonical_accepted_count=cp.canonical_accepted_count,
                            canonical_rejected_count=cp.canonical_rejected_count,
                            canonical_indeterminate_count=cp.canonical_indeterminate_count,
                            deduplicated_count=cp.deduplicated_count,
                            pages_fetched=cp.pages_fetched,
                            resumable=False,
                            warnings=list(cp.warnings),
                            search_run_id=cp.search_run_id,
                            cursor=cp.cursor,
                            kept_records=prev_records,
                        )
                        _reconcile_indeterminate_warning(state)
                    elif cp is not None:
                        prev_records = []
                        if callable(get_snapshots):
                            prev_records = [
                                s.publication
                                for s in get_snapshots(job.project_id, cp.search_run_id)
                                if s.provider.casefold() == p.name.casefold()
                            ]
                        state = FetchAllProviderState(
                            name=p.name,
                            status="pending",
                            fetched_count=cp.fetched_count,
                            kept_count=cp.canonical_accepted_count,
                            canonical_accepted_count=cp.canonical_accepted_count,
                            canonical_rejected_count=cp.canonical_rejected_count,
                            canonical_indeterminate_count=cp.canonical_indeterminate_count,
                            deduplicated_count=cp.deduplicated_count,
                            pages_fetched=cp.pages_fetched,
                            resumable=cp.resumable,
                            warnings=list(cp.warnings),
                            search_run_id=cp.search_run_id,
                            cursor=cp.cursor,
                            plan_metadata=cp.plan_metadata,
                            kept_records=prev_records,
                        )
                        _reconcile_indeterminate_warning(state)
                    else:
                        state = FetchAllProviderState(name=p.name)
                    job.providers.append(state)

                enricher = LiveSearchService._build_enricher(http_client, enable_external_lookups=False)
                known_abstracts: dict[str, tuple[str, str]] = {}
                for provider, state in zip(providers, job.providers, strict=True):
                    if job.cancel_requested:
                        state.status = "cancelled"
                        state.resumable = True
                        self._save_checkpoint(job, state, state.cursor or "*", resumable=True)
                        continue

                    if state.status == "complete" and not state.resumable:
                        continue
                    initial_cp = checkpoints_by_provider.get(provider.name)
                    await self._run_single_provider(
                        job, provider, state, started_clock, enricher, known_abstracts, initial_checkpoint=initial_cp
                    )
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
        enricher: MetadataEnrichmentService | None = None,
        known_abstracts: dict[str, tuple[str, str]] | None = None,
        initial_checkpoint: SearchRunCheckpoint | None = None,
    ) -> None:
        renderer = get_query_renderer(provider.name)
        rendered = renderer.render(job.query)
        run_id = initial_checkpoint.search_run_id if initial_checkpoint is not None else self._run_id_factory()
        search_run = SearchRun(
            run_id=run_id,
            query_id=job.query.query_id,
            query_version=job.query.version,
            provider=provider.name,
            rendered_query=rendered.query_string,
            canonical_hash=job.query.canonical_hash,
            physical_endpoint=rendered.physical_endpoint,
            is_lossless=rendered.is_lossless,
            warnings=list(rendered.warnings),
            status=SearchRunStatus.RUNNING,
            started_at=datetime.now(timezone.utc),
        )
        state.rendered_query = rendered.query_string
        state.lossless = rendered.is_lossless
        if rendered.metadata:
            state.plan_metadata = {**(state.plan_metadata or {}), **rendered.metadata}
        for w in rendered.warnings:
            if w not in state.warnings:
                state.warnings.append(w)
        state.search_run_id = search_run.run_id
        state.status = "running"

        seen_source_ids: set[str] = {publication_source_id(p) for p in state.kept_records}
        seen_cursors: set[str] = set()
        cursor = initial_checkpoint.cursor if initial_checkpoint is not None and initial_checkpoint.cursor else "*"
        state.cursor = cursor

        # Save initial running checkpoint
        self._save_checkpoint(job, state, cursor, resumable=True)

        while True:
            if job.cancel_requested:
                state.status = "cancelled"
                state.resumable = True
                self._save_checkpoint(job, state, cursor, resumable=True)
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
                state.resumable = bool(cursor is not None)
                self._save_checkpoint(job, state, cursor, resumable=state.resumable)
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
                state.resumable = bool(cursor is not None)
                self._save_checkpoint(job, state, cursor, resumable=state.resumable)
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

                doi = publication_doi(normalized)
                if normalized.abstract is not None and doi:
                    if known_abstracts is not None:
                        known_abstracts[doi] = (normalized.abstract, state.name)

                if enricher is not None and normalized.abstract is None and doi:
                    enriched, _ = await enricher.enrich_single(normalized, known_abstracts=known_abstracts)
                else:
                    enriched = normalized

                validation = validate_canonical_query(job.query, enriched)
                if validation.status is CanonicalMatchStatus.NON_MATCH:
                    state.canonical_rejected_count += 1
                    continue
                if validation.status is CanonicalMatchStatus.INDETERMINATE:
                    state.canonical_indeterminate_count += 1
                    warning = "A candidate had a missing canonically scoped field and was retained to protect recall."
                    if warning not in state.warnings:
                        state.warnings.append(warning)
                else:
                    state.canonical_accepted_count += 1
                if matches_execution_constraints(enriched, job.strategy):
                    state.kept_records.append(enriched)
                    state.kept_count += 1

            _reconcile_indeterminate_warning(state)

            next_cursor = output.next_cursor
            state.cursor = next_cursor

            if next_cursor is None:
                state.status = "complete"
                state.resumable = False
                if state.total_reported is not None and state.fetched_count < state.total_reported:
                    state.limit_reached = True
                    state.message = (
                        f"Provider reported {state.total_reported} matching records but "
                        f"stopped offering further pages after {state.fetched_count} "
                        f"(provider-side retrieval cap)."
                    )
                self._save_checkpoint(job, state, None, resumable=False)
                break
            if not output.publications:
                state.status = "partial"
                state.limit_reached = True
                state.resumable = True
                state.message = (
                    "Provider returned an empty page while claiming more results; pagination could not safely continue."
                )
                self._save_checkpoint(job, state, next_cursor, resumable=True)
                break
            if next_cursor == cursor or next_cursor in seen_cursors:
                state.status = "partial"
                state.limit_reached = True
                state.resumable = False
                state.message = "Provider repeated its pagination cursor; pagination could not safely continue."
                self._save_checkpoint(job, state, next_cursor, resumable=False)
                break

            # Save in-flight progress checkpoint after each page
            self._save_checkpoint(job, state, next_cursor, resumable=True)
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
            job.message = "Fetch-all finished with incomplete provider coverage; see per-provider statuses."
        for state in job.providers:
            state.deduplicated_count = 0
            _reconcile_indeterminate_warning(state)
        all_records = [(publication, state) for state in job.providers for publication in state.kept_records]
        seen_dois: set[str] = set()
        for publication, state in all_records:
            doi = publication_doi(publication)
            if doi is not None:
                if doi in seen_dois:
                    state.deduplicated_count += 1
                else:
                    seen_dois.add(doi)
        merged_publications = ResultMerger().merge(publication for publication, _ in all_records)
        post_merge_validations = [
            validate_canonical_query(job.query, publication) for publication in merged_publications
        ]
        merged_publications = [
            publication
            for publication, validation in zip(merged_publications, post_merge_validations, strict=True)
            if validation.status is not CanonicalMatchStatus.NON_MATCH
        ]
        finished_at = datetime.now(timezone.utc)
        save_audit = getattr(self._snapshot_repo(), "save_audit", None)
        if callable(save_audit):
            for state in job.providers:
                if state.search_run_id is None:
                    continue
                if job.resumed_from_job_id:
                    resume_notice = f"Execution resumed from job {job.resumed_from_job_id}"
                    if resume_notice not in state.warnings:
                        state.warnings.append(resume_notice)
                rendered = get_query_renderer(state.name).render(job.query)
                save_audit(

                    SearchRunAudit(
                        search_run_id=state.search_run_id,
                        project_id=job.project_id,
                        canonical_query_id=job.query.query_id,
                        canonical_version=job.query.version,
                        canonical_hash=job.query.canonical_hash,
                        provider=state.name,
                        physical_endpoint=rendered.physical_endpoint,
                        physical_query=state.rendered_query,
                        translation_lossless=state.lossless,
                        translation_warnings=tuple(state.warnings),
                        retrieved_count=state.fetched_count,
                        canonical_accepted_count=state.canonical_accepted_count,
                        canonical_rejected_count=state.canonical_rejected_count,
                        canonical_indeterminate_count=state.canonical_indeterminate_count,
                        deduplicated_count=state.deduplicated_count,
                        started_at=job.started_at,
                        finished_at=finished_at,
                    )
                )
        results = []
        state_by_run_id = {state.search_run_id: state for state in job.providers if state.search_run_id is not None}
        existing_snapshots_by_key: dict[tuple[UUID, str], SearchResultSnapshot] = {}
        get_snapshots = getattr(self._snapshot_repo(), "get_for_search_run", None)
        if callable(get_snapshots):
            for state in job.providers:
                if state.search_run_id is not None:
                    for snap in get_snapshots(job.project_id, state.search_run_id):
                        existing_snapshots_by_key[(snap.search_run_id, snap.source_id)] = snap

        for publication in merged_publications:
            run_id = publication.provenance[0].run_id
            if run_id is None or run_id not in state_by_run_id:
                continue
            state = state_by_run_id[run_id]
            provider = state.name
            source_id = publication_source_id(publication)
            try:
                snapshot = self._snapshot_repo().save(
                    SearchResultSnapshot.create(
                        project_id=job.project_id,
                        search_run_id=run_id,
                        provider=provider,
                        source_id=source_id,
                        publication=publication,
                    )
                )
                result_id = str(snapshot.snapshot_id)
            except DuplicateSearchResultSnapshotError:
                existing = existing_snapshots_by_key.get((run_id, source_id))
                result_id = str(existing.snapshot_id) if existing is not None else str(publication.record_id)
            results.append(
                map_search_result_record(
                    publication,
                    provider=provider,
                    result_id=result_id,
                )
            )

        total_count = sum(
            state.total_reported if state.total_reported is not None else state.fetched_count for state in job.providers
        )
        job.result = SearchStrategyExecutionResponse(
            project_id=job.project_id,
            rendered_query=job.query.to_boolean_query(),
            canonical_query_id=job.query.query_id,
            canonical_version=job.query.version,
            canonical_hash=job.query.canonical_hash,
            provider_queries=[
                ProviderQueryResponse(
                    provider=state.name,
                    rendered_query=state.rendered_query,
                    canonical_query_id=job.query.query_id,
                    canonical_version=job.query.version,
                    canonical_hash=job.query.canonical_hash,
                    physical_endpoint=get_query_renderer(state.name).render(job.query).physical_endpoint,
                    is_lossless=state.lossless,
                    warnings=list(state.warnings),
                    retrieved_count=state.fetched_count,
                    canonical_accepted_count=state.canonical_accepted_count,
                    canonical_rejected_count=state.canonical_rejected_count,
                    canonical_indeterminate_count=state.canonical_indeterminate_count,
                    deduplicated_count=state.deduplicated_count,
                )
                for state in job.providers
            ],
            providers=[state.name for state in job.providers],
            publication_year_from=job.strategy.publication_year_from,
            publication_year_to=job.strategy.publication_year_to,
            executed_at=job.started_at,
            total_count=max(total_count, len(results)),
            returned_count=len(results),
            retrieved_count=sum(state.fetched_count for state in job.providers),
            canonical_accepted_count=sum(state.canonical_accepted_count for state in job.providers),
            canonical_rejected_count=sum(state.canonical_rejected_count for state in job.providers),
            canonical_indeterminate_count=sum(state.canonical_indeterminate_count for state in job.providers),
            deduplicated_count=sum(state.deduplicated_count for state in job.providers),
            next_cursor=None,
            has_more=bool(partial_any or cancelled_any),
            results=results,
            provider_errors=[
                SearchProviderErrorResponse(
                    provider=cast(
                        Literal["openalex", "crossref", "semantic_scholar"],
                        state.name,
                    ),
                    message=(f"Fetch-all stopped early ({state.status}): {state.message}"),
                )
                for state in job.providers
                if state.status in {"failed", "partial"} and state.message is not None
            ],
        )
        job.finished_at = finished_at


fetch_all_service = FetchAllSearchService()
