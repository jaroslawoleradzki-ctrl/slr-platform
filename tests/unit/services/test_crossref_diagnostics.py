"""WP2 — Crossref diagnostic provenance and replay dataset regressions.

All provider traffic is local via ``httpx.MockTransport``; no live Crossref
fetch is performed.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import UUID

import httpx
import pytest

from app.api.dto.search_strategy import ConceptGroupRequest, SearchStrategyExecutionRequest
from app.domain.crossref_diagnostics import (
    CrossrefRecordDiagnostic,
    RetentionOutcome,
    build_crossref_replay_dataset,
)
from app.domain.search import SearchQuery, SearchRun, SearchTerm
from app.providers.crossref import CrossrefClient
from app.providers.search.crossref import CrossrefProvider
from app.repositories.search_result_snapshot_repository import SqliteSearchResultSnapshotRepository
from app.repositories.search_run_checkpoint_repository import SqliteSearchRunCheckpointRepository
from app.services.canonical_query_validator import CanonicalMatchStatus
from app.services.fetch_all_search import FetchAllSearchService
from app.services.live_search import build_search_query


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def _strategy() -> SearchStrategyExecutionRequest:
    return SearchStrategyExecutionRequest(
        publication_year_from=2020,
        publication_year_to=2025,
        providers=["crossref"],
        concept_groups=[
            ConceptGroupRequest(id="g1", name="Greek", terms=["Alpha", "Beta"]),
            ConceptGroupRequest(id="g2", name="Gamma", terms=["Gamma"]),
        ],
        languages=["en"],
        publication_types=["article"],
        open_access=False,
    )


def _item(
    doi: str,
    title: str,
    *,
    abstract: str | None = "Alpha Gamma research advances the field.",
    score: float | None = None,
    language: str | None = None,
) -> dict[str, Any]:
    item: dict[str, Any] = {
        "DOI": doi,
        "title": [title],
        "type": "journal-article",
        "published": {"date-parts": [[2024, 5, 1]]},
    }
    if abstract is not None:
        item["abstract"] = abstract
    if score is not None:
        item["score"] = score
    if language is not None:
        item["language"] = language
    return item


_MATCH = _item("10.1000/a", "Alpha Gamma breakthrough study", score=7.5)
_NO_ABSTRACT = _item("10.1000/b", "Unrelated robotics paper", abstract=None)
_NON_MATCH = _item(
    "10.1000/c",
    "Unrelated ceramics overview",
    abstract="A survey of kiln temperatures and clay bodies.",
)
_CONSTRAINED = _item(
    "10.1000/d",
    "Alpha Gamma breakthrough study",
    abstract="Alpha Gamma research.",
    language="de",
)


def _make_handler(requests: list[tuple[str, str]]) -> Any:
    async def handler(request: httpx.Request) -> httpx.Response:
        query = request.url.params["query"]
        cursor = request.url.params.get("cursor", "*")
        requests.append((query, cursor))
        if query == '"Alpha" "Gamma"':
            items: list[dict[str, Any]] = [_MATCH, _NO_ABSTRACT]
        else:
            assert query == '"Beta" "Gamma"'
            items = [_MATCH, _NON_MATCH, _CONSTRAINED]
            # Second retrieval path for the duplicate DOI with its own score.
            items[0] = _item("10.1000/a", "Alpha Gamma breakthrough study", score=6.0)
        return httpx.Response(
            200,
            json={"message": {"items": items, "next-cursor": None, "total-results": len(items)}},
            request=request,
        )

    return handler


def _provider_factory(
    http_client: httpx.AsyncClient,
    requests: list[tuple[str, str]],
    *,
    max_physical_requests_per_call: int = 10,
) -> Any:
    def factory(strategy: SearchStrategyExecutionRequest, client: httpx.AsyncClient) -> list[CrossrefProvider]:
        return [
            CrossrefProvider(
                client=CrossrefClient(http_client=http_client, requests_per_second=None),
                paginate=True,
                max_physical_requests_per_call=max_physical_requests_per_call,
            )
        ]

    return factory


async def _run_fetch_all(
    tmp_path: Path,
    requests: list[tuple[str, str]],
    db_name: str = "wp2.db",
    *,
    max_pages_per_provider: int = 20,
) -> tuple[FetchAllSearchService, Any]:
    db_path = tmp_path / db_name
    handler = _make_handler(requests)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        service = FetchAllSearchService(
            provider_factory=_provider_factory(http_client, requests),
            snapshot_repository=SqliteSearchResultSnapshotRepository(db_path),
            checkpoint_repository=SqliteSearchRunCheckpointRepository(db_path),
            max_pages_per_provider=max_pages_per_provider,
        )
        started = service.start("wp2-provenance", _strategy())
        job = await service.wait(started.job_id)
    return service, job


def _diagnostics_by_source(service: FetchAllSearchService, job_id: str) -> dict[str, CrossrefRecordDiagnostic]:
    job = service._jobs[job_id]
    return {item.source_record_id: item for state in job.providers for item in state.record_diagnostics}


@pytest.mark.anyio
async def test_provider_attaches_physical_query_to_provenance() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "message": {
                    "items": [_item("10.1000/a", "Alpha study", score=7.5)],
                    "next-cursor": None,
                }
            },
            request=request,
        )

    query = SearchQuery(name="Single", expression=SearchTerm(value="Alpha", exact_phrase=True))
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        provider = CrossrefProvider(
            client=CrossrefClient(http_client=http_client, requests_per_second=None),
            paginate=True,
        )
        output = await provider.search_with_raw(
            search_run=SearchRun(
                query_id=query.query_id,
                query_version=query.version,
                provider="crossref",
                rendered_query='"Alpha"',
            ),
            search_query=query,
        )

    assert len(output.publications) == 1
    entry = output.publications[0].provenance[0]
    assert entry.physical_query == '"Alpha"'
    assert entry.physical_query_index == 0
    assert entry.result_rank == 0
    assert entry.physical_cursor == "*"
    assert entry.provider_score == 7.5


@pytest.mark.anyio
async def test_provider_records_index_rank_and_score_across_queries() -> None:
    requests: list[tuple[str, str]] = []
    handler = _make_handler(requests)
    strategy = _strategy()
    query = build_search_query(strategy)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        provider = CrossrefProvider(
            client=CrossrefClient(http_client=http_client, requests_per_second=None),
            paginate=True,
        )
        output = await provider.search_with_raw(
            search_run=SearchRun(
                query_id=query.query_id,
                query_version=query.version,
                provider="crossref",
                rendered_query="...",
            ),
            search_query=query,
        )

    assert [request[0] for request in requests] == ['"Alpha" "Gamma"', '"Beta" "Gamma"']
    by_source = {publication.provenance[0].source_record_id: publication for publication in output.publications}
    # Duplicate DOI merged into one publication with two retrieval paths.
    assert set(by_source) == {"10.1000/a", "10.1000/b", "10.1000/c", "10.1000/d"}
    merged = by_source["10.1000/a"].provenance
    assert len(merged) == 2
    assert [(entry.physical_query_index, entry.result_rank) for entry in merged] == [(0, 0), (1, 0)]
    assert [entry.provider_score for entry in merged] == [7.5, 6.0]
    assert [entry.physical_cursor for entry in merged] == ["*", "*"]
    # Record without a supplier score keeps an explicit null.
    assert by_source["10.1000/b"].provenance[0].provider_score is None
    assert by_source["10.1000/b"].provenance[0].result_rank == 1


@pytest.mark.anyio
async def test_fetch_all_diagnostic_records_match_and_evidence(tmp_path: Path) -> None:
    requests: list[tuple[str, str]] = []
    service, job = await _run_fetch_all(tmp_path, requests)
    assert job.status == "completed"

    diagnostics = _diagnostics_by_source(service, job.job_id)
    assert set(diagnostics) == {"10.1000/a", "10.1000/b", "10.1000/c", "10.1000/d"}

    match = diagnostics["10.1000/a"]
    assert match.canonical_status is CanonicalMatchStatus.MATCH
    assert match.retention_outcome is RetentionOutcome.RETAINED
    assert match.doi == "10.1000/a"
    assert len(match.group_evidence) == 2
    assert all(group.status is CanonicalMatchStatus.MATCH for group in match.group_evidence)
    assert match.completeness.abstract_present is True
    assert match.completeness.doi_present is True
    assert match.completeness.title_present is True
    # Duplicate DOI retrieved through both physical queries keeps both paths.
    assert [(path.physical_query_index, path.result_rank) for path in match.retrieval_paths] == [(0, 0), (1, 0)]
    assert [path.provider_score for path in match.retrieval_paths] == [7.5, 6.0]


@pytest.mark.anyio
async def test_fetch_all_missing_abstract_is_represented(tmp_path: Path) -> None:
    requests: list[tuple[str, str]] = []
    service, job = await _run_fetch_all(tmp_path, requests)

    diagnostics = _diagnostics_by_source(service, job.job_id)
    missing = diagnostics["10.1000/b"]
    assert missing.completeness.abstract_present is False
    assert missing.canonical_status is CanonicalMatchStatus.INDETERMINATE
    assert "abstract" in missing.group_evidence[0].missing_fields
    # Recall-first retention: indeterminate records are still retained.
    assert missing.retention_outcome is RetentionOutcome.RETAINED


@pytest.mark.anyio
async def test_fetch_all_retained_vs_rejected_outcomes(tmp_path: Path) -> None:
    requests: list[tuple[str, str]] = []
    service, job = await _run_fetch_all(tmp_path, requests)

    diagnostics = _diagnostics_by_source(service, job.job_id)
    rejected = diagnostics["10.1000/c"]
    assert rejected.canonical_status is CanonicalMatchStatus.NON_MATCH
    assert rejected.retention_outcome is RetentionOutcome.REJECTED_CANONICAL
    constrained = diagnostics["10.1000/d"]
    assert constrained.canonical_status is CanonicalMatchStatus.MATCH
    assert constrained.retention_outcome is RetentionOutcome.REJECTED_CONSTRAINTS
    # Counters agree with the recorded outcomes (WP1 semantics unchanged).
    assert job.providers[0].fetched_count == 4
    assert job.providers[0].canonical_accepted_count == 2
    assert job.providers[0].canonical_rejected_count == 1
    assert job.providers[0].canonical_indeterminate_count == 1
    assert job.providers[0].kept_count == 2


@pytest.mark.anyio
async def test_provenance_survives_checkpoint_restart(tmp_path: Path) -> None:
    requests: list[tuple[str, str]] = []
    service, job = await _run_fetch_all(tmp_path, requests)
    live_rows = service.get_crossref_replay_dataset(job.job_id)
    assert live_rows

    restarted = FetchAllSearchService(
        snapshot_repository=SqliteSearchResultSnapshotRepository(tmp_path / "wp2.db"),
        checkpoint_repository=SqliteSearchRunCheckpointRepository(tmp_path / "wp2.db"),
    )
    historical_rows = restarted.get_crossref_replay_dataset(job.job_id)
    assert historical_rows == live_rows
    # WP1 accounting still reconstructs identically after restart.
    assert restarted.get_status(job.job_id).kept_total == 2
    assert restarted.get_status(job.job_id).fetched_total == 4


@pytest.mark.anyio
async def test_provenance_correct_after_resume_without_replay(tmp_path: Path) -> None:
    db_path = tmp_path / "wp2-resume.db"
    requests: list[tuple[str, str]] = []

    async def run_session(*, max_pages: int, resume_from: str | None = None) -> Any:
        handler = _make_handler(requests)
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
            service = FetchAllSearchService(
                provider_factory=_provider_factory(
                    http_client, requests, max_physical_requests_per_call=1
                ),
                snapshot_repository=SqliteSearchResultSnapshotRepository(db_path),
                checkpoint_repository=SqliteSearchRunCheckpointRepository(db_path),
                max_pages_per_provider=max_pages,
            )
            if resume_from is None:
                started = service.start("wp2-resume", _strategy())
            else:
                started = service.start_resume_job("wp2-resume", resume_from)
            return service, await service.wait(started.job_id)

    service1, job1 = await run_session(max_pages=1)
    # One physical request per provider call: session 1 executes only the
    # first physical query, then the page cap stops the job as partial.
    assert job1.providers[0].status == "partial"
    before_requests = list(requests)
    assert before_requests == [('"Alpha" "Gamma"', "*")]

    service2, job2 = await run_session(max_pages=20, resume_from=job1.job_id)
    assert job2.status == "completed"
    resumed_requests = requests[len(before_requests):]
    assert resumed_requests
    assert not set(before_requests).intersection(resumed_requests)

    diagnostics = _diagnostics_by_source(service2, job2.job_id)
    assert set(diagnostics) == {"10.1000/a", "10.1000/b", "10.1000/c", "10.1000/d"}
    assert len(diagnostics["10.1000/a"].retrieval_paths) == 2
    assert diagnostics["10.1000/c"].retention_outcome is RetentionOutcome.REJECTED_CANONICAL

    # Historical reconstruction from a fresh instance over the same database.
    fresh = FetchAllSearchService(
        snapshot_repository=SqliteSearchResultSnapshotRepository(db_path),
        checkpoint_repository=SqliteSearchRunCheckpointRepository(db_path),
    )
    assert fresh.get_crossref_replay_dataset(job2.job_id) == service2.get_crossref_replay_dataset(job2.job_id)
    assert fresh.get_status(job2.job_id).kept_total == 2


def test_replay_dataset_is_deterministic() -> None:
    diagnostic = CrossrefRecordDiagnostic(
        source_record_id="10.1000/a",
        doi="10.1000/a",
        title="Alpha Gamma breakthrough study",
        search_run_id=UUID("11111111-1111-4111-8111-111111111111"),
        retrieval_paths=(),
        canonical_status=CanonicalMatchStatus.MATCH,
        retention_outcome=RetentionOutcome.RETAINED,
    )
    first = build_crossref_replay_dataset([diagnostic], job_id="job-1")
    second = build_crossref_replay_dataset([diagnostic], job_id="job-1")
    assert first == second
    assert len(first) == 1
    row = first[0]
    assert row["job_id"] == "job-1"
    assert row["source_record_id"] == "10.1000/a"
    assert row["physical_query"] is None
    assert row["canonical_status"] == "match"
    assert row["retention_outcome"] == "retained"
    assert set(row) == {
        "job_id",
        "search_run_id",
        "source_record_id",
        "doi",
        "title",
        "physical_query",
        "physical_query_index",
        "physical_cursor",
        "result_rank",
        "provider_score",
        "metadata_completeness",
        "canonical_group_evidence",
        "canonical_status",
        "retention_outcome",
    }
