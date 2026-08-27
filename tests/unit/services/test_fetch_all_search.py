"""Fetch-all pagination tests (v0.6.5), provider-agnostic by construction.

Every scenario drives the real ``FetchAllSearchService`` loop with scripted
providers exposing the uniform ``search_with_raw`` contract, mirroring how
OpenAlex (opaque cursor), Crossref (opaque cursor) and Semantic Scholar
(offset-as-cursor) behave.
"""

from __future__ import annotations

import asyncio
import dataclasses
from typing import Any
from uuid import UUID

import httpx

from app.api.dto.search_strategy import SearchStrategyExecutionRequest
from app.domain.author import Author
from app.domain.identifiers import Identifier, IdentifierType
from app.domain.provenance import ProvenanceEntry
from app.domain.publication import DocumentType, Publication
from app.providers.search.base import ProviderSearchOutput
from app.repositories.search_result_snapshot_repository import (
    DuplicateSearchResultSnapshotError,
    SearchResultSnapshot,
)
from app.services.fetch_all_search import FetchAllSearchService


class FakeSnapshotRepository:
    def __init__(self) -> None:
        self.saved: list[SearchResultSnapshot] = []

    def save(self, snapshot: SearchResultSnapshot) -> SearchResultSnapshot:
        for existing in self.saved:
            if (
                existing.project_id == snapshot.project_id
                and existing.search_run_id == snapshot.search_run_id
                and existing.publication.record_id == snapshot.publication.record_id
            ):
                raise DuplicateSearchResultSnapshotError(
                    "publication already has a snapshot in this project search run"
                )
        self.saved.append(snapshot)
        return snapshot

    def get_for_search_run(
        self, project_id: str, search_run_id: UUID, *, connection: Any = None
    ) -> list[SearchResultSnapshot]:
        return [
            s for s in self.saved if s.project_id == project_id and s.search_run_id == search_run_id
        ]


class FakeProvider:
    """Scripted provider popping one response per ``search_with_raw`` call."""

    def __init__(self, name: str, responses: list[Any]) -> None:
        self.name = name
        self._responses = list(responses)
        self.cursors: list[str] = []

    async def search_with_raw(
        self,
        *,
        search_run: Any,
        search_query: Any,
        cursor: str = "*",
    ) -> ProviderSearchOutput:
        self.cursors.append(cursor)
        if not self._responses:
            raise AssertionError(f"{self.name} fetched more pages than scripted")
        response = self._responses.pop(0)
        if isinstance(response, Exception):
            raise response
        publications = [
            publication.model_copy(
                update={
                    "provenance": [
                        entry.model_copy(update={"run_id": search_run.run_id}) for entry in publication.provenance
                    ]
                }
            )
            for publication in response.publications
        ]
        return dataclasses.replace(response, publications=publications)


def _publication(
    title: str,
    *,
    provider: str,
    source_id: str,
    year: int | None = 2024,
    language: str | None = None,
    document_type: DocumentType | None = DocumentType.JOURNAL_ARTICLE,
    open_access: bool | None = False,
    doi: str | None = None,
) -> Publication:
    return Publication(
        title=title,
        authors=[Author(display_name="Ada Author")],
        publication_year=year,
        language=language,
        document_type=document_type,
        open_access=open_access,
        identifiers=([Identifier(type=IdentifierType.DOI, value=doi)] if doi is not None else []),
        provenance=[ProvenanceEntry(source=provider, source_record_id=source_id)],
    )


def _out(
    publications: list[Publication],
    next_cursor: str | None = None,
    *,
    total_count: int | None = None,
    warnings: tuple[str, ...] = (),
    is_lossless: bool | None = None,
    raw_count: int = 0,
    skipped_malformed_count: int = 0,
) -> ProviderSearchOutput:
    return ProviderSearchOutput(
        publications=list(publications),
        raw_responses=[],
        total_count=total_count,
        next_cursor=next_cursor,
        has_more=next_cursor is not None,
        warnings=warnings,
        is_lossless=is_lossless,
        raw_count=raw_count,
        skipped_malformed_count=skipped_malformed_count,
    )


