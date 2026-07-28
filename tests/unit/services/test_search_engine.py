from __future__ import annotations

from datetime import datetime, timezone
from typing import Protocol, runtime_checkable
from uuid import UUID

import pytest

from app.domain.publication import Publication
from app.domain.search import SearchQuery, SearchRun, SearchTerm
from app.providers.search.base import JsonObject, ProviderSearchOutput
from app.services.search_engine import (
    ProviderSearchResult,
    SearchEngine,
    SearchProvider,
)
from app.storage.raw_response_archive import (
    RawResponseArchiveEntry,
    RawResponseStatus,
)

_CAPTURED_AT = datetime(2026, 7, 28, 12, 0, tzinfo=timezone.utc)


@runtime_checkable
class RuntimeSearchProvider(SearchProvider, Protocol):
    pass


class FakeSearchProvider:
    def __init__(
        self,
        name: str,
        publications: list[Publication] | None = None,
        raw_responses: list[JsonObject] | None = None,
        error: Exception | None = None,
        call_order: list[str] | None = None,
    ) -> None:
        self.name = name
        self.publications = publications if publications is not None else []
        self.raw_responses = raw_responses if raw_responses is not None else []
        self.error = error
        self.call_order = call_order
        self.calls: list[tuple[SearchRun, SearchQuery]] = []

    async def search_with_raw(
        self,
        *,
        search_run: SearchRun,
        search_query: SearchQuery,
    ) -> ProviderSearchOutput:
        self.calls.append((search_run, search_query))
        if self.call_order is not None:
            self.call_order.append(self.name)
        if self.error is not None:
            raise self.error
        return ProviderSearchOutput(
            publications=self.publications,
            raw_responses=self.raw_responses,
        )


class FakeRawResponseArchive:
    def __init__(self, error: Exception | None = None) -> None:
        self.entries: list[RawResponseArchiveEntry] = []
        self.error = error

    async def save(self, entry: RawResponseArchiveEntry) -> None:
        if self.error is not None:
            raise self.error
        self.entries.append(entry)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def archive() -> FakeRawResponseArchive:
    return FakeRawResponseArchive()


@pytest.fixture
def search_query() -> SearchQuery:
    return SearchQuery(
        query_id=UUID("11111111-1111-1111-1111-111111111111"),
        name="Lean manufacturing",
        expression=SearchTerm(value="lean manufacturing"),
        version=3,
    )


@pytest.fixture
def search_run(search_query: SearchQuery) -> SearchRun:
    return SearchRun(
        run_id=UUID("22222222-2222-2222-2222-222222222222"),
        query_id=search_query.query_id,
        query_version=search_query.version,
        provider="fake",
        rendered_query=search_query.to_boolean_query(),
    )


def test_provider_result_rejects_missing_publications_and_error(
    search_run: SearchRun,
) -> None:
    with pytest.raises(
        ValueError,
        match="must contain either publications or an error",
    ):
        ProviderSearchResult(
            search_run=search_run,
            publications=None,
            error=None,
        )


def test_provider_result_rejects_publications_and_error_together(
    search_run: SearchRun,
) -> None:
    with pytest.raises(
        ValueError,
        match="must contain either publications or an error",
    ):
        ProviderSearchResult(
            search_run=search_run,
            publications=[],
            error=RuntimeError("failure"),
        )


