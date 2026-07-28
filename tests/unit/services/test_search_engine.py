from __future__ import annotations

from typing import Protocol, runtime_checkable
from uuid import UUID

import pytest

from app.domain.publication import Publication
from app.domain.search import SearchQuery, SearchRun, SearchTerm
from app.services.search_engine import SearchEngine, SearchProvider


@runtime_checkable
class RuntimeSearchProvider(SearchProvider, Protocol):
    pass


class FakeSearchProvider:
    name = "fake"

    def __init__(
        self,
        publications: list[Publication] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.publications = publications if publications is not None else []
        self.error = error
        self.calls: list[tuple[SearchRun, SearchQuery]] = []

    async def search(
        self,
        *,
        search_run: SearchRun,
        search_query: SearchQuery,
    ) -> list[Publication]:
        self.calls.append((search_run, search_query))
        if self.error is not None:
            raise self.error
        return self.publications


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def search_query() -> SearchQuery:
    return SearchQuery(
        query_id=UUID("11111111-1111-1111-1111-111111111111"),
        name="Lean manufacturing",
        expression=SearchTerm(value="lean manufacturing"),
        version=3,
    )


@pytest.mark.anyio
async def test_execute_calls_one_provider_once_with_query_and_created_run(
    search_query: SearchQuery,
) -> None:
    publications = [
        Publication(title="First"),
        Publication(title="Second"),
    ]
    provider = FakeSearchProvider(publications)
    run_id = UUID("22222222-2222-2222-2222-222222222222")

    result = await SearchEngine(
        provider=provider,
        run_id_factory=lambda: run_id,
    ).execute(search_query)

    assert len(provider.calls) == 1
    called_run, called_query = provider.calls[0]
    assert called_query is search_query
    assert called_run is result.search_run
    assert called_run.run_id == run_id
    assert called_run.query_id == search_query.query_id
    assert called_run.query_version == search_query.version
    assert called_run.provider == provider.name
    assert called_run.rendered_query == '"lean manufacturing"'
    assert called_run.started_at is None
    assert called_run.finished_at is None


@pytest.mark.anyio
async def test_execute_returns_provider_list_in_order_without_copying(
    search_query: SearchQuery,
) -> None:
    first = Publication(title="First")
    second = Publication(title="Second")
    publications = [first, second]

    result = await SearchEngine(
        provider=FakeSearchProvider(publications),
    ).execute(search_query)

    assert result.publications is publications
    assert result.publications == [first, second]
    assert result.publications[0] is first
    assert result.publications[1] is second


@pytest.mark.anyio
async def test_execute_preserves_empty_provider_result(
    search_query: SearchQuery,
) -> None:
    publications: list[Publication] = []

    result = await SearchEngine(
        provider=FakeSearchProvider(publications),
    ).execute(search_query)

    assert result.publications is publications
    assert result.publications == []


@pytest.mark.anyio
async def test_execute_propagates_provider_exception(
    search_query: SearchQuery,
) -> None:
    error = RuntimeError("provider failed")
    provider = FakeSearchProvider(error=error)

    with pytest.raises(RuntimeError) as exc_info:
        await SearchEngine(provider=provider).execute(search_query)

    assert exc_info.value is error
    assert len(provider.calls) == 1


def test_fake_provider_structurally_satisfies_search_provider() -> None:
    assert isinstance(FakeSearchProvider(), RuntimeSearchProvider)