def _strategy(**overrides: Any) -> SearchStrategyExecutionRequest:
    data: dict[str, Any] = {
        "publication_year_from": 2018,
        "publication_year_to": 2026,
        "providers": ["openalex"],
        "concept_groups": [{"id": "g1", "name": "Lean", "terms": ["lean"]}],
    }
    data.update(overrides)
    return SearchStrategyExecutionRequest(**data)


def run_fetch_all(
    providers: list[FakeProvider],
    strategy: SearchStrategyExecutionRequest | None = None,
    project_id: str = "proj-1",
    **service_overrides: Any,
):
    """Drive one fetch-all job to completion on a private event loop."""

    async def factory(strategy: Any, http_client: httpx.AsyncClient) -> list[FakeProvider]:
        return providers

    service = FetchAllSearchService(
        provider_factory=factory,
        snapshot_repository=FakeSnapshotRepository(),
        **service_overrides,
    )

    async def main() -> tuple[FetchAllSearchService, Any]:
        started = service.start(project_id, strategy or _strategy())
        job = await service.wait(started.job_id)
        return service, job

    service_obj, job = asyncio.run(main())
    return service_obj, job, service_obj.get_status(job.job_id)


# --- core pagination scenarios ---------------------------------------------


def test_openalex_multi_page_fetch_all_retrieves_every_available_page() -> None:
    provider = FakeProvider(
        "openalex",
        [
            _out([_publication("A1", provider="openalex", source_id="W1")], "cursor-1"),
            _out([_publication("A2", provider="openalex", source_id="W2")], "cursor-2"),
            _out([_publication("A3", provider="openalex", source_id="W3")], None),
        ],
    )
    _, _, status_response = run_fetch_all([provider], _strategy(providers=["openalex"]))

    assert status_response.status == "completed"
    assert provider.cursors == ["*", "cursor-1", "cursor-2"]
    state = status_response.providers[0]
    assert state.status == "complete"
    assert state.fetched_count == 3
    assert state.kept_count == 3
    assert status_response.fetched_total == 3
    result = status_response.result
    assert result is not None
    assert result.returned_count == 3
    assert [record.source_id for record in result.results] == ["W1", "W2", "W3"]


def test_crossref_multi_page_fetch_all_retrieves_every_available_page() -> None:
    provider = FakeProvider(
        "crossref",
        [
            _out([_publication("C1", provider="crossref", source_id="10.1/a")], "cx-1"),
            _out([_publication("C2", provider="crossref", source_id="10.1/b")], "cx-2"),
            _out([], None),
        ],
    )
    _, _, status_response = run_fetch_all([provider], _strategy(providers=["crossref"]))

    assert status_response.status == "completed"
    assert provider.cursors == ["*", "cx-1", "cx-2"]
    state = status_response.providers[0]
    assert state.status == "complete"
    assert state.fetched_count == 2
    assert state.kept_count == 2


def test_fetch_all_continues_after_a_page_containing_only_malformed_crossref_records() -> None:
    warning = "1 Crossref record(s) skipped due to missing/malformed title or metadata validation."
    provider = FakeProvider(
        "crossref",
        [
            _out([], "cx-1", raw_count=1, skipped_malformed_count=1, warnings=(warning,)),
            _out([_publication("C1", provider="crossref", source_id="10.1/a")]),
        ],
    )

    _, _, status_response = run_fetch_all([provider], _strategy(providers=["crossref"]))

    assert provider.cursors == ["*", "cx-1"]
    state = status_response.providers[0]
    assert state.status == "complete"
    assert state.fetched_count == 1
    assert state.skipped_malformed_count == 1


def test_semantic_scholar_offset_cursor_pagination_is_followed() -> None:
    provider = FakeProvider(
        "semantic_scholar",
        [
            _out([_publication("S1", provider="semantic_scholar", source_id="P1")], "100"),
            _out([_publication("S2", provider="semantic_scholar", source_id="P2")], "200"),
            _out([_publication("S3", provider="semantic_scholar", source_id="P3")], None),
        ],
    )
    _, _, status_response = run_fetch_all([provider], _strategy(providers=["semantic_scholar"]))

    assert status_response.status == "completed"
    # Semantic Scholar paginates by numeric offset surfaced as cursor string.
    assert provider.cursors == ["*", "100", "200"]
    state = status_response.providers[0]
    assert state.status == "complete"
    assert state.fetched_count == 3


