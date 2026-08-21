from __future__ import annotations

import os
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
from app.providers.crossref import CrossrefClient, CrossrefSearchFilters
from app.providers.openalex import OpenAlexClient, OpenAlexSearchFilters
from app.providers.search.crossref import CrossrefProvider
from app.providers.search.openalex import OpenAlexProvider
from app.providers.search.semantic_scholar import SemanticScholarProvider
from app.providers.semantic_scholar import (
    SemanticScholarClient,
    SemanticScholarSearchFilters,
)
from app.repositories.project_publication_repository import (
    ProjectPublicationRepository,
    default_project_publication_repository,
)
from app.services.search_engine import SearchEngine, SearchExecution, SearchProvider
from app.storage.raw_response_archive import RawResponseArchiveEntry


class _InMemoryRawResponseArchive:
    """Request-scoped in-memory archive used during the execution lifecycle.

    NOTE/LIMITATION: Raw JSON responses are held in memory for the duration of
    one search execution request. Mapped publication records and search run
    provenance are durably persisted in SQLite via SearchResultSnapshotRepository.
    TODO: Implement a durable raw response storage backend (e.g. SQLite blob or
    compressed filesystem store) if long-term raw API response archiving is required.
    """

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
        repository: ProjectPublicationRepository | None = None,
    ) -> None:
        self._repository = repository or default_project_publication_repository()

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
        openalex_email = (
            (os.getenv("OPENALEX_EMAIL") or "").strip()
            or (os.getenv("CROSSREF_EMAIL") or "").strip()
            or None
        )
        crossref_email = (
            (os.getenv("CROSSREF_EMAIL") or "").strip()
            or (os.getenv("OPENALEX_EMAIL") or "").strip()
            or None
        )

        for name in strategy.providers:
            if name == "openalex":
                providers.append(
                    OpenAlexProvider(
                        client=OpenAlexClient(
                            http_client=http_client,
                            mailto=openalex_email,
                        ),
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
                        client=CrossrefClient(
                            http_client=http_client,
                            mailto=crossref_email,
                            requests_per_second=20.0,
                        ),
                        paginate=True,
                        filters=CrossrefSearchFilters(
                            publication_year_from=strategy.publication_year_from,
                            publication_year_to=strategy.publication_year_to,
                            languages=tuple(strategy.languages),
                            publication_types=tuple(strategy.publication_types),
                            open_access=strategy.open_access,
                        ),
                    )
                )
            elif name == "semantic_scholar":
                semantic_scholar_api_key = (
                    (os.getenv("SEMANTIC_SCHOLAR_API_KEY") or "").strip() or None
                )
                providers.append(
                    SemanticScholarProvider(
                        client=SemanticScholarClient(
                            http_client=http_client,
                            api_key=semantic_scholar_api_key,
                            requests_per_second=1.0,
                        ),
                        paginate=True,
                        filters=SemanticScholarSearchFilters(
                            publication_year_from=strategy.publication_year_from,
                            publication_year_to=strategy.publication_year_to,
                            languages=tuple(strategy.languages),
                            publication_types=tuple(strategy.publication_types),
                            open_access=strategy.open_access,
                        ),
                    )
                )
        return providers


live_search_service = LiveSearchService()
