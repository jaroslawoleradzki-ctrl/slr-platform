from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID, uuid4

from app.domain.publication import Publication
from app.domain.search import SearchQuery, SearchRun


class SearchProvider(Protocol):
    """Minimal structural contract for one canonical search execution."""

    name: str

    async def search(
        self,
        *,
        search_run: SearchRun,
        search_query: SearchQuery,
    ) -> list[Publication]: ...


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
        run_id_factory: Callable[[], UUID] = uuid4,
    ) -> None:
        self._providers = tuple(providers)
        self._run_id_factory = run_id_factory

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
                publications = await provider.search(
                    search_run=search_run,
                    search_query=search_query,
                )
            except Exception as error:
                provider_results.append(
                    ProviderSearchResult(
                        search_run=search_run,
                        publications=None,
                        error=error,
                    )
                )
            else:
                provider_results.append(
                    ProviderSearchResult(
                        search_run=search_run,
                        publications=publications,
                        error=None,
                    )
                )
        return SearchExecution(provider_results=provider_results)