def test_multi_provider_jobs_paginate_each_provider_independently() -> None:
    openalex = FakeProvider(
        "openalex",
        [
            _out([_publication("A1", provider="openalex", source_id="W1")], "oa-2"),
            _out([_publication("A2", provider="openalex", source_id="W2")], None),
        ],
    )
    crossref = FakeProvider(
        "crossref",
        [
            _out([_publication("C1", provider="crossref", source_id="10.1/a")], "cx-2"),
            _out([_publication("C2", provider="crossref", source_id="10.1/b")], "cx-3"),
            _out([_publication("C3", provider="crossref", source_id="10.1/c")], None),
        ],
    )
    semantic = FakeProvider(
        "semantic_scholar",
        [_out([_publication("S1", provider="semantic_scholar", source_id="P1")], None)],
    )
    strategy = _strategy(providers=["openalex", "crossref", "semantic_scholar"])
    _, job, status_response = run_fetch_all([openalex, crossref, semantic], strategy)

    assert status_response.status == "completed"
    assert openalex.cursors == ["*", "oa-2"]
    assert crossref.cursors == ["*", "cx-2", "cx-3"]
    assert semantic.cursors == ["*"]
    statuses = {state.provider: state.status for state in status_response.providers}
    assert statuses == {
        "openalex": "complete",
        "crossref": "complete",
        "semantic_scholar": "complete",
    }
    result = status_response.result
    assert result is not None
    assert len(result.results) == 6
    assert [state.name for state in job.providers] == [
        "openalex",
        "crossref",
        "semantic_scholar",
    ]


# --- early end, limits and loop guards --------------------------------------


def test_provider_that_ends_after_first_page_is_marked_complete() -> None:
    provider = FakeProvider(
        "openalex",
        [_out([_publication("Only", provider="openalex", source_id="W1")], None)],
    )
    _, _, status_response = run_fetch_all([provider])

    state = status_response.providers[0]
    assert state.status == "complete"
    assert state.pages_fetched == 1
    assert state.limit_reached is False


def test_record_safety_cap_stops_pagination_without_infinite_loop() -> None:
    endless_pages = [
        _out(
            [_publication(f"A{page}-{i}", provider="openalex", source_id=f"W{page}-{i}") for i in range(4)],
            f"cursor-{page}",
        )
        for page in range(50)
    ]
    provider = FakeProvider("openalex", endless_pages)
    _, _, status_response = run_fetch_all([provider], max_records_per_provider=10, max_pages_per_provider=200)

    state = status_response.providers[0]
    assert state.fetched_count == 12
    assert state.limit_reached is True
    assert state.status == "partial"
    assert len(provider.cursors) < 50
    result = status_response.result
    assert result is not None
    assert result.has_more is True


def test_page_safety_cap_limits_request_count() -> None:
    endless_pages = [
        _out(
            [_publication(f"A{i}", provider="openalex", source_id=f"W{i}")],
            f"cursor-{i}",
        )
        for i in range(50)
    ]
    provider = FakeProvider("openalex", endless_pages)
    _, _, status_response = run_fetch_all([provider], max_pages_per_provider=3)

    state = status_response.providers[0]
    assert len(provider.cursors) == 3
    assert state.pages_fetched == 3
    assert state.status == "partial"
    assert state.limit_reached is True


def test_semantic_scholar_api_hard_limit_is_reported_as_complete_with_limit() -> None:
    """Provider reports many matches but stops offering further pages."""

    records = [_publication(f"S{i}", provider="semantic_scholar", source_id=f"P{i}") for i in range(2)]
    provider = FakeProvider(
        "semantic_scholar",
        [_out(records, None, total_count=7574)],
    )
    _, _, status_response = run_fetch_all([provider], _strategy(providers=["semantic_scholar"]))

    state = status_response.providers[0]
    assert state.status == "complete"
    assert state.total_reported == 7574
    assert state.fetched_count == 2
    assert state.limit_reached is True
    assert state.message is not None and "7574" in state.message
    result = status_response.result
    assert result is not None
    assert result.total_count == 7574
    assert result.returned_count == 2


