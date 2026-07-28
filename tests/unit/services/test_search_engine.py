from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timedelta, timezone
from typing import Protocol, runtime_checkable
from uuid import UUID

import pytest

from app.domain.identifiers import Identifier, IdentifierType
from app.domain.publication import Publication
from app.domain.search import SearchQuery, SearchRun, SearchRunStatus, SearchTerm
from app.providers.search.base import JsonObject, ProviderSearchOutput
from app.services.search_engine import (
    ProviderSearchResult,
    SearchEngine,
    SearchProvider,
)
from app.services.result_merger import ResultMerger
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


class SpyResultMerger(ResultMerger):
    def __init__(self) -> None:
        self.calls: list[list[Publication]] = []

    def merge(
        self,
        publications: Iterable[Publication],
    ) -> list[Publication]:
        captured = list(publications)
        self.calls.append(captured)
        return super().merge(captured)


class FakeClock:
    def __init__(self, values: list[datetime]) -> None:
        self._values = iter(values)
        self.calls: list[datetime] = []

    def __call__(self) -> datetime:
        value = next(self._values)
        self.calls.append(value)
        return value


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
    assert result.merged_publications == [
        provider.publications[0]
        for provider in providers
        if provider.publications
    ]
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
        assert called_run is not provider_result.search_run
        assert called_run.run_id == provider_result.search_run.run_id
        assert called_run.query_id == search_query.query_id
        assert called_run.query_version == search_query.version
        assert called_run.provider == provider.name
        assert called_run.rendered_query == '"lean manufacturing"'
        assert called_run.status is SearchRunStatus.RUNNING
        assert called_run.started_at is not None
        assert called_run.finished_at is None
        assert provider_result.search_run.status is SearchRunStatus.COMPLETED
        assert provider_result.search_run.finished_at is not None
        assert provider_result.search_run.records_retrieved == 0
        assert provider_result.search_run.error_count == 0
        assert provider_result.search_run.errors == []
        assert provider_result.publications is not provider.publications
        assert provider_result.error is None


