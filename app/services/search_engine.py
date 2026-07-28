from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol
from uuid import UUID, uuid4

from app.domain.publication import Publication
from app.domain.search import SearchQuery, SearchRun, SearchRunStatus
from app.domain.search_provenance import (
    PublicationSearchProvenance,
    SearchExecutionProvenance,
)
from app.providers.search.base import ProviderSearchOutput
from app.services.result_merger import ResultMerger
from app.storage.raw_response_archive import (
    RawResponseArchive,
    RawResponseArchiveEntry,
    RawResponseStatus,
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class SearchProvider(Protocol):
    """Minimal structural contract for one canonical search execution."""

    name: str

    async def search_with_raw(
        self,
        *,
        search_run: SearchRun,
        search_query: SearchQuery,
    ) -> ProviderSearchOutput: ...


@dataclass(frozen=True, slots=True)
class ProviderSearchResult:
    """One provider run with either canonical results or its original error."""

    search_run: SearchRun
    publications: list[Publication] | None
    error: Exception | None

    def __post_init__(self) -> None:
        if (self.publications is None) == (self.error is None):
            raise ValueError(
                "ProviderSearchResult must contain either publications or an error"
            )

    @property
    def duration_seconds(self) -> float:
        if self.search_run.started_at is None or self.search_run.finished_at is None:
            raise ValueError("completed provider results require run timestamps")
        return (
            self.search_run.finished_at - self.search_run.started_at
        ).total_seconds()


@dataclass(frozen=True, slots=True)
class SearchExecution:
    """Ordered, separate results from one sequential provider execution."""

    provider_results: list[ProviderSearchResult]
    merged_publications: list[Publication]
    result_provenance: list[PublicationSearchProvenance]
    execution_provenance: SearchExecutionProvenance


class SearchEngine:
    """Orchestrate one canonical query through explicit providers."""

    def __init__(
        self,
        *,
        providers: Sequence[SearchProvider],
        raw_response_archive: RawResponseArchive,
        run_id_factory: Callable[[], UUID] = uuid4,
        archive_id_factory: Callable[[], UUID] = uuid4,
        clock: Callable[[], datetime] = _utc_now,
        result_merger: ResultMerger | None = None,
    ) -> None:
        self._providers = tuple(providers)
        self._raw_response_archive = raw_response_archive
        self._run_id_factory = run_id_factory
        self._archive_id_factory = archive_id_factory
        self._clock = clock
        self._result_merger = (
            result_merger if result_merger is not None else ResultMerger()
        )

    async def execute(self, search_query: SearchQuery) -> SearchExecution:
        """Execute providers sequentially and preserve separate result identity."""

        execution_started_at = self._clock()
        provider_results: list[ProviderSearchResult] = []
        result_provenance: list[PublicationSearchProvenance] = []
        for provider in self._providers:
            provider_started_at = self._clock()
            search_run = SearchRun(
                run_id=self._run_id_factory(),
                query_id=search_query.query_id,
                query_version=search_query.version,
                provider=provider.name,
                rendered_query=search_query.to_boolean_query(),
                status=SearchRunStatus.RUNNING,
                started_at=provider_started_at,
            )
            try:
                output = await provider.search_with_raw(
                    search_run=search_run,
                    search_query=search_query,
                )
            except Exception as error:
                await self._raw_response_archive.save(
                    RawResponseArchiveEntry(
                        archive_id=self._archive_id_factory(),
                        search_run_id=search_run.run_id,
                        provider=search_run.provider,
                        rendered_query=search_run.rendered_query,
                        captured_at=self._clock(),
                        status=RawResponseStatus.FAILED,
                        responses=[],
                        error_type=type(error).__name__,
                        error_message=str(error),
                    )
                )
                final_search_run = self._finish_search_run(
                    search_run,
                    status=SearchRunStatus.FAILED,
                    finished_at=self._clock(),
                    records_retrieved=0,
                    errors=[f"{type(error).__name__}: {error}"],
                )
                provider_results.append(
                    ProviderSearchResult(
                        search_run=final_search_run,
                        publications=None,
                        error=error,
                    )
                )
            else:
                await self._raw_response_archive.save(
                    RawResponseArchiveEntry(
                        archive_id=self._archive_id_factory(),
                        search_run_id=search_run.run_id,
                        provider=search_run.provider,
                        rendered_query=search_run.rendered_query,
                        captured_at=self._clock(),
                        status=RawResponseStatus.SUCCESS,
                        responses=output.raw_responses,
                    )
                )
                final_search_run = self._finish_search_run(
                    search_run,
                    status=SearchRunStatus.COMPLETED,
                    finished_at=self._clock(),
                    records_retrieved=len(output.publications),
                    errors=[],
                )
                provider_results.append(
                    ProviderSearchResult(
                        search_run=final_search_run,
                        publications=output.publications,
                        error=None,
                    )
                )
                result_provenance.extend(
                    PublicationSearchProvenance(
                        publication=publication,
                        search_run=final_search_run,
                        provider=final_search_run.provider,
                    )
                    for publication in output.publications
                )
        merged_publications = self._result_merger.merge(
            publication
            for provider_result in provider_results
            if provider_result.publications is not None
            for publication in provider_result.publications
        )
        execution_finished_at = self._clock()
        return SearchExecution(
            provider_results=provider_results,
            merged_publications=merged_publications,
            result_provenance=result_provenance,
            execution_provenance=SearchExecutionProvenance(
                started_at=execution_started_at,
                finished_at=execution_finished_at,
                provider_run_ids=tuple(
                    result.search_run.run_id for result in provider_results
                ),
                total_provider_results=sum(
                    len(result.publications)
                    for result in provider_results
                    if result.publications is not None
                ),
                merged_result_count=len(merged_publications),
            ),
        )

    @staticmethod
    def _finish_search_run(
        search_run: SearchRun,
        *,
        status: SearchRunStatus,
        finished_at: datetime,
        records_retrieved: int,
        errors: list[str],
    ) -> SearchRun:
        data = search_run.model_dump()
        data.update(
            status=status,
            finished_at=finished_at,
            records_retrieved=records_retrieved,
            error_count=len(errors),
            errors=errors,
        )
        return SearchRun.model_validate(data)