@pytest.mark.anyio
async def test_execute_calls_all_providers_in_order_with_separate_runs(
    search_query: SearchQuery,
    archive: FakeRawResponseArchive,
) -> None:
    call_order: list[str] = []
    providers = [
        FakeSearchProvider("first", call_order=call_order),
        FakeSearchProvider("second", call_order=call_order),
        FakeSearchProvider("third", call_order=call_order),
    ]
    run_ids = iter(
        [
            UUID("22222222-2222-2222-2222-222222222222"),
            UUID("33333333-3333-3333-3333-333333333333"),
            UUID("44444444-4444-4444-4444-444444444444"),
        ]
    )

    result = await SearchEngine(
        providers=providers,
        raw_response_archive=archive,
        run_id_factory=lambda: next(run_ids),
    ).execute(search_query)

    assert call_order == ["first", "second", "third"]
    assert [len(provider.calls) for provider in providers] == [1, 1, 1]
    assert len(result.provider_results) == 3
    assert len(archive.entries) == 3
    assert [
        provider_result.search_run.run_id
        for provider_result in result.provider_results
    ] == [
        UUID("22222222-2222-2222-2222-222222222222"),
        UUID("33333333-3333-3333-3333-333333333333"),
        UUID("44444444-4444-4444-4444-444444444444"),
    ]
    assert [entry.search_run_id for entry in archive.entries] == [
        provider_result.search_run.run_id
        for provider_result in result.provider_results
    ]
    assert len(
        {
            provider_result.search_run.run_id
            for provider_result in result.provider_results
        }
    ) == 3
    for provider, provider_result in zip(
        providers,
        result.provider_results,
        strict=True,
    ):
        called_run, called_query = provider.calls[0]
        assert called_query is search_query
        assert called_run is provider_result.search_run
        assert called_run.query_id == search_query.query_id
        assert called_run.query_version == search_query.version
        assert called_run.provider == provider.name
        assert called_run.rendered_query == '"lean manufacturing"'
        assert called_run.started_at is None
        assert called_run.finished_at is None
        assert provider_result.publications is provider.publications
        assert provider_result.error is None


@pytest.mark.anyio
async def test_execute_keeps_provider_results_separate_without_copying(
    search_query: SearchQuery,
    archive: FakeRawResponseArchive,
) -> None:
    first = Publication(title="First")
    second = Publication(title="Second")
    third = Publication(title="Third")
    first_publications = [first, second]
    second_publications = [third]

    result = await SearchEngine(
        providers=[
            FakeSearchProvider("first", first_publications),
            FakeSearchProvider("second", second_publications),
        ],
        raw_response_archive=archive,
    ).execute(search_query)

    assert result.provider_results[0].publications is first_publications
    assert result.provider_results[1].publications is second_publications
    assert result.provider_results[0].error is None
    assert result.provider_results[1].error is None
    assert result.provider_results[0].publications == [first, second]
    assert result.provider_results[1].publications == [third]
    assert result.provider_results[0].publications[0] is first
    assert result.provider_results[0].publications[1] is second
    assert result.provider_results[1].publications[0] is third


@pytest.mark.anyio
async def test_execute_preserves_empty_provider_result(
    search_query: SearchQuery,
    archive: FakeRawResponseArchive,
) -> None:
    publications: list[Publication] = []

    result = await SearchEngine(
        providers=[FakeSearchProvider("empty", publications)],
        raw_response_archive=archive,
    ).execute(search_query)

    assert result.provider_results[0].publications is publications
    assert result.provider_results[0].publications == []
    assert result.provider_results[0].error is None


@pytest.mark.anyio
async def test_execute_continues_after_error_and_preserves_partial_results(
    search_query: SearchQuery,
    archive: FakeRawResponseArchive,
) -> None:
    error = RuntimeError("provider failed")
    call_order: list[str] = []
    first_publications = [Publication(title="First result")]
    third_publications = [Publication(title="Third result")]
    first = FakeSearchProvider(
        "first",
        first_publications,
        raw_responses=[{"page": 1}],
        call_order=call_order,
    )
    second = FakeSearchProvider(
        "second",
        error=error,
        call_order=call_order,
    )
    third = FakeSearchProvider(
        "third",
        third_publications,
        raw_responses=[{"page": 3}],
        call_order=call_order,
    )

    result = await SearchEngine(
        providers=[first, second, third],
        raw_response_archive=archive,
    ).execute(search_query)

    assert call_order == ["first", "second", "third"]
    assert len(first.calls) == 1
    assert len(second.calls) == 1
    assert len(third.calls) == 1
    assert result.provider_results[0].publications is first_publications
    assert result.provider_results[0].error is None
    assert result.provider_results[1].publications is None
    assert result.provider_results[1].error is error
    assert result.provider_results[2].publications is third_publications
    assert result.provider_results[2].error is None
    assert [entry.status for entry in archive.entries] == [
        RawResponseStatus.SUCCESS,
        RawResponseStatus.FAILED,
        RawResponseStatus.SUCCESS,
    ]
    assert archive.entries[0].responses == [{"page": 1}]
    assert archive.entries[1].responses == []
    assert archive.entries[1].error_type == "RuntimeError"
    assert archive.entries[1].error_message == "provider failed"
    assert archive.entries[2].responses == [{"page": 3}]


