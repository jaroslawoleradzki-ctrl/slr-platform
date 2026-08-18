from __future__ import annotations

from typing import Any, Literal
from unittest.mock import patch

import httpx
import pytest

from app.api.dto.search_strategy import ConceptGroupRequest, SearchStrategyExecutionRequest
from app.providers.crossref import CrossrefClient, CrossrefSearchFilters
from app.providers.openalex import OpenAlexClient, OpenAlexSearchFilters
from app.providers.search.crossref import CrossrefProvider
from app.providers.search.openalex import OpenAlexProvider
from app.repositories.project_publication_repository import default_project_publication_repository
from app.services.live_search import LiveSearchService, build_search_query


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def _sample_strategy(
    *, providers: list[Literal["openalex", "crossref"]] | None = None
) -> SearchStrategyExecutionRequest:
    return SearchStrategyExecutionRequest(
        publication_year_from=2020,
        publication_year_to=2025,
        providers=providers or ["crossref"],
        concept_groups=[
            ConceptGroupRequest(
                id="g1",
                name="Lean",
                terms=["lean production", "lean manufacturing"],
            ),
            ConceptGroupRequest(
                id="g2",
                name="Energy",
                terms=["energy efficiency"],
            ),
        ],
        languages=["en", "pl"],
        publication_types=["article", "review"],
        open_access=True,
    )


def test_build_search_query_creates_nested_boolean_tree() -> None:
    strategy = _sample_strategy()
    query = build_search_query(strategy)

    boolean_representation = query.to_boolean_query()
    assert '("lean production" OR "lean manufacturing")' in boolean_representation
    assert '"energy efficiency"' in boolean_representation
    assert " AND " in boolean_representation


def test_build_providers_configures_crossref_filters_and_mailto() -> None:
    strategy = _sample_strategy(providers=["crossref"])

    with patch.dict("os.environ", {"CROSSREF_EMAIL": "test@crossref.example.org"}):
        async_client = httpx.AsyncClient()
        providers = LiveSearchService._build_providers(strategy, async_client)

    assert len(providers) == 1
    crossref_provider = providers[0]
    assert isinstance(crossref_provider, CrossrefProvider)
    assert crossref_provider._paginate is True

    # Verify filters
    filters = crossref_provider._filters
    assert isinstance(filters, CrossrefSearchFilters)
    assert filters.publication_year_from == 2020
    assert filters.publication_year_to == 2025
    assert filters.languages == ("en", "pl")
    assert filters.publication_types == ("article", "review")
    assert filters.open_access is True
    assert filters.is_lossless is False
    assert len(filters.get_warnings()) == 3

    # Verify client
    client = crossref_provider._client
    assert isinstance(client, CrossrefClient)
    assert client._mailto == "test@crossref.example.org"
    assert client._minimum_interval == 1 / 20.0


def test_build_providers_configures_openalex_filters_and_mailto() -> None:
    strategy = _sample_strategy(providers=["openalex"])

    with patch.dict("os.environ", {"OPENALEX_EMAIL": "test@openalex.example.org"}):
        async_client = httpx.AsyncClient()
        providers = LiveSearchService._build_providers(strategy, async_client)

    assert len(providers) == 1
    openalex_provider = providers[0]
    assert isinstance(openalex_provider, OpenAlexProvider)
    assert openalex_provider._paginate is True

    # Verify filters
    filters = openalex_provider._filters
    assert isinstance(filters, OpenAlexSearchFilters)
    assert filters.publication_year_from == 2020
    assert filters.publication_year_to == 2025
    assert filters.languages == ("en", "pl")
    assert filters.publication_types == ("article", "review")
    assert filters.open_access is True

    # Verify client
    client = openalex_provider._client
    assert isinstance(client, OpenAlexClient)
    assert client._mailto == "test@openalex.example.org"


def test_build_providers_handles_blank_or_whitespace_emails() -> None:
    strategy = _sample_strategy(providers=["crossref", "openalex"])

    with patch.dict("os.environ", {"OPENALEX_EMAIL": "   ", "CROSSREF_EMAIL": ""}):
        async_client = httpx.AsyncClient()
        providers = LiveSearchService._build_providers(strategy, async_client)

    assert len(providers) == 2
    crossref_provider = providers[0]
    openalex_provider = providers[1]
    assert isinstance(crossref_provider, CrossrefProvider)
    assert crossref_provider._client._mailto is None
    assert isinstance(openalex_provider, OpenAlexProvider)
    assert openalex_provider._client._mailto is None


@pytest.mark.anyio
async def test_live_search_service_executes_crossref_end_to_end() -> None:
    strategy = _sample_strategy(providers=["crossref"])

    crossref_payload: dict[str, Any] = {
        "status": "ok",
        "message": {
            "total-results": 42,
            "next-cursor": "cursor-page-2",
            "items": [
                {
                    "DOI": "10.1000/lean-energy-1",
                    "title": ["Lean Energy Study 1"],
                    "published": {"date-parts": [[2022, 6, 15]]},
                    "type": "journal-article",
                }
            ],
        },
    }

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "api.crossref.org"
        assert request.url.path == "/works"
        assert request.url.params["filter"] == (
            "from-pub-date:2020-01-01,until-pub-date:2025-12-31,type:journal-article"
        )
        if request.url.params.get("cursor") == "cursor-page-2":
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "message": {
                        "total-results": 42,
                        "next-cursor": None,
                        "items": [],
                    },
                },
                request=request,
            )
        return httpx.Response(200, json=crossref_payload, request=request)

    repo = default_project_publication_repository()
    service = LiveSearchService(repository=repo)

    # Mock httpx transport inside LiveSearchService.execute
    original_async_client = httpx.AsyncClient

    def mock_async_client(**kwargs: Any) -> httpx.AsyncClient:
        kwargs["transport"] = httpx.MockTransport(handler)
        return original_async_client(**kwargs)

    with patch("httpx.AsyncClient", side_effect=mock_async_client):
        execution = await service.execute("lean_energy", strategy)

    assert len(execution.provider_results) == 1
    result = execution.provider_results[0]
    assert result.search_run.provider == "crossref"
    assert result.search_run.records_retrieved == 1
    assert result.total_count == 42
    assert result.next_cursor is None
    assert result.has_more is False

    # Warnings from unsupported filters (languages, open_access, review) + Boolean OR flattening
    warnings = result.search_run.warnings
    assert any("language filtering" in w for w in warnings)
    assert any("open access filtering" in w for w in warnings)
    assert any("review" in w for w in warnings)
    assert any("OR operators" in w for w in warnings)
    assert result.search_run.is_lossless is False

    assert len(execution.normalized_publications) == 1
    pub = execution.normalized_publications[0]
    assert pub.title == "Lean Energy Study 1"
    assert pub.publication_year == 2022
    assert pub.identifiers[0].value == "10.1000/lean-energy-1"
    assert pub.provenance[0].source == "crossref"