def test_repeated_cursor_stops_pagination_safely() -> None:
    """A repeated cursor means no forward progress - NOT proven completeness."""

    provider = FakeProvider(
        "openalex",
        [
            _out([_publication("A1", provider="openalex", source_id="W1")], "same-cursor"),
            _out([_publication("A2", provider="openalex", source_id="W2")], "same-cursor"),
        ],
    )
    _, _, status_response = run_fetch_all([provider])

    state = status_response.providers[0]
    assert provider.cursors == ["*", "same-cursor"]
    assert state.status == "partial"
    assert state.limit_reached is True
    assert state.message is not None and "cursor" in state.message
    assert state.fetched_count == 2

    # Already fetched records are preserved; the job completes with
    # partial-success information for the affected provider.
    assert status_response.status == "completed"
    result = status_response.result
    assert result is not None
    assert [record.source_id for record in result.results] == ["W1", "W2"]
    assert result.has_more is True
    assert any(error.provider == "openalex" and "cursor" in error.message for error in result.provider_errors)


def test_empty_page_with_has_more_stops_pagination_safely() -> None:
    """An empty page while more results are claimed is NOT proven completeness."""

    provider = FakeProvider(
        "openalex",
        [
            _out([_publication("A1", provider="openalex", source_id="W1")], "cursor-2"),
            _out([], "cursor-3"),
        ],
    )
    _, _, status_response = run_fetch_all([provider])

    state = status_response.providers[0]
    assert provider.cursors == ["*", "cursor-2"]
    assert state.status == "partial"
    assert state.limit_reached is True
    assert state.message is not None and "empty page" in state.message
    assert state.fetched_count == 1

    # Already fetched records are preserved; the job completes with
    # partial-success information for the affected provider.
    assert status_response.status == "completed"
    result = status_response.result
    assert result is not None
    assert [record.source_id for record in result.results] == ["W1"]
    assert result.has_more is True
    assert any(error.provider == "openalex" and "empty page" in error.message for error in result.provider_errors)


# --- partial failure ---------------------------------------------------------


def test_permanent_error_keeps_other_providers_partial_success() -> None:
    openalex = FakeProvider(
        "openalex",
        [_out([_publication("A1", provider="openalex", source_id="W1")], None)],
    )
    broken = FakeProvider(
        "crossref",
        [RuntimeError("upstream exploded"), RuntimeError("upstream exploded again")],
    )
    semantic = FakeProvider(
        "semantic_scholar",
        [_out([_publication("S1", provider="semantic_scholar", source_id="P1")], None)],
    )
    strategy = _strategy(providers=["openalex", "crossref", "semantic_scholar"])
    _, _, status_response = run_fetch_all([openalex, broken, semantic], strategy)

    statuses = {state.provider: state.status for state in status_response.providers}
    assert statuses == {
        "openalex": "complete",
        "crossref": "failed",
        "semantic_scholar": "complete",
    }
    assert status_response.status == "completed"
    result = status_response.result
    assert result is not None
    assert [record.source_id for record in result.results] == ["W1", "P1"]
    assert len(result.provider_errors) == 1
    assert result.provider_errors[0].provider == "crossref"
    assert "RuntimeError" in result.provider_errors[0].message


def test_http_429_after_exhausted_retries_is_partial_not_fatal() -> None:
    retry_error = httpx.HTTPStatusError(
        "rate limited",
        request=httpx.Request("GET", "https://api.semanticscholar.org"),
        response=httpx.Response(429, request=httpx.Request("GET", "https://x")),
    )
    rate_limited = FakeProvider(
        "semantic_scholar",
        [
            retry_error,
            _out([_publication("S1", provider="semantic_scholar", source_id="P1")], None),
        ],
    )
    openalex = FakeProvider(
        "openalex",
        [
            _out([_publication("A1", provider="openalex", source_id="W1")], "cursor-2"),
            _out([_publication("A2", provider="openalex", source_id="W2")], None),
        ],
    )
    strategy = _strategy(providers=["openalex", "semantic_scholar"])
    _, _, status_response = run_fetch_all([openalex, rate_limited], strategy)

    statuses = {state.provider: state.status for state in status_response.providers}
    assert statuses == {"openalex": "complete", "semantic_scholar": "failed"}
    result = status_response.result
    assert result is not None
    assert len(result.results) == 2
    assert any(error.provider == "semantic_scholar" for error in result.provider_errors)


