from __future__ import annotations

from collections.abc import Callable
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
class SearchExecution:
    """One search run and the provider-owned canonical results."""

    search_run: SearchRun
    publications: list[Publication]


class SearchEngine:
    """Orchestrate one canonical query through one explicit provider."""

    def __init__(
        self,
        *,
        provider: SearchProvider,
        run_id_factory: Callable[[], UUID] = uuid4,
    ) -> None:
        self._provider = provider
        self._run_id_factory = run_id_factory

    async def execute(self, search_query: SearchQuery) -> SearchExecution:
        """Execute a canonical query once and preserve provider result identity."""

        search_run = SearchRun(
            run_id=self._run_id_factory(),
            query_id=search_query.query_id,
            query_version=search_query.version,
            provider=self._provider.name,
            rendered_query=search_query.to_boolean_query(),
        )
        publications = await self._provider.search(
            search_run=search_run,
            search_query=search_query,
        )
        return SearchExecution(
            search_run=search_run,
            publications=publications,
        )
