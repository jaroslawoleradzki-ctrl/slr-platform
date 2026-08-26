from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timedelta, timezone
from typing import Protocol, runtime_checkable
from uuid import UUID

import pytest

from app.domain.identifiers import Identifier, IdentifierType
from app.domain.publication import Publication
from app.domain.search import (
    BooleanOperator,
    SearchGroup,
    SearchQuery,
    SearchRun,
    SearchRunStatus,
    SearchTerm,
)
from app.providers.search.base import JsonObject, ProviderSearchOutput
from app.services.canonical_query_validator import (
    CanonicalMatchStatus,
    validate_canonical_query,
)
from app.services.duplicate_group_builder import DuplicateGroupBuilder
from app.services.publication_merge_policy import PublicationMergePolicy
from app.services.result_merger import ResultMerger
from app.services.search_engine import (
    ProviderSearchResult,
    SearchEngine,
    SearchProvider,
)
from app.storage.raw_response_archive import (
    RawResponseArchiveEntry,
    RawResponseStatus,
)
from tests.unit.services.test_search_canonical_regression import canonical_regression_query

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
        cursor: str = "*",
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


class SpyDuplicateGroupBuilder(DuplicateGroupBuilder):
    def __init__(self) -> None:
        self.calls: list[tuple[list[Publication], datetime | None]] = []

    def build(
        self,
        publications: Iterable[Publication],
        *,
        created_at: datetime | None = None,
    ) -> list:
        captured = list(publications)
        self.calls.append((captured, created_at))
        return super().build(captured, created_at=created_at)


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
    assert result.normalized_publications == result.merged_publications
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
    assert result.normalized_publications == result.merged_publications
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
    assert result.normalized_publications == []
    assert result.merged_publications == []
    assert result.duplicate_groups == []
    assert result.result_provenance == []


@pytest.mark.anyio
async def test_execute_returns_duplicate_groups_for_merged_publications(
    search_query: SearchQuery,
    archive: FakeRawResponseArchive,
) -> None:
    first = Publication(
        title="First",
        identifiers=[Identifier(type=IdentifierType.PMID, value="123")],
    )
    second = Publication(
        title="Second",
        identifiers=[Identifier(type=IdentifierType.PMID, value="123")],
    )

    result = await SearchEngine(
        providers=[FakeSearchProvider("provider", [first, second])],
        raw_response_archive=archive,
    ).execute(search_query)

    assert [publication.title for publication in result.merged_publications] == [
        "First",
        "Second",
    ]
    assert result.normalized_publications == result.merged_publications
    assert len(result.duplicate_groups) == 1
    assert result.duplicate_groups[0].publication_ids == tuple(
        sorted((first.record_id, second.record_id))
    )