# --- local filters & language semantics -------------------------------------


def test_local_filters_are_applied_to_every_fetched_page() -> None:
    provider = FakeProvider(
        "openalex",
        [
            _out(
                [
                    _publication(
                        "Keep",
                        provider="openalex",
                        source_id="W1",
                        year=2024,
                        open_access=True,
                    ),
                    _publication("Too old", provider="openalex", source_id="W2", year=2001),
                    _publication("Too new", provider="openalex", source_id="W3", year=2030),
                ],
                "cursor-2",
            ),
            _out(
                [
                    _publication(
                        "Wrong type",
                        provider="openalex",
                        source_id="W4",
                        year=2024,
                        document_type=DocumentType.REVIEW,
                    ),
                    _publication(
                        "Not OA",
                        provider="openalex",
                        source_id="W5",
                        year=2024,
                        open_access=False,
                    ),
                    _publication(
                        "OA article",
                        provider="openalex",
                        source_id="W6",
                        year=2024,
                        open_access=True,
                    ),
                ],
                None,
            ),
        ],
    )
    strategy = _strategy(
        publication_year_from=2018,
        publication_year_to=2026,
        publication_types=["article"],
        open_access=True,
    )
    _, _, status_response = run_fetch_all([provider], strategy)

    state = status_response.providers[0]
    assert state.fetched_count == 6
    assert state.kept_count == 2
    result = status_response.result
    assert result is not None
    assert [record.source_id for record in result.results] == ["W1", "W6"]


def test_unknown_language_stays_candidate_with_language_filter_v064_regression() -> None:
    """Regression (v0.6.4 semantics): language=None must be kept for ["en"]."""

    provider = FakeProvider(
        "semantic_scholar",
        [
            _out(
                [
                    _publication(
                        "Unknown language",
                        provider="semantic_scholar",
                        source_id="P1",
                        language=None,
                    ),
                    _publication(
                        "English",
                        provider="semantic_scholar",
                        source_id="P2",
                        language="en",
                    ),
                    _publication(
                        "German non-match",
                        provider="semantic_scholar",
                        source_id="P3",
                        language="de",
                    ),
                ],
                None,
            )
        ],
    )
    strategy = _strategy(
        providers=["semantic_scholar"],
        languages=["en"],
    )
    _, _, status_response = run_fetch_all([provider], strategy)

    state = status_response.providers[0]
    assert state.fetched_count == 3
    assert state.kept_count == 2
    result = status_response.result
    assert result is not None
    assert [record.source_id for record in result.results] == ["P1", "P2"]


def test_records_repeated_across_pages_are_added_only_once() -> None:
    provider = FakeProvider(
        "openalex",
        [
            _out([_publication("Dup", provider="openalex", source_id="W1")], "cursor-2"),
            _out([_publication("Dup", provider="openalex", source_id="W1")], None),
        ],
    )
    service, job, status_response = run_fetch_all([provider])
    del job

    state = status_response.providers[0]
    assert state.fetched_count == 1
    assert state.kept_count == 1
    snapshots = service._snapshot_repository.saved  # noqa: SLF001 - test assertion
    assert len(snapshots) == 1
    result = status_response.result
    assert result is not None
    assert len(result.results) == 1


# --- cancellation ------------------------------------------------------------