@pytest.mark.anyio
async def test_execute_archives_success_with_deterministic_metadata(
    search_query: SearchQuery,
) -> None:
    archive = FakeRawResponseArchive()
    publications = [Publication(title="Result")]
    raw_pages: list[JsonObject] = [
        {"page": 1, "items": [{"id": "one"}]},
        {"page": 2, "items": [{"id": "two"}]},
    ]
    run_id = UUID("22222222-2222-2222-2222-222222222222")
    archive_id = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")

    result = await SearchEngine(
        providers=[
            FakeSearchProvider(
                "fake",
                publications,
                raw_responses=raw_pages,
            )
        ],
        raw_response_archive=archive,
        run_id_factory=lambda: run_id,
        archive_id_factory=lambda: archive_id,
        clock=lambda: _CAPTURED_AT,
    ).execute(search_query)

    assert result.provider_results[0].publications is publications
    assert len(archive.entries) == 1
    entry = archive.entries[0]
    assert entry.archive_id == archive_id
    assert entry.search_run_id == run_id
    assert entry.provider == "fake"
    assert entry.rendered_query == '"lean manufacturing"'
    assert entry.captured_at == _CAPTURED_AT
    assert entry.status is RawResponseStatus.SUCCESS
    assert entry.responses is raw_pages
    assert entry.responses == raw_pages
    assert entry.error_type is None
    assert entry.error_message is None


@pytest.mark.anyio
async def test_archive_failure_is_propagated_and_stops_execution(
    search_query: SearchQuery,
) -> None:
    archive_error = RuntimeError("archive unavailable")
    archive = FakeRawResponseArchive(error=archive_error)
    first = FakeSearchProvider("first")
    second = FakeSearchProvider("second")

    with pytest.raises(RuntimeError) as exc_info:
        await SearchEngine(
            providers=[first, second],
            raw_response_archive=archive,
        ).execute(search_query)

    assert exc_info.value is archive_error
    assert len(first.calls) == 1
    assert second.calls == []
    assert archive.entries == []


@pytest.mark.anyio
async def test_engine_uses_original_provider_sequence_after_list_mutation(
    search_query: SearchQuery,
    archive: FakeRawResponseArchive,
) -> None:
    first = FakeSearchProvider("first")
    second = FakeSearchProvider("second")
    providers = [first]
    engine = SearchEngine(
        providers=providers,
        raw_response_archive=archive,
    )
    providers.clear()
    providers.append(second)

    result = await engine.execute(search_query)

    assert len(first.calls) == 1
    assert second.calls == []
    assert len(result.provider_results) == 1
    assert result.provider_results[0].search_run.provider == "first"


@pytest.mark.anyio
async def test_execute_with_no_providers_returns_empty_result(
    search_query: SearchQuery,
    archive: FakeRawResponseArchive,
) -> None:
    result = await SearchEngine(
        providers=[],
        raw_response_archive=archive,
    ).execute(search_query)

    assert result.provider_results == []
    assert archive.entries == []


def test_fake_provider_structurally_satisfies_search_provider() -> None:
    assert isinstance(FakeSearchProvider("fake"), RuntimeSearchProvider)
