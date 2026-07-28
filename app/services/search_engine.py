from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol
from uuid import UUID, uuid4

from app.domain.publication import Publication
from app.domain.search import SearchQuery, SearchRun
from app.providers.search.base import ProviderSearchOutput
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


@dataclass(frozen=True, slots=True)
class SearchExecution:
    """Ordered, separate results from one sequential provider execution."""

    provider_results: list[ProviderSearchResult]


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
    ) -> None:
        self._providers = tuple(providers)
        self._raw_response_archive = raw_response_archive
        self._run_id_factory = run_id_factory
        self._archive_id_factory = archive_id_factory
        self._clock = clock

    async def execute(self, search_query: SearchQuery) -> SearchExecution:
        """Execute providers sequentially and preserve separate result identity."""

        provider_results: list[ProviderSearchResult] = []
        for provider in self._providers:
            search_run = SearchRun(
                run_id=self._run_id_factory(),
                query_id=search_query.query_id,
                query_version=search_query.version,
                provider=provider.name,
                rendered_query=search_query.to_boolean_query(),
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
                provider_results.append(
                    ProviderSearchResult(
                        search_run=search_run,
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
                provider_results.append(
                    ProviderSearchResult(
                        search_run=search_run,
                        publications=output.publications,
                        error=None,
                    )
                )
        return SearchExecution(provider_results=provider_results)