def test_cancel_between_pages_keeps_already_fetched_records() -> None:
    class CancelBeforeSecondPage(FakeProvider):
        def __init__(self) -> None:
            super().__init__(
                "openalex",
                [
                    _out(
                        [_publication("Kept", provider="openalex", source_id="W1")],
                        "cursor-2",
                    ),
                    _out(
                        [_publication("Also kept", provider="openalex", source_id="W2")],
                        "cursor-3",
                    ),
                    _out(
                        [_publication("Never fetched", provider="openalex", source_id="W3")],
                        None,
                    ),
                ],
            )
            self.job_holder: dict[str, Any] = {}

        async def search_with_raw(self, *, search_run, search_query, cursor="*"):
            if cursor == "cursor-2":
                self.job_holder["cancel"]()
            return await super().search_with_raw(search_run=search_run, search_query=search_query, cursor=cursor)

    provider = CancelBeforeSecondPage()

    async def factory(strategy: Any, http_client: httpx.AsyncClient) -> list[Any]:
        return [provider]

    service = FetchAllSearchService(
        provider_factory=factory,
        snapshot_repository=FakeSnapshotRepository(),
    )

    async def main():
        started = service.start("proj-1", _strategy())
        job = service.active_job_for_project("proj-1")
        assert job is not None
        provider.job_holder["cancel"] = lambda: service.request_cancel(job.job_id)
        return await service.wait(started.job_id)

    job = asyncio.run(main())
    status_response = service.get_status(job.job_id)

    assert job.cancel_requested is True
    assert status_response.status == "cancelled"
    state = status_response.providers[0]
    assert state.status == "cancelled"
    assert state.kept_count == 2
    result = status_response.result
    assert result is not None
    source_ids = [record.source_id for record in result.results]
    assert source_ids == ["W1", "W2"]
    assert result.has_more is True


# --- warnings / lossless propagation ----------------------------------------


def test_provider_warnings_and_losslessness_survive_fetch_all() -> None:
    warning = "Semantic Scholar relevance search does not support language filtering."
    provider = FakeProvider(
        "semantic_scholar",
        [
            _out(
                [_publication("S1", provider="semantic_scholar", source_id="P1")],
                None,
                warnings=(warning,),
                is_lossless=False,
            )
        ],
    )
    strategy = _strategy(providers=["semantic_scholar"], languages=["en"])
    _, _, status_response = run_fetch_all([provider], strategy)

    result = status_response.result
    assert result is not None
    assert len(result.provider_queries) == 1
    query = result.provider_queries[0]
    assert query.is_lossless is False
    assert warning in query.warnings


def test_cross_provider_doi_dedup_persists_one_snapshot_with_both_provenances() -> None:
    openalex = FakeProvider(
        "openalex",
        [
            _out(
                [
                    _publication(
                        "Lean result",
                        provider="openalex",
                        source_id="W1",
                        doi="10.1000/shared",
                    )
                ]
            )
        ],
    )
    crossref = FakeProvider(
        "crossref",
        [
            _out(
                [
                    _publication(
                        "Lean duplicate",
                        provider="crossref",
                        source_id="10.1000/shared",
                        doi="10.1000/shared",
                    )
                ]
            )
        ],
    )

    service, _, status = run_fetch_all(
        [openalex, crossref],
        _strategy(providers=["openalex", "crossref"]),
    )

    assert status.result is not None
    assert status.result.returned_count == 1
    assert status.result.deduplicated_count == 1
    repository = service._snapshot_repository
    assert isinstance(repository, FakeSnapshotRepository)
    assert len(repository.saved) == 1
    assert [entry.source for entry in repository.saved[0].publication.provenance] == ["openalex", "crossref"]


def test_job_status_reports_running_state_before_completion() -> None:
    started_flag: dict[str, bool] = {"started": False}

    class BlockingProvider(FakeProvider):
        async def search_with_raw(self, *, search_run, search_query, cursor="*"):
            started_flag["started"] = True
            import asyncio as _asyncio

            await _asyncio.sleep(0.2)
            return await super().search_with_raw(search_run=search_run, search_query=search_query, cursor=cursor)

    provider = BlockingProvider(
        "openalex",
        [_out([_publication("Slow", provider="openalex", source_id="W1")], None)],
    )

    async def factory(strategy: Any, http_client: httpx.AsyncClient) -> list[Any]:
        return [provider]

    service = FetchAllSearchService(
        provider_factory=factory,
        snapshot_repository=FakeSnapshotRepository(),
        poll_interval_seconds=0.01,
    )

    async def main():
        started = service.start("proj-1", _strategy())
        while not started_flag["started"]:
            await asyncio.sleep(0.005)
        running_status = service.get_status(started.job_id)
        finished_job = await service.wait(started.job_id)
        return running_status, finished_job

    running_status, job = asyncio.run(main())

    assert running_status.status == "running"
    assert running_status.providers[0].status == "running"
    assert job.status == "completed"


# --- registry behaviour -------------------------------------------------------


