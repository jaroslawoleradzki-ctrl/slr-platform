from unittest.mock import AsyncMock

import pytest

from app.domain.publication import Publication
from app.domain.search import BooleanOperator, SearchGroup, SearchQuery, SearchTerm
from app.providers.search.base import ProviderSearchOutput
from app.services.live_search import _InMemoryRawResponseArchive
from app.services.search_engine import SearchEngine


@pytest.mark.anyio
async def test_search_engine_provider_specific_rendered_queries() -> None:
    query = SearchQuery(
        name="Test Integration Query",
        expression=SearchGroup(
            operator=BooleanOperator.AND,
            children=[
                SearchGroup(
                    operator=BooleanOperator.OR,
                    children=[
                        SearchTerm(value="lean management", exact_phrase=True),
                        SearchTerm(value="lean manufacturing", exact_phrase=True),
                    ],
                ),
                SearchTerm(value="sustainability"),
            ],
        ),
    )

    openalex_provider = AsyncMock()
    openalex_provider.name = "openalex"
    openalex_provider.search_with_raw = AsyncMock(
        return_value=ProviderSearchOutput(
            publications=[Publication(title="Lean management sustainability", publication_year=2024)],
            raw_responses=[{"id": "W1"}],
            total_count=1,
            has_more=False,
        )
    )

    crossref_provider = AsyncMock()
    crossref_provider.name = "crossref"
    crossref_provider.search_with_raw = AsyncMock(
        return_value=ProviderSearchOutput(
            publications=[Publication(title="Lean management sustainability", publication_year=2024)],
            raw_responses=[{"id": "CR1"}],
            total_count=1,
            has_more=False,
        )
    )

    semantic_scholar_provider = AsyncMock()
    semantic_scholar_provider.name = "semantic_scholar"
    semantic_scholar_provider.search_with_raw = AsyncMock(
        return_value=ProviderSearchOutput(
            publications=[Publication(title="Lean management sustainability", publication_year=2024)],
            raw_responses=[{"paperId": "S2-1"}],
            total_count=1,
            has_more=False,
        )
    )

    archive = _InMemoryRawResponseArchive()
    engine = SearchEngine(
        providers=[openalex_provider, crossref_provider, semantic_scholar_provider],
        raw_response_archive=archive,
    )

    execution = await engine.execute(query)

    # Check OpenAlex executed query
    openalex_call_kwargs = openalex_provider.search_with_raw.call_args.kwargs
    openalex_search_run = openalex_call_kwargs["search_run"]
    assert openalex_search_run.provider == "openalex"
    assert openalex_search_run.rendered_query == '(("lean management" OR "lean manufacturing") AND sustainability)'

    # Check Crossref executed query
    crossref_call_kwargs = crossref_provider.search_with_raw.call_args.kwargs
    crossref_search_run = crossref_call_kwargs["search_run"]
    assert crossref_search_run.provider == "crossref"
    assert crossref_search_run.rendered_query == "sustainability"

    semantic_scholar_call_kwargs = semantic_scholar_provider.search_with_raw.call_args.kwargs
    semantic_scholar_search_run = semantic_scholar_call_kwargs["search_run"]
    assert semantic_scholar_search_run.provider == "semantic_scholar"
    assert semantic_scholar_search_run.rendered_query == '(("lean management" | "lean manufacturing") + sustainability)'
    assert semantic_scholar_search_run.is_lossless is True

    # Verify that the two search runs have different rendered_query strings for the same SearchQuery!
    assert openalex_search_run.rendered_query != crossref_search_run.rendered_query

    # Verify provider results in SearchExecution
    assert len(execution.provider_results) == 3
    assert execution.provider_results[0].search_run.rendered_query == openalex_search_run.rendered_query
    assert execution.provider_results[1].search_run.rendered_query == crossref_search_run.rendered_query
    assert execution.provider_results[2].search_run.rendered_query == semantic_scholar_search_run.rendered_query


@pytest.mark.anyio
async def test_search_engine_partial_failure_preserves_rendered_queries() -> None:
    query = SearchQuery(
        name="Test Partial Failure",
        expression=SearchTerm(value="machine learning", exact_phrase=True),
    )

    openalex_provider = AsyncMock()
    openalex_provider.name = "openalex"
    openalex_provider.search_with_raw = AsyncMock(side_effect=RuntimeError("OpenAlex HTTP 500 Server Error"))

    crossref_provider = AsyncMock()
    crossref_provider.name = "crossref"
    crossref_provider.search_with_raw = AsyncMock(
        return_value=ProviderSearchOutput(
            publications=[Publication(title="Crossref Work 1", publication_year=2024)],
            raw_responses=[{"id": "CR1"}],
            total_count=1,
            has_more=False,
        )
    )

    archive = _InMemoryRawResponseArchive()
    engine = SearchEngine(
        providers=[openalex_provider, crossref_provider],
        raw_response_archive=archive,
    )

    execution = await engine.execute(query)

    assert len(execution.provider_results) == 2
    assert execution.provider_results[0].search_run.provider == "openalex"
    assert execution.provider_results[0].search_run.rendered_query == '"machine learning"'
    assert execution.provider_results[0].search_run.errors == ["RuntimeError: OpenAlex HTTP 500 Server Error"]

    assert execution.provider_results[1].search_run.provider == "crossref"
    assert execution.provider_results[1].search_run.rendered_query == '"machine learning"'
    assert execution.provider_results[1].search_run.errors == []