@pytest.mark.anyio
async def test_builder_is_called_once_and_merge_policy_is_not_used(
    search_query: SearchQuery,
    archive: FakeRawResponseArchive,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    publications = [
        Publication(
            title="First",
            identifiers=[Identifier(type=IdentifierType.DOI, value="10.1000/shared")],
        ),
        Publication(
            title="Alternative metadata",
            identifiers=[Identifier(type=IdentifierType.DOI, value="10.1000/SHARED")],
        ),
    ]
    builder = SpyDuplicateGroupBuilder()

    def fail_if_called(
        self: PublicationMergePolicy,
        first: Publication,
        second: Publication,
    ) -> Publication:
        raise AssertionError("PublicationMergePolicy must not be called")

    monkeypatch.setattr(PublicationMergePolicy, "merge", fail_if_called)
    result = await SearchEngine(
        providers=[FakeSearchProvider("provider", publications)],
        raw_response_archive=archive,
        duplicate_group_builder=builder,
    ).execute(search_query)

    assert len(builder.calls) == 1
    captured, created_at = builder.calls[0]
    assert captured == result.normalized_publications
    assert len(captured) == 2
    assert [publication.title for publication in result.merged_publications] == [
        "First"
    ]
    assert [publication.title for publication in result.normalized_publications] == [
        "First",
        "Alternative metadata",
    ]
    assert created_at == result.execution_provenance.finished_at
    assert len(result.duplicate_groups) == 1


@pytest.mark.anyio
async def test_execute_groups_actual_openalex_identifier_format(
    search_query: SearchQuery,
    archive: FakeRawResponseArchive,
) -> None:
    identifier = Identifier(
        type=IdentifierType.OTHER,
        value="https://openalex.org/W123",
        source="openalex",
    )
    first = Publication(title="First", identifiers=[identifier])
    second = Publication(title="Second", identifiers=[identifier])

    result = await SearchEngine(
        providers=[FakeSearchProvider("openalex", [first, second])],
        raw_response_archive=archive,
    ).execute(search_query)

    assert result.normalized_publications == result.merged_publications
    assert result.duplicate_groups[0].publication_ids == tuple(
        sorted((first.record_id, second.record_id))
    )


@pytest.mark.anyio
async def test_execute_builds_transitive_group_before_doi_reduction(
    search_query: SearchQuery,
    archive: FakeRawResponseArchive,
) -> None:
    first = Publication(
        title="First",
        identifiers=[Identifier(type=IdentifierType.DOI, value="10.1000/shared")],
    )
    bridge = Publication(
        title="Bridge",
        identifiers=[
            Identifier(type=IdentifierType.DOI, value="10.1000/SHARED"),
            Identifier(type=IdentifierType.PMID, value="123"),
        ],
    )
    third = Publication(
        title="Third",
        identifiers=[Identifier(type=IdentifierType.PMID, value="123")],
    )

    result = await SearchEngine(
        providers=[FakeSearchProvider("provider", [first, bridge, third])],
        raw_response_archive=archive,
    ).execute(search_query)

    assert result.normalized_publications == result.provider_results[0].publications
    assert [publication.title for publication in result.merged_publications] == [
        "First",
        "Third",
    ]
    assert result.duplicate_groups[0].publication_ids == tuple(
        sorted((first.record_id, bridge.record_id, third.record_id))
    )
    available_ids = [
        publication.record_id for publication in result.normalized_publications
    ]
    for group in result.duplicate_groups:
        for publication_id in group.publication_ids:
            assert available_ids.count(publication_id) == 1


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
    assert result.normalized_publications == [
        first_results[0],
        third_results[0],
        third_results[1],
    ]
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
    assert result.normalized_publications == normalized
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
    assert result.normalized_publications == []
    assert result.merged_publications == []
    assert result.duplicate_groups == []
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


@pytest.mark.anyio
async def test_post_merge_canonical_validation_abstract_obtained_via_merge_causes_match(
    archive: FakeRawResponseArchive,
) -> None:
    """1. Brak abstraktu przed merge -> INDETERMINATE (zachowany w provider 1).
    2. Drugi rekord tego samego artykułu z abstraktem -> MATCH przed merge (zachowany w provider 2).
    3. Merge konsoliduje rekord i dołącza abstrakt.
    4. Po merge obecność abstraktu daje MATCH i publikacja zostaje w merged_publications.
    """
    query = canonical_regression_query()
    doi = "10.1016/j.test.match.1"

    # Provider 1: Title matches Kaizen (block 1) & industrial plants (block 3), missing Energy (block 2).
    # Abstract is None -> INDETERMINATE before merge.
    pub1 = Publication(
        title="Kaizen in industrial plants",
        abstract=None,
        identifiers=[Identifier(type=IdentifierType.DOI, value=doi)],
    )
    assert validate_canonical_query(query, pub1).status is CanonicalMatchStatus.INDETERMINATE

    # Provider 2: Has the abstract with energy efficiency -> MATCH before merge.
    pub2 = Publication(
        title="Kaizen in industrial plants",
        abstract="A case study of energy efficiency in manufacturing.",
        identifiers=[Identifier(type=IdentifierType.DOI, value=doi)],
    )
    assert validate_canonical_query(query, pub2).status is CanonicalMatchStatus.MATCH

    provider1 = FakeSearchProvider("provider1", [pub1])
    provider2 = FakeSearchProvider("provider2", [pub2])

    result = await SearchEngine(
        providers=[provider1, provider2],
        raw_response_archive=archive,
    ).execute(query)

    assert len(result.provider_results[0].publications or []) == 1
    assert len(result.provider_results[1].publications or []) == 1
    assert len(result.normalized_publications) == 2
    assert len(result.merged_publications) == 1
    merged = result.merged_publications[0]
    assert merged.abstract == "A case study of energy efficiency in manufacturing."
    assert validate_canonical_query(query, merged).status is CanonicalMatchStatus.MATCH
    assert result.execution_provenance.merged_result_count == 1


@pytest.mark.anyio
async def test_post_merge_canonical_validation_abstract_obtained_via_merge_causes_non_match(
    archive: FakeRawResponseArchive,
) -> None:
    """1. Brak abstraktu przed merge -> INDETERMINATE (zachowany w provider 1 ze względu na recall-first).
    2. Drugi rekord dostarcza abstrakt, w którym brakuje wymaganego bloku tematycznego.
    3. Merge konsoliduje metadane rekordu.
    4. Po merge pełny rekord (tytuł + abstrakt) jest oceniany jako NON_MATCH i zostaje odrzucony z merged_publications.
    """
    query = canonical_regression_query()
    doi = "10.1016/j.test.nonmatch.1"

    # Provider 1: Title has Kaizen & industrial plants, Abstract is None -> INDETERMINATE before merge.
    pub1 = Publication(
        title="Kaizen in industrial plants",
        abstract=None,
        identifiers=[Identifier(type=IdentifierType.DOI, value=doi)],
    )
    assert validate_canonical_query(query, pub1).status is CanonicalMatchStatus.INDETERMINATE

    # Provider 2: Abstract discusses healthcare without energy concepts -> when merged into pub1,
    # the complete title + abstract lacks Block 2 (Energy), making it a definitive NON_MATCH.
    pub2 = Publication(
        title="Kaizen in industrial plants",
        abstract="A healthcare hospital case study focusing purely on ergonomics without any energy concepts.",
        identifiers=[Identifier(type=IdentifierType.DOI, value=doi)],
    )
    assert validate_canonical_query(query, pub2).status is CanonicalMatchStatus.NON_MATCH

    # Custom merger that simulates consolidation of pub2's abstract into pub1
    class NonMatchMerger(ResultMerger):
        def merge(self, publications: Iterable[Publication]) -> list[Publication]:
            pubs = list(publications)
            if len(pubs) == 1 and pubs[0].identifiers:
                # Merge incoming abstract into candidate
                return [pubs[0].model_copy(update={"abstract": pub2.abstract})]
            return super().merge(pubs)

    provider1 = FakeSearchProvider("provider1", [pub1])
    provider2 = FakeSearchProvider("provider2", [pub2])

    result = await SearchEngine(
        providers=[provider1, provider2],
        raw_response_archive=archive,
        result_merger=NonMatchMerger(),
    ).execute(query)

    # Provider 1 kept pub1 (INDETERMINATE), Provider 2 dropped pub2 (NON_MATCH)
    assert len(result.provider_results[0].publications or []) == 1
    assert len(result.provider_results[1].publications or []) == 0
    # After ResultMerger consolidated the abstract, post-merge canonical validation evaluated it as NON_MATCH
    assert result.merged_publications == []
    assert result.execution_provenance.merged_result_count == 0


@pytest.mark.anyio
async def test_post_merge_canonical_validation_preserves_indeterminate_when_still_insufficient_data(
    archive: FakeRawResponseArchive,
) -> None:
    """1. Brak abstraktu przed merge -> INDETERMINATE (zachowany w obu providerach).
    2. Po merge rekord nadal nie posiada abstraktu (dane nadal niewystarczające).
    3. Po merge rekord nadal otrzymuje INDETERMINATE i jest zachowany w merged_publications (polityka recall-first).
    """
    query = canonical_regression_query()
    doi = "10.1016/j.test.indeterminate.1"

    pub1 = Publication(
        title="Kaizen in industrial plants",
        abstract=None,
        identifiers=[Identifier(type=IdentifierType.DOI, value=doi)],
    )
    pub2 = Publication(
        title="Kaizen in industrial plants",
        abstract=None,
        identifiers=[Identifier(type=IdentifierType.DOI, value=doi)],
    )
    assert validate_canonical_query(query, pub1).status is CanonicalMatchStatus.INDETERMINATE
    assert validate_canonical_query(query, pub2).status is CanonicalMatchStatus.INDETERMINATE

    provider1 = FakeSearchProvider("provider1", [pub1])
    provider2 = FakeSearchProvider("provider2", [pub2])

    result = await SearchEngine(
        providers=[provider1, provider2],
        raw_response_archive=archive,
    ).execute(query)

    assert len(result.provider_results[0].publications or []) == 1
    assert len(result.provider_results[1].publications or []) == 1
    assert len(result.normalized_publications) == 2
    assert len(result.merged_publications) == 1
    merged = result.merged_publications[0]
    assert merged.abstract is None
    assert validate_canonical_query(query, merged).status is CanonicalMatchStatus.INDETERMINATE
    assert result.execution_provenance.merged_result_count == 1


@pytest.mark.anyio
async def test_post_merge_canonical_validation_not_operator_rejection(
    archive: FakeRawResponseArchive,
) -> None:
    """NOT operator: brak abstraktu daje INDETERMINATE, ale abstrakt po merge zawiera zanegowany termin -> NON_MATCH."""
    query = SearchQuery(
        name="Kaizen manufacturing without hospitals",
        expression=SearchGroup(
            operator=BooleanOperator.AND,
            children=[
                SearchTerm(value="Kaizen"),
                SearchTerm(value="Manufacturing"),
                SearchGroup(
                    operator=BooleanOperator.NOT,
                    children=[SearchTerm(value="Hospital")],
                ),
            ],
        ),
    )
    doi = "10.1016/j.test.not.1"

    pub1 = Publication(
        title="Kaizen in manufacturing operations",
        abstract=None,
        identifiers=[Identifier(type=IdentifierType.DOI, value=doi)],
    )
    assert validate_canonical_query(query, pub1).status is CanonicalMatchStatus.INDETERMINATE

    pub2 = Publication(
        title="Kaizen in manufacturing operations",
        abstract="Application in hospital emergency maintenance.",
        identifiers=[Identifier(type=IdentifierType.DOI, value=doi)],
    )
    assert validate_canonical_query(query, pub2).status is CanonicalMatchStatus.NON_MATCH

    class NotMerger(ResultMerger):
        def merge(self, publications: Iterable[Publication]) -> list[Publication]:
            pubs = list(publications)
            if len(pubs) == 1:
                return [pubs[0].model_copy(update={"abstract": pub2.abstract})]
            return super().merge(pubs)

    provider1 = FakeSearchProvider("provider1", [pub1])
    provider2 = FakeSearchProvider("provider2", [pub2])

    result = await SearchEngine(
        providers=[provider1, provider2],
        raw_response_archive=archive,
        result_merger=NotMerger(),
    ).execute(query)

    # Merged publication contains "hospital" which violates the NOT clause -> filtered out
    assert result.merged_publications == []
    assert result.execution_provenance.merged_result_count == 0

