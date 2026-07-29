from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from uuid import UUID

import pytest

from app.domain.identifiers import Identifier, IdentifierType
from app.domain.deduplication import DuplicateGroupStatus
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
from app.services.search_engine import SearchEngine
from app.services.publication_merge_policy import PublicationMergePolicy
from app.storage.raw_response_archive import (
    RawResponseArchiveEntry,
    RawResponseStatus,
)

_QUERY_ID = UUID("00000000-0000-0000-0000-000000000001")
_BASE_TIME = datetime(2026, 7, 28, 12, 0, tzinfo=timezone.utc)


class ContractProvider:
    def __init__(
        self,
        name: str,
        *,
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


class ContractArchive:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.attempted_entries: list[RawResponseArchiveEntry] = []
        self.saved_entries: list[RawResponseArchiveEntry] = []

    async def save(self, entry: RawResponseArchiveEntry) -> None:
        self.attempted_entries.append(entry)
        if self.error is not None:
            raise self.error
        self.saved_entries.append(entry)


class ContractClock:
    def __init__(self, values: list[datetime]) -> None:
        self._values = iter(values)
        self.calls: list[datetime] = []

    def __call__(self) -> datetime:
        value = next(self._values)
        self.calls.append(value)
        return value


def _clock_values(provider_count: int) -> list[datetime]:
    return [
        _BASE_TIME + timedelta(seconds=index)
        for index in range(2 + 3 * provider_count)
    ]


def _uuid_factory(values: list[UUID]) -> Callable[[], UUID]:
    iterator = iter(values)
    return lambda: next(iterator)


def _uuid(number: int) -> UUID:
    return UUID(f"00000000-0000-0000-0000-{number:012d}")


def _query() -> SearchQuery:
    return SearchQuery(
        query_id=_QUERY_ID,
        name="Lean manufacturing energy",
        version=3,
        expression=SearchGroup(
            operator=BooleanOperator.AND,
            children=[
                SearchGroup(
                    operator=BooleanOperator.OR,
                    children=[
                        SearchTerm(value="lean manufacturing"),
                        SearchTerm(value="lean production"),
                    ],
                ),
                SearchGroup(
                    operator=BooleanOperator.OR,
                    children=[
                        SearchTerm(value="energy efficiency"),
                        SearchTerm(value="energy consumption"),
                    ],
                ),
            ],
        ),
    )


def _publication(title: str, *, doi: str | None = None) -> Publication:
    identifiers = (
        [Identifier(type=IdentifierType.DOI, value=doi)]
        if doi is not None
        else []
    )
    return Publication(
        title=title,
        publication_year=2025,
        identifiers=identifiers,
    )


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_single_provider_success_contract() -> None:
    query = _query()
    with_doi = _publication("Lean energy study", doi="10.1000/lean")
    without_doi = _publication("Lean case study")
    publications = [with_doi, without_doi]
    raw_pages: list[JsonObject] = [
        {"page": 1, "items": [{"id": "A"}]},
        {"page": 2, "items": [{"id": "B"}]},
    ]
    provider = ContractProvider(
        "openalex",
        publications=publications,
        raw_responses=raw_pages,
    )
    archive = ContractArchive()
    times = _clock_values(1)
    clock = ContractClock(times)
    run_id = _uuid(101)
    archive_id = _uuid(201)

    execution = await SearchEngine(
        providers=[provider],
        raw_response_archive=archive,
        run_id_factory=_uuid_factory([run_id]),
        archive_id_factory=_uuid_factory([archive_id]),
        clock=clock,
    ).execute(query)

    assert len(provider.calls) == 1
    running_run, received_query = provider.calls[0]
    assert received_query is query
    assert running_run.status is SearchRunStatus.RUNNING
    assert running_run.run_id == run_id
    assert running_run.query_id == query.query_id
    assert running_run.query_version == query.version
    assert running_run.provider == provider.name
    assert running_run.rendered_query == query.to_boolean_query()
    assert running_run.started_at == times[1]
    assert len(archive.saved_entries) == 1
    entry = archive.saved_entries[0]
    assert entry.archive_id == archive_id
    assert entry.search_run_id == run_id
    assert entry.provider == provider.name
    assert entry.rendered_query == query.to_boolean_query()
    assert entry.captured_at == times[2]
    assert entry.status is RawResponseStatus.SUCCESS
    assert entry.responses is raw_pages
    assert entry.error_type is None
    assert entry.error_message is None
    result = execution.provider_results[0]
    assert result.search_run.status is SearchRunStatus.COMPLETED
    assert result.search_run.started_at == times[1]
    assert result.search_run.finished_at == times[3]
    assert result.search_run.records_retrieved == 2
    assert result.publications is not None
    assert result.publications is not publications
    assert result.publications[0] is not with_doi
    assert result.publications[1] is not without_doi
    assert [publication.title_normalized for publication in result.publications] == [
        "lean energy study",
        "lean case study",
    ]
    assert execution.merged_publications == result.publications
    assert execution.normalized_publications == result.publications
    assert execution.merged_publications[0] is result.publications[0]
    assert execution.merged_publications[1] is result.publications[1]
    assert execution.duplicate_groups == []
    assert [item.publication for item in execution.result_provenance] == (
        result.publications
    )
    assert all(
        item.search_run is result.search_run
        for item in execution.result_provenance
    )
    summary = execution.execution_provenance
    assert summary.started_at == times[0]
    assert summary.finished_at == times[4]
    assert summary.duration_seconds == 4
    assert summary.provider_run_ids == (run_id,)
    assert summary.total_provider_results == 2
    assert summary.merged_result_count == 2
    assert clock.calls == times


@pytest.mark.anyio
async def test_multi_provider_order_and_association_contract() -> None:
    query = _query()
    call_order: list[str] = []
    publications = [
        [_publication("A1"), _publication("A2")],
        [_publication("B1")],
        [_publication("C1"), _publication("C2")],
    ]
    providers = [
        ContractProvider(
            name,
            publications=provider_publications,
            raw_responses=[{"provider": name}],
            call_order=call_order,
        )
        for name, provider_publications in zip(
            ["openalex", "crossref", "semantic_scholar"],
            publications,
            strict=True,
        )
    ]
    archive = ContractArchive()
    times = _clock_values(3)
    clock = ContractClock(times)
    run_ids = [_uuid(101), _uuid(102), _uuid(103)]
    archive_ids = [_uuid(201), _uuid(202), _uuid(203)]

    execution = await SearchEngine(
        providers=providers,
        raw_response_archive=archive,
        run_id_factory=_uuid_factory(run_ids),
        archive_id_factory=_uuid_factory(archive_ids),
        clock=clock,
    ).execute(query)

    assert call_order == ["openalex", "crossref", "semantic_scholar"]
    assert [len(provider.calls) for provider in providers] == [1, 1, 1]
    assert [result.search_run.run_id for result in execution.provider_results] == run_ids
    assert len(set(run_ids)) == 3
    assert [entry.archive_id for entry in archive.saved_entries] == archive_ids
    assert [entry.search_run_id for entry in archive.saved_entries] == run_ids
    assert [entry.provider for entry in archive.saved_entries] == call_order
    assert [
        result.search_run.provider for result in execution.provider_results
    ] == call_order
    expected_publications = [
        publication
        for result in execution.provider_results
        if result.publications is not None
        for publication in result.publications
    ]
    assert [
        item.publication for item in execution.result_provenance
    ] == expected_publications
    assert execution.execution_provenance.provider_run_ids == tuple(run_ids)
    assert execution.execution_provenance.total_provider_results == 5
    assert execution.execution_provenance.merged_result_count == 5
    assert clock.calls == times
    for index, provider in enumerate(providers):
        running_run, received_query = provider.calls[0]
        final_run = execution.provider_results[index].search_run
        archive_entry = archive.saved_entries[index]
        assert received_query is query
        assert running_run.run_id == final_run.run_id == archive_entry.search_run_id
        assert running_run.query_id == final_run.query_id == query.query_id
        assert running_run.query_version == final_run.query_version == query.version
        assert running_run.rendered_query == final_run.rendered_query
        assert final_run.rendered_query == query.to_boolean_query()
        assert running_run.provider == final_run.provider == provider.name


@pytest.mark.anyio
async def test_partial_provider_failure_contract() -> None:
    query = _query()
    call_order: list[str] = []
    error = RuntimeError("provider unavailable")
    first_publications = [_publication("First")]
    third_publications = [_publication("Third")]
    providers = [
        ContractProvider(
            "first",
            publications=first_publications,
            raw_responses=[{"page": 1}],
            call_order=call_order,
        ),
        ContractProvider("second", error=error, call_order=call_order),
        ContractProvider(
            "third",
            publications=third_publications,
            raw_responses=[{"page": 3}],
            call_order=call_order,
        ),
    ]
    archive = ContractArchive()

    execution = await SearchEngine(
        providers=providers,
        raw_response_archive=archive,
        run_id_factory=_uuid_factory([_uuid(101), _uuid(102), _uuid(103)]),
        archive_id_factory=_uuid_factory([_uuid(201), _uuid(202), _uuid(203)]),
        clock=ContractClock(_clock_values(3)),
    ).execute(query)

    assert call_order == ["first", "second", "third"]
    assert [result.search_run.status for result in execution.provider_results] == [
        SearchRunStatus.COMPLETED,
        SearchRunStatus.FAILED,
        SearchRunStatus.COMPLETED,
    ]
    failed = execution.provider_results[1]
    assert failed.publications is None
    assert failed.error is error
    assert failed.search_run.records_retrieved == 0
    assert failed.search_run.error_count == 1
    assert failed.search_run.errors == ["RuntimeError: provider unavailable"]
    assert [entry.status for entry in archive.saved_entries] == [
        RawResponseStatus.SUCCESS,
        RawResponseStatus.FAILED,
        RawResponseStatus.SUCCESS,
    ]
    failed_entry = archive.saved_entries[1]
    assert failed_entry.search_run_id == failed.search_run.run_id
    assert failed_entry.responses == []
    assert failed_entry.error_type == "RuntimeError"
    assert failed_entry.error_message == "provider unavailable"
    first_result = execution.provider_results[0].publications
    third_result = execution.provider_results[2].publications
    assert first_result is not None
    assert third_result is not None
    assert [item.publication for item in execution.result_provenance] == [
        first_result[0],
        third_result[0],
    ]
    assert execution.merged_publications == [first_result[0], third_result[0]]
    assert execution.normalized_publications == [
        first_result[0],
        third_result[0],
    ]
    assert execution.duplicate_groups == []
    assert execution.execution_provenance.total_provider_results == 2


@pytest.mark.anyio
async def test_doi_merge_and_separate_provenance_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    a1 = _publication("A1", doi="10.1000/example")
    a2 = _publication("A2")
    b1 = _publication("B1", doi="https://doi.org/10.1000/EXAMPLE")
    b2 = _publication("B2")
    first_publications = [a1, a2]
    second_publications = [b1, b2]
    archive = ContractArchive()

    def fail_if_called(
        self: PublicationMergePolicy,
        first: Publication,
        second: Publication,
    ) -> Publication:
        raise AssertionError("PublicationMergePolicy must not be called")

    monkeypatch.setattr(PublicationMergePolicy, "merge", fail_if_called)

    execution = await SearchEngine(
        providers=[
            ContractProvider(
                "first",
                publications=first_publications,
                raw_responses=[{"provider": "first"}],
            ),
            ContractProvider(
                "second",
                publications=second_publications,
                raw_responses=[{"provider": "second"}],
            ),
        ],
        raw_response_archive=archive,
        run_id_factory=_uuid_factory([_uuid(101), _uuid(102)]),
        archive_id_factory=_uuid_factory([_uuid(201), _uuid(202)]),
        clock=ContractClock(_clock_values(2)),
    ).execute(_query())

    first_result = execution.provider_results[0].publications
    second_result = execution.provider_results[1].publications
    assert first_result is not None
    assert second_result is not None
    assert first_result is not first_publications
    assert second_result is not second_publications
    assert [item.publication for item in execution.result_provenance] == [
        first_result[0],
        first_result[1],
        second_result[0],
        second_result[1],
    ]
    assert execution.result_provenance[0].search_run is not (
        execution.result_provenance[2].search_run
    )
    assert execution.merged_publications == [
        first_result[0],
        first_result[1],
        second_result[1],
    ]
    assert execution.normalized_publications == [
        first_result[0],
        first_result[1],
        second_result[0],
        second_result[1],
    ]
    assert execution.merged_publications[0] is first_result[0]
    assert execution.merged_publications[1] is first_result[1]
    assert execution.merged_publications[2] is second_result[1]
    assert execution.execution_provenance.total_provider_results == 4
    assert execution.execution_provenance.merged_result_count == 3
    assert len(execution.duplicate_groups) == 1
    assert execution.duplicate_groups[0].publication_ids == tuple(
        sorted((a1.record_id, b1.record_id))
    )
    normalized_ids = {
        publication.record_id
        for publication in execution.normalized_publications
    }
    assert set(execution.duplicate_groups[0].publication_ids) <= normalized_ids
    assert execution.duplicate_groups[0].status is DuplicateGroupStatus.PENDING
    assert execution.duplicate_groups[0].decision_history == ()
    assert [item.title for item in execution.normalized_publications] == [
        "A1",
        "A2",
        "B1",
        "B2",
    ]


@pytest.mark.anyio
async def test_search_execution_exposes_strong_identifier_candidate_groups() -> None:
    first = Publication(
        title="First",
        identifiers=[Identifier(type=IdentifierType.PMID, value="123")],
    )
    second = Publication(
        title="Second",
        identifiers=[Identifier(type=IdentifierType.PMID, value="123")],
    )
    execution = await SearchEngine(
        providers=[
            ContractProvider(
                "provider",
                publications=[first, second],
                raw_responses=[{"provider": "provider"}],
            )
        ],
        raw_response_archive=ContractArchive(),
        run_id_factory=_uuid_factory([_uuid(101)]),
        archive_id_factory=_uuid_factory([_uuid(201)]),
        clock=ContractClock(_clock_values(1)),
    ).execute(_query())

    assert [item.title for item in execution.merged_publications] == [
        "First",
        "Second",
    ]
    assert execution.normalized_publications == execution.merged_publications
    assert len(execution.duplicate_groups) == 1
    assert execution.duplicate_groups[0].publication_ids == tuple(
        sorted((first.record_id, second.record_id))
    )


@pytest.mark.anyio
async def test_empty_successful_provider_contract() -> None:
    raw_pages: list[JsonObject] = [{"page": 1, "items": []}]
    provider = ContractProvider(
        "empty",
        publications=[],
        raw_responses=raw_pages,
    )
    archive = ContractArchive()
    run_id = _uuid(101)

    execution = await SearchEngine(
        providers=[provider],
        raw_response_archive=archive,
        run_id_factory=_uuid_factory([run_id]),
        archive_id_factory=_uuid_factory([_uuid(201)]),
        clock=ContractClock(_clock_values(1)),
    ).execute(_query())

    result = execution.provider_results[0]
    assert result.search_run.status is SearchRunStatus.COMPLETED
    assert result.search_run.records_retrieved == 0
    assert result.publications == []
    assert archive.saved_entries[0].responses is raw_pages
    assert execution.result_provenance == []
    assert execution.normalized_publications == []
    assert execution.merged_publications == []
    assert execution.execution_provenance.provider_run_ids == (run_id,)
    assert execution.execution_provenance.total_provider_results == 0
    assert execution.execution_provenance.merged_result_count == 0


@pytest.mark.anyio
async def test_no_configured_providers_contract() -> None:
    archive = ContractArchive()
    times = _clock_values(0)
    clock = ContractClock(times)

    execution = await SearchEngine(
        providers=[],
        raw_response_archive=archive,
        clock=clock,
    ).execute(_query())

    assert archive.attempted_entries == []
    assert execution.provider_results == []
    assert execution.normalized_publications == []
    assert execution.merged_publications == []
    assert execution.result_provenance == []
    assert execution.execution_provenance.provider_run_ids == ()
    assert execution.execution_provenance.total_provider_results == 0
    assert execution.execution_provenance.merged_result_count == 0
    assert execution.execution_provenance.started_at == times[0]
    assert execution.execution_provenance.finished_at == times[1]
    assert execution.execution_provenance.duration_seconds == 1
    assert clock.calls == times


@pytest.mark.anyio
async def test_archive_failure_after_successful_provider_contract() -> None:
    archive_error = RuntimeError("archive unavailable")
    archive = ContractArchive(error=archive_error)
    first = ContractProvider(
        "first",
        publications=[_publication("First")],
        raw_responses=[{"page": 1}],
    )
    second = ContractProvider("second", publications=[_publication("Second")])

    with pytest.raises(RuntimeError) as exc_info:
        await SearchEngine(
            providers=[first, second],
            raw_response_archive=archive,
            run_id_factory=_uuid_factory([_uuid(101), _uuid(102)]),
            archive_id_factory=_uuid_factory([_uuid(201), _uuid(202)]),
            clock=ContractClock(_clock_values(2)),
        ).execute(_query())

    assert exc_info.value is archive_error
    assert len(first.calls) == 1
    assert second.calls == []
    assert archive.saved_entries == []
    assert len(archive.attempted_entries) == 1
    attempted = archive.attempted_entries[0]
    assert attempted.status is RawResponseStatus.SUCCESS
    assert attempted.archive_id == _uuid(201)
    assert attempted.search_run_id == _uuid(101)
    assert attempted.responses == [{"page": 1}]


@pytest.mark.anyio
async def test_archive_failure_while_recording_provider_failure_contract() -> None:
    provider_error = RuntimeError("provider unavailable")
    archive_error = RuntimeError("archive unavailable")
    archive = ContractArchive(error=archive_error)
    first = ContractProvider("first", error=provider_error)
    second = ContractProvider("second", publications=[_publication("Second")])

    with pytest.raises(RuntimeError) as exc_info:
        await SearchEngine(
            providers=[first, second],
            raw_response_archive=archive,
            run_id_factory=_uuid_factory([_uuid(101), _uuid(102)]),
            archive_id_factory=_uuid_factory([_uuid(201), _uuid(202)]),
            clock=ContractClock(_clock_values(2)),
        ).execute(_query())

    assert exc_info.value is archive_error
    assert len(first.calls) == 1
    assert second.calls == []
    assert archive.saved_entries == []
    assert len(archive.attempted_entries) == 1
    attempted = archive.attempted_entries[0]
    assert attempted.status is RawResponseStatus.FAILED
    assert attempted.archive_id == _uuid(201)
    assert attempted.search_run_id == _uuid(101)
    assert attempted.responses == []
    assert attempted.error_type == "RuntimeError"
    assert attempted.error_message == "provider unavailable"