@pytest.mark.anyio
async def test_execute_keeps_normalized_provider_results_separate(
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

    first_results = result.provider_results[0].publications
    second_results = result.provider_results[1].publications
    assert first_results is not None
    assert second_results is not None
    assert first_results is not first_publications
    assert second_results is not second_publications
    assert result.provider_results[0].error is None
    assert result.provider_results[1].error is None
    assert [publication.title for publication in first_results] == [
        "First",
        "Second",
    ]
    assert [publication.title for publication in second_results] == ["Third"]
    assert first_results[0] is not first
    assert first_results[1] is not second
    assert second_results[0] is not third
    assert result.merged_publications == [
        first_results[0],
        first_results[1],
        second_results[0],
    ]
    assert [item.publication for item in result.result_provenance] == [
        first_results[0],
        first_results[1],
        second_results[0],
    ]
    assert result.result_provenance[0].publication is first_results[0]
    assert result.result_provenance[1].publication is first_results[1]
    assert result.result_provenance[2].publication is second_results[0]


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

    assert result.provider_results[0].publications is not publications
    assert result.provider_results[0].publications == []
    assert result.provider_results[0].error is None
    assert result.merged_publications == []
    assert result.result_provenance == []


@pytest.mark.anyio
async def test_execute_continues_after_error_and_preserves_partial_results(
    search_query: SearchQuery,
    archive: FakeRawResponseArchive,
) -> None:
    error = RuntimeError("provider failed")
    call_order: list[str] = []
    first_result = Publication(
        title="First result",
        identifiers=[
            Identifier(type=IdentifierType.DOI, value="10.1000/shared")
        ],
    )
    duplicate = Publication(
        title="Duplicate result",
        identifiers=[
            Identifier(type=IdentifierType.DOI, value="10.1000/SHARED")
        ],
    )
    no_doi = Publication(title="Third result without DOI")
    first_publications = [first_result]
    third_publications = [duplicate, no_doi]
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
    first_results = result.provider_results[0].publications
    third_results = result.provider_results[2].publications
    assert first_results is not None
    assert third_results is not None
    assert first_results is not first_publications
    assert result.provider_results[0].error is None
    assert result.provider_results[1].publications is None
    assert result.provider_results[1].error is error
    assert third_results is not third_publications
    assert result.provider_results[2].error is None
    assert result.merged_publications == [first_results[0], third_results[1]]
    assert result.merged_publications[0] is first_results[0]
    assert result.merged_publications[1] is third_results[1]
    assert [
        provider_result.search_run.status
        for provider_result in result.provider_results
    ] == [
        SearchRunStatus.COMPLETED,
        SearchRunStatus.FAILED,
        SearchRunStatus.COMPLETED,
    ]
    assert [
        provider_result.search_run.records_retrieved
        for provider_result in result.provider_results
    ] == [1, 0, 2]
    failed_run = result.provider_results[1].search_run
    assert failed_run.error_count == 1
    assert failed_run.errors == ["RuntimeError: provider failed"]
    assert result.provider_results[1].error is error
    assert [item.publication for item in result.result_provenance] == [
        first_results[0],
        third_results[0],
        third_results[1],
    ]
    assert result.result_provenance[0].search_run is result.provider_results[
        0
    ].search_run
    assert result.result_provenance[1].search_run is result.provider_results[
        2
    ].search_run
    assert result.result_provenance[2].search_run is result.provider_results[
        2
    ].search_run
    assert result.execution_provenance.total_provider_results == 3
    assert result.execution_provenance.merged_result_count == 2
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
async def test_execute_records_failed_run_timing_and_diagnostics(
    search_query: SearchQuery,
) -> None:
    error = RuntimeError("provider unavailable")
    archive = FakeRawResponseArchive()
    clock_values = [
        _CAPTURED_AT,
        _CAPTURED_AT + timedelta(seconds=1),
        _CAPTURED_AT + timedelta(seconds=2),
        _CAPTURED_AT + timedelta(seconds=4),
        _CAPTURED_AT + timedelta(seconds=5),
    ]
    clock = FakeClock(clock_values)

    result = await SearchEngine(
        providers=[FakeSearchProvider("failed", error=error)],
        raw_response_archive=archive,
        clock=clock,
    ).execute(search_query)

    provider_result = result.provider_results[0]
    assert provider_result.publications is None
    assert provider_result.error is error
    assert provider_result.search_run.status is SearchRunStatus.FAILED
    assert provider_result.search_run.started_at == clock_values[1]
    assert provider_result.search_run.finished_at == clock_values[3]
    assert provider_result.duration_seconds == 3
    assert provider_result.search_run.records_retrieved == 0
    assert provider_result.search_run.error_count == 1
    assert provider_result.search_run.errors == [
        "RuntimeError: provider unavailable"
    ]
    assert result.result_provenance == []
    assert archive.entries[0].status is RawResponseStatus.FAILED
    assert archive.entries[0].captured_at == clock_values[2]
    assert archive.entries[0].error_type == "RuntimeError"
    assert archive.entries[0].error_message == "provider unavailable"
    assert result.execution_provenance.total_provider_results == 0
    assert result.execution_provenance.merged_result_count == 0
    assert clock.calls == clock_values


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
    clock_values = [
        _CAPTURED_AT,
        _CAPTURED_AT + timedelta(seconds=1),
        _CAPTURED_AT + timedelta(seconds=2),
        _CAPTURED_AT + timedelta(seconds=4),
        _CAPTURED_AT + timedelta(seconds=5),
    ]
    clock = FakeClock(clock_values)

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
        clock=clock,
    ).execute(search_query)

    normalized = result.provider_results[0].publications
    assert normalized is not None
    assert normalized is not publications
    assert result.merged_publications == normalized
    assert result.merged_publications is not publications
    assert result.merged_publications[0] is normalized[0]
    assert len(archive.entries) == 1
    entry = archive.entries[0]
    assert entry.archive_id == archive_id
    assert entry.search_run_id == run_id
    assert entry.provider == "fake"
    assert entry.rendered_query == '"lean manufacturing"'
    assert entry.captured_at == clock_values[2]
    assert entry.status is RawResponseStatus.SUCCESS
    assert entry.responses is raw_pages
    assert entry.responses == raw_pages
    assert entry.error_type is None
    assert entry.error_message is None
    provider_result = result.provider_results[0]
    assert provider_result.search_run.status is SearchRunStatus.COMPLETED
    assert provider_result.search_run.started_at == clock_values[1]
    assert provider_result.search_run.finished_at == clock_values[3]
    assert provider_result.duration_seconds == 3
    assert provider_result.search_run.records_retrieved == 1
    assert provider_result.search_run.error_count == 0
    assert provider_result.search_run.errors == []
    assert result.result_provenance[0].publication is normalized[0]
    assert result.result_provenance[0].search_run is provider_result.search_run
    assert result.result_provenance[0].provider == "fake"
    assert result.execution_provenance.started_at == clock_values[0]
    assert result.execution_provenance.finished_at == clock_values[4]
    assert result.execution_provenance.duration_seconds == 5
    assert result.execution_provenance.provider_run_ids == (run_id,)
    assert result.execution_provenance.total_provider_results == 1
    assert result.execution_provenance.merged_result_count == 1
    assert clock.calls == clock_values


@pytest.mark.anyio
async def test_archive_failure_is_propagated_and_stops_execution(
    search_query: SearchQuery,
) -> None:
    archive_error = RuntimeError("archive unavailable")
    archive = FakeRawResponseArchive(error=archive_error)
    first = FakeSearchProvider("first")
    second = FakeSearchProvider("second")
    merger = SpyResultMerger()

    with pytest.raises(RuntimeError) as exc_info:
        await SearchEngine(
            providers=[first, second],
            raw_response_archive=archive,
            result_merger=merger,
        ).execute(search_query)

    assert exc_info.value is archive_error
    assert len(first.calls) == 1
    assert second.calls == []
    assert archive.entries == []
    assert merger.calls == []


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
    merger = SpyResultMerger()
    clock_values = [_CAPTURED_AT, _CAPTURED_AT]
    clock = FakeClock(clock_values)
    result = await SearchEngine(
        providers=[],
        raw_response_archive=archive,
        result_merger=merger,
        clock=clock,
    ).execute(search_query)

    assert result.provider_results == []
    assert result.merged_publications == []
    assert result.result_provenance == []
    assert result.execution_provenance.provider_run_ids == ()
    assert result.execution_provenance.total_provider_results == 0
    assert result.execution_provenance.merged_result_count == 0
    assert result.execution_provenance.duration_seconds == 0
    assert archive.entries == []
    assert merger.calls == [[]]
    assert clock.calls == clock_values


def test_fake_provider_structurally_satisfies_search_provider() -> None:
    assert isinstance(FakeSearchProvider("fake"), RuntimeSearchProvider)