def test_second_parallel_fetch_all_for_same_project_is_rejected() -> None:
    provider = FakeProvider(
        "openalex",
        [_out([_publication("A1", provider="openalex", source_id="W1")], None)],
    )

    async def factory(strategy: Any, http_client: httpx.AsyncClient) -> list[Any]:
        return [provider]

    service = FetchAllSearchService(
        provider_factory=factory,
        snapshot_repository=FakeSnapshotRepository(),
    )

    from app.services.fetch_all_search import FetchAllJobAlreadyRunningError

    async def main():
        service.start("proj-1", _strategy())
        try:
            service.start("proj-1", _strategy())
        except FetchAllJobAlreadyRunningError:
            return "rejected"
        finally:
            job = service.active_job_for_project("proj-1")
            if job is not None:
                await service.wait(job.job_id)
        return "allowed"

    outcome = asyncio.run(main())

    assert outcome == "rejected"


def test_finished_jobs_are_pruned_to_the_retention_limit() -> None:
    provider = FakeProvider(
        "openalex",
        [_out([_publication(f"A{i}", provider="openalex", source_id=f"W{i}")], None) for i in range(30)],
    )

    async def factory(strategy: Any, http_client: httpx.AsyncClient) -> list[Any]:
        return [provider]

    service = FetchAllSearchService(
        provider_factory=factory,
        snapshot_repository=FakeSnapshotRepository(),
    )

    async def main():
        job_ids = []
        for index in range(30):
            started = service.start(f"project-{index}", _strategy())
            job_ids.append(started.job_id)
            await service.wait(started.job_id)
        return job_ids

    asyncio.run(main())

    from app.services.fetch_all_search import MAX_FINISHED_JOBS_KEPT

    assert len(service._jobs) <= MAX_FINISHED_JOBS_KEPT + 1  # noqa: SLF001


# --- 429 Retry-After integration through the real client ---------------------


def test_semantic_scholar_429_retry_after_is_honored_inside_fetch_all() -> None:
    paper_payload = {
        "total": 1,
        "offset": 0,
        "next": None,
        "data": [
            {
                "paperId": "abc123",
                "title": "Rate limited but recovered",
                "authors": [{"name": "Ada Author"}],
                "year": 2024,
            }
        ],
    }
    calls: list[int] = []
    sleeps: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        if len(calls) <= 2:
            return httpx.Response(429, headers={"Retry-After": "0"}, json={})
        return httpx.Response(200, json=paper_payload)

    transport = httpx.MockTransport(handler)

    async def sleep_tracker(seconds: float) -> None:
        sleeps.append(seconds)
        await asyncio.sleep(0)

    async def factory(strategy: Any, http_client: httpx.AsyncClient) -> list[Any]:
        from app.providers.search.semantic_scholar import SemanticScholarProvider
        from app.providers.semantic_scholar import SemanticScholarClient

        client = SemanticScholarClient(
            http_client=httpx.AsyncClient(transport=transport, base_url="https://x"),
            requests_per_second=None,
            sleep=sleep_tracker,
        )
        del http_client
        return [SemanticScholarProvider(client=client, paginate=True)]

    service = FetchAllSearchService(
        provider_factory=factory,
        snapshot_repository=FakeSnapshotRepository(),
    )

    async def main():
        started = service.start("proj-1", _strategy(providers=["semantic_scholar"]))
        return await service.wait(started.job_id)

    job = asyncio.run(main())
    status_response = service.get_status(job.job_id)

    assert len(calls) >= 3
    assert len(sleeps) >= 2
    state = status_response.providers[0]
    assert state.status == "complete"
    assert state.fetched_count == 1
    result = status_response.result
    assert result is not None
    assert result.results[0].source_id == "abc123"


# --- JSON serialization sanity ------------------------------------------------


def test_status_response_serializes_for_api_clients() -> None:
    provider = FakeProvider(
        "openalex",
        [_out([_publication("A1", provider="openalex", source_id="W1")], None)],
    )
    _, _, status_response = run_fetch_all([provider])

    payload = status_response.model_dump(mode="json")
    assert payload["status"] == "completed"
    assert payload["providers"][0]["status"] == "complete"
    assert payload["result"]["returned_count"] == 1
