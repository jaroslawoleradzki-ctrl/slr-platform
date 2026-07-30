from __future__ import annotations

from datetime import datetime, timezone
from typing import Protocol

import httpx

from app.api.dto.search_strategy import SearchStrategyExecutionRequest
from app.domain.search import (
    BooleanOperator,
    SearchExpression,
    SearchGroup,
    SearchQuery,
    SearchTerm,
)
from app.providers.crossref import CrossrefClient
from app.providers.openalex import OpenAlexClient, OpenAlexSearchFilters
from app.providers.search.crossref import CrossrefProvider
from app.providers.search.openalex import OpenAlexProvider
from app.repositories.project_publication_repository import (
    ProjectPublicationRepository,
    demo_project_publication_repository,
)
from app.services.search_engine import SearchEngine, SearchExecution, SearchProvider
from app.storage.raw_response_archive import RawResponseArchiveEntry


class _InMemoryRawResponseArchive:
    """Request-process archive used until durable raw-response storage exists."""

    def __init__(self) -> None:
        self.entries: list[RawResponseArchiveEntry] = []

    async def save(self, entry: RawResponseArchiveEntry) -> None:
        self.entries.append(entry)


class LiveSearchExecutor(Protocol):
    async def execute(
        self,
        project_id: str,
        strategy: SearchStrategyExecutionRequest,
    ) -> SearchExecution: ...


def build_search_query(strategy: SearchStrategyExecutionRequest) -> SearchQuery:
    group_expressions: list[SearchExpression] = []
    for group in strategy.concept_groups:
        terms: list[SearchExpression] = [
            SearchTerm(value=term, exact_phrase=True)
            for term in group.terms
        ]
        group_expressions.append(
            terms[0]
            if len(terms) == 1
            else SearchGroup(operator=BooleanOperator.OR, children=terms)
        )
    expression: SearchExpression = (
        group_expressions[0]
        if len(group_expressions) == 1
        else SearchGroup(
            operator=BooleanOperator.AND,
            children=group_expressions,
        )
    )
    return SearchQuery(
        name="Search strategy execution",
        expression=expression,
        created_at=datetime.now(timezone.utc),
    )


class LiveSearchService:
    """Thin adapter connecting the REST workflow to the existing SearchEngine."""

    def __init__(
        self,
        repository: ProjectPublicationRepository = demo_project_publication_repository,
    ) -> None:
        self._repository = repository

    async def execute(
        self,
        project_id: str,
        strategy: SearchStrategyExecutionRequest,
    ) -> SearchExecution:
        self._repository.get_publications(project_id)
        async with httpx.AsyncClient(timeout=30.0) as http_client:
            providers = self._build_providers(strategy, http_client)
            engine = SearchEngine(
                providers=providers,
                raw_response_archive=_InMemoryRawResponseArchive(),
            )
            return await engine.execute(
                build_search_query(strategy),
                cursor=strategy.cursor or "*",
            )

    @staticmethod
    def _build_providers(
        strategy: SearchStrategyExecutionRequest,
        http_client: httpx.AsyncClient,
    ) -> list[SearchProvider]:
        providers: list[SearchProvider] = []
        for name in strategy.providers:
            if name == "openalex":
                providers.append(
                    OpenAlexProvider(
                        client=OpenAlexClient(http_client=http_client),
                        paginate=True,
                        filters=OpenAlexSearchFilters(
                            publication_year_from=strategy.publication_year_from,
                            publication_year_to=strategy.publication_year_to,
                            languages=tuple(strategy.languages),
                            publication_types=tuple(strategy.publication_types),
                            open_access=strategy.open_access,
                        ),
                    )
                )
            elif name == "crossref":
                providers.append(
                    CrossrefProvider(
                        client=CrossrefClient(http_client=http_client),
                        paginate=True,
                    )
                )
        return providers


live_search_service = LiveSearchService()
