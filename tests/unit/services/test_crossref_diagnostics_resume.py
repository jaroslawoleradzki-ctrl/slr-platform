"""WP2.1 — provenance correction regressions.

Covers the independent-review findings: Resume duplicate identity for
rejected/constrained candidates, Crossref score overflow, NOT/positive-group
semantics, replay path-level shape after Resume, backward compatibility, and
a checkpoint scaling benchmark. All provider traffic is local via
``httpx.MockTransport``.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import httpx
import pytest

from app.api.dto.search_strategy import ConceptGroupRequest, SearchStrategyExecutionRequest
from app.domain.crossref_diagnostics import (
    CrossrefRecordDiagnostic,
    RetentionOutcome,
    group_evidence_for,
)
from app.domain.publication import Publication
from app.domain.search import BooleanOperator, SearchGroup, SearchQuery, SearchRun, SearchTerm
from app.providers.crossref import CrossrefClient
from app.providers.search.crossref import CrossrefProvider, _read_crossref_score
from app.repositories.search_result_snapshot_repository import SqliteSearchResultSnapshotRepository
from app.repositories.search_run_checkpoint_repository import (
    SearchRunCheckpoint,
    SqliteSearchRunCheckpointRepository,
)
from app.services.canonical_query_validator import CanonicalMatchStatus
from app.services.fetch_all_search import FetchAllSearchService
from app.services.live_search import build_search_query


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def _strategy(*, languages: list[str] | None = None) -> SearchStrategyExecutionRequest:
    return SearchStrategyExecutionRequest(
        publication_year_from=2020,
        publication_year_to=2025,
        providers=["crossref"],
        concept_groups=[
            ConceptGroupRequest(id="g1", name="Greek", terms=["Alpha", "Beta"]),
            ConceptGroupRequest(id="g2", name="Gamma", terms=["Gamma"]),
        ],
        languages=languages or [],
        publication_types=["article"],
        open_access=False,
    )


def _item(
    doi: str,
    title: str,
    *,
    abstract: str | None = "Alpha Gamma research advances the field.",
    score: Any = None,
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


_X_NON_MATCH_Q0 = _item("10.9/x", "Unrelated ceramics overview", abstract="Kiln survey.", score=3.0)
_X_NON_MATCH_Q1 = _item("10.9/x", "Unrelated ceramics overview", abstract="Kiln survey.", score=2.5)
_K_MATCH_Q0 = _item("10.9/k", "Alpha Gamma breakthrough", score=9.0)
_K_MATCH_Q1 = _item("10.9/k", "Alpha Gamma breakthrough", score=8.0)
_XC_CONSTRAINED = _item(
    "10.9/xc", "Alpha Gamma breakthrough", abstract="Alpha Gamma research.", language="de"
)


def _resume_handler(requests: list[tuple[str, str]], *, constrained: bool = False) -> Any:
    async def handler(request: httpx.Request) -> httpx.Response:
        query = request.url.params["query"]
        cursor = request.url.params.get("cursor", "*")
        requests.append((query, cursor))
        if constrained:
            items = [_XC_CONSTRAINED]
        elif query == '"Alpha" "Gamma"':
            items = [_X_NON_MATCH_Q0, _K_MATCH_Q0]
        else:
            assert query == '"Beta" "Gamma"'
            items = [_X_NON_MATCH_Q1, _K_MATCH_Q1]
        return httpx.Response(
            200,
            json={"message": {"items": items, "next-cursor": None, "total-results": len(items)}},
            request=request,
        )

    return handler


def _factory(http_client: httpx.AsyncClient) -> Any:
    def factory(strategy: SearchStrategyExecutionRequest, client: httpx.AsyncClient) -> list[CrossrefProvider]:
        return [
            CrossrefProvider(
                client=CrossrefClient(http_client=http_client, requests_per_second=None),
                paginate=True,
                max_physical_requests_per_call=1,
            )
        ]

    return factory


async def _run_session(
    db_path: Path,
    requests: list[tuple[str, str]],
    strategy: SearchStrategyExecutionRequest,
    *,
    max_pages: int,
    resume_from: str | None = None,
    constrained: bool = False,
) -> tuple[FetchAllSearchService, Any]:
    handler = _resume_handler(requests, constrained=constrained)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        service = FetchAllSearchService(
            provider_factory=_factory(http_client),
            snapshot_repository=SqliteSearchResultSnapshotRepository(db_path),
            checkpoint_repository=SqliteSearchRunCheckpointRepository(db_path),
            max_pages_per_provider=max_pages,
        )
        if resume_from is None:
            started = service.start("wp21-resume", strategy)
        else:
            started = service.start_resume_job("wp21-resume", resume_from)
        return service, await service.wait(started.job_id)


def _diagnostics(service: FetchAllSearchService, job_id: str) -> dict[str, CrossrefRecordDiagnostic]:
    job = service._jobs[job_id]
    return {item.source_record_id: item for state in job.providers for item in state.record_diagnostics}


@pytest.mark.anyio
async def test_rejected_duplicate_across_resume_matches_uninterrupted(tmp_path: Path) -> None:
    strategy = _strategy()
    # Uninterrupted reference run.
    ref_requests: list[tuple[str, str]] = []
    ref_service, ref_job = await _run_session(
        tmp_path / "ref.db", ref_requests, strategy, max_pages=20
    )
    ref_state = ref_job.providers[0]
    assert (ref_state.fetched_count, ref_state.kept_count, ref_state.canonical_rejected_count) == (2, 1, 1)
    ref_diagnostics = _diagnostics(ref_service, ref_job.job_id)
    assert set(ref_diagnostics) == {"10.9/x", "10.9/k"}
    assert len(ref_diagnostics["10.9/x"].retrieval_paths) == 2

    # Interrupted run: stop after physical query 0, Resume with a fresh service.
    requests: list[tuple[str, str]] = []
    db_path = tmp_path / "resume.db"
    _, job1 = await _run_session(db_path, requests, strategy, max_pages=1)
    assert job1.providers[0].status == "partial"
    assert requests == [('"Alpha" "Gamma"', "*")]
    service2, job2 = await _run_session(db_path, requests, strategy, max_pages=20, resume_from=job1.job_id)

    state = job2.providers[0]
    assert state.status == "complete"
    assert requests == [('"Alpha" "Gamma"', "*"), ('"Beta" "Gamma"', "*")]
    # Logical result must not depend on the restart boundary.
    assert state.fetched_count == ref_state.fetched_count == 2
    assert state.kept_count == ref_state.kept_count == 1
    assert state.canonical_rejected_count == ref_state.canonical_rejected_count == 1
    assert state.canonical_accepted_count == ref_state.canonical_accepted_count == 1
    diagnostics = _diagnostics(service2, job2.job_id)
    assert set(diagnostics) == set(ref_diagnostics)
    rejected = diagnostics["10.9/x"]
    assert rejected.retention_outcome is RetentionOutcome.REJECTED_CANONICAL
    assert [(p.physical_query_index, p.result_rank) for p in rejected.retrieval_paths] == [(0, 0), (1, 0)]
    assert [p.provider_score for p in rejected.retrieval_paths] == [3.0, 2.5]
    kept = diagnostics["10.9/k"]
    assert kept.retention_outcome is RetentionOutcome.RETAINED
    assert len(kept.retrieval_paths) == 2


@pytest.mark.anyio
async def test_constrained_duplicate_across_resume_matches_uninterrupted(tmp_path: Path) -> None:
    strategy = _strategy(languages=["en"])
    ref_requests: list[tuple[str, str]] = []
    ref_service, ref_job = await _run_session(
        tmp_path / "cref.db", ref_requests, strategy, max_pages=20, constrained=True
    )
    ref_state = ref_job.providers[0]
    assert (ref_state.fetched_count, ref_state.kept_count, ref_state.canonical_accepted_count) == (1, 0, 1)
    ref_diagnostics = _diagnostics(ref_service, ref_job.job_id)
    assert set(ref_diagnostics) == {"10.9/xc"}
    assert ref_diagnostics["10.9/xc"].retention_outcome is RetentionOutcome.REJECTED_CONSTRAINTS

    requests: list[tuple[str, str]] = []
    db_path = tmp_path / "cresume.db"
    _, job1 = await _run_session(db_path, requests, strategy, max_pages=1, constrained=True)
    assert job1.providers[0].status == "partial"
    service2, job2 = await _run_session(
        db_path, requests, strategy, max_pages=20, resume_from=job1.job_id, constrained=True
    )

    state = job2.providers[0]
    assert state.fetched_count == 1
    assert state.kept_count == 0
    assert state.canonical_accepted_count == 1
    diagnostics = _diagnostics(service2, job2.job_id)
    assert set(diagnostics) == {"10.9/xc"}
    assert diagnostics["10.9/xc"].retention_outcome is RetentionOutcome.REJECTED_CONSTRAINTS
    assert len(diagnostics["10.9/xc"].retrieval_paths) == 2


@pytest.mark.anyio
async def test_replay_rows_are_path_level_after_resume(tmp_path: Path) -> None:
    strategy = _strategy()
    requests: list[tuple[str, str]] = []
    db_path = tmp_path / "replay.db"
    _, job1 = await _run_session(db_path, requests, strategy, max_pages=1)
    service2, job2 = await _run_session(db_path, requests, strategy, max_pages=20, resume_from=job1.job_id)

    rows = service2.get_crossref_replay_dataset(job2.job_id)
    by_source: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_source.setdefault(row["source_record_id"], []).append(row)
    assert set(by_source) == {"10.9/x", "10.9/k"}
    # One logical candidate per source in the durable diagnostics ...
    job = service2._jobs[job2.job_id]
    diagnostic_sources = [item.source_record_id for state in job.providers for item in state.record_diagnostics]
    assert sorted(diagnostic_sources) == ["10.9/k", "10.9/x"]
    # One logical candidate, two path rows, each path fully described.
    assert len(by_source["10.9/x"]) == 2
    assert [(row["physical_query_index"], row["result_rank"]) for row in by_source["10.9/x"]] == [(0, 0), (1, 0)]
    assert [row["physical_query"] for row in by_source["10.9/x"]] == ['"Alpha" "Gamma"', '"Beta" "Gamma"']
    assert [row["provider_score"] for row in by_source["10.9/x"]] == [3.0, 2.5]
    assert all(row["physical_cursor"] == "*" for row in by_source["10.9/x"])
    assert by_source["10.9/x"][0]["retention_outcome"] == "rejected_canonical_validation"
    assert by_source["10.9/x"][0]["canonical_status"] == "non_match"


@pytest.mark.anyio
async def test_old_checkpoint_without_diagnostics_remains_resumable(tmp_path: Path) -> None:
    db_path = tmp_path / "old.db"
    strategy = _strategy()
    job_id = uuid4()
    search_run_id = uuid4()
    now = datetime.now(timezone.utc)
    SqliteSearchRunCheckpointRepository(db_path).save_checkpoint(
        SearchRunCheckpoint(
            search_run_id=search_run_id,
            project_id="wp21-old",
            job_id=job_id,
            provider="crossref",
            cursor="*",
            pages_fetched=0,
            fetched_count=0,
            canonical_accepted_count=0,
            canonical_rejected_count=0,
            canonical_indeterminate_count=0,
            deduplicated_count=0,
            status="partial",
            resumable=True,
            plan_metadata={"strategy": strategy.model_dump(mode="json")},
            warnings=(),
            created_at=now,
            updated_at=now,
        )
    )
    requests: list[tuple[str, str]] = []
    handler = _resume_handler(requests)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        service = FetchAllSearchService(
            provider_factory=_factory(http_client),
            snapshot_repository=SqliteSearchResultSnapshotRepository(db_path),
            checkpoint_repository=SqliteSearchRunCheckpointRepository(db_path),
            max_pages_per_provider=20,
        )
        resumed = service.start_resume_job("wp21-old", str(job_id))
        job = await service.wait(resumed.job_id)
    assert job.status == "completed"
    diagnostics = _diagnostics(service, job.job_id)
    assert set(diagnostics) == {"10.9/x", "10.9/k"}


@pytest.mark.anyio
async def test_corrupt_diagnostic_row_does_not_break_resume(tmp_path: Path) -> None:
    db_path = tmp_path / "corrupt.db"
    strategy = _strategy()
    requests: list[tuple[str, str]] = []
    _, job1 = await _run_session(db_path, requests, strategy, max_pages=1)
    checkpoint_repo = SqliteSearchRunCheckpointRepository(db_path)
    checkpoints = checkpoint_repo.get_checkpoints_for_job(UUID(job1.job_id))
    assert len(checkpoints) == 1
    poisoned = dict(checkpoints[0].plan_metadata or {})
    valid_rows = list(poisoned.get("record_diagnostics", []))
    assert valid_rows
    poisoned["record_diagnostics"] = valid_rows + [{"bogus": "row"}, "not-a-dict", 42]
    checkpoint_repo.save_checkpoint(
        SearchRunCheckpoint(
            search_run_id=checkpoints[0].search_run_id,
            project_id=checkpoints[0].project_id,
            job_id=checkpoints[0].job_id,
            provider=checkpoints[0].provider,
            cursor=checkpoints[0].cursor,
            pages_fetched=checkpoints[0].pages_fetched,
            fetched_count=checkpoints[0].fetched_count,
            canonical_accepted_count=checkpoints[0].canonical_accepted_count,
            canonical_rejected_count=checkpoints[0].canonical_rejected_count,
            canonical_indeterminate_count=checkpoints[0].canonical_indeterminate_count,
            deduplicated_count=checkpoints[0].deduplicated_count,
            status=checkpoints[0].status,
            resumable=True,
            plan_metadata=poisoned,
            warnings=checkpoints[0].warnings,
            created_at=checkpoints[0].created_at,
            updated_at=checkpoints[0].updated_at,
        )
    )
    service2, job2 = await _run_session(db_path, requests, strategy, max_pages=20, resume_from=job1.job_id)
    assert job2.status == "completed"
    diagnostics = _diagnostics(service2, job2.job_id)
    assert set(diagnostics) == {"10.9/x", "10.9/k"}


@pytest.mark.anyio
async def test_crossref_score_overflow_becomes_null_without_aborting() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "message": {
                    "items": [
                        _item("10.9/big", "Alpha Gamma study", score=10**400),
                        _item("10.9/ok", "Alpha Gamma study", score=5),
                    ],
                    "next-cursor": None,
                }
            },
            request=request,
        )

    query = build_search_query(_strategy())
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
    assert len(output.publications) == 2
    by_source = {publication.provenance[0].source_record_id: publication for publication in output.publications}
    assert by_source["10.9/big"].provenance[0].provider_score is None
    assert by_source["10.9/ok"].provenance[0].provider_score == 5.0


def test_read_crossref_score_edge_cases() -> None:
    assert _read_crossref_score({"score": 7.5}) == 7.5
    assert _read_crossref_score({"score": 5}) == 5.0
    assert _read_crossref_score({}) is None
    assert _read_crossref_score({"score": None}) is None
    assert _read_crossref_score({"score": "high"}) is None
    assert _read_crossref_score({"score": True}) is None
    assert _read_crossref_score({"score": float("nan")}) is None
    assert _read_crossref_score({"score": float("inf")}) is None
    assert _read_crossref_score({"score": 10**400}) is None
    assert _read_crossref_score({"score": -10**400}) is None
    assert _read_crossref_score("not-a-dict") is None


def _pub_for_groups(title: str, abstract: str | None) -> Publication:
    return Publication(title=title, abstract=abstract, publication_year=2024)


def test_not_child_is_not_a_positive_group() -> None:
    query = SearchQuery(
        name="AND with NOT",
        expression=SearchGroup(
            operator=BooleanOperator.AND,
            children=[
                SearchTerm(value="Alpha", exact_phrase=True),
                SearchTerm(value="Gamma", exact_phrase=True),
                SearchGroup(operator=BooleanOperator.NOT, children=[SearchTerm(value="Beta")]),
            ],
        ),
    )
    publication = _pub_for_groups("Alpha Gamma study", "Alpha Gamma research.")
    evidence = group_evidence_for(query, publication)
    assert [group.group_index for group in evidence] == [0, 1]
    assert all("Beta" not in group.group_query for group in evidence)
    assert all(group.status is CanonicalMatchStatus.MATCH for group in evidence)


def test_pure_not_query_yields_no_positive_groups() -> None:
    query = SearchQuery(
        name="Pure NOT",
        expression=SearchGroup(operator=BooleanOperator.NOT, children=[SearchTerm(value="Beta")]),
    )
    evidence = group_evidence_for(query, _pub_for_groups("Alpha study", "Alpha research."))
    assert evidence == ()


def test_positive_and_children_still_counted() -> None:
    query = build_search_query(_strategy())
    evidence = group_evidence_for(query, _pub_for_groups("Alpha Gamma breakthrough", "Alpha Gamma research."))
    assert len(evidence) == 2
    assert [group.group_index for group in evidence] == [0, 1]


def test_checkpoint_scaling_at_provider_cap(tmp_path: Path) -> None:
    from app.domain.crossref_diagnostics import (
        CanonicalGroupEvidence,
        CrossrefMetadataCompleteness,
        CrossrefRetrievalPath,
    )

    diagnostics = [
        CrossrefRecordDiagnostic(
            source_record_id=f"10.9/{index}",
            doi=f"10.9/{index}",
            title=f"Alpha Gamma diagnostic record number {index} with a representative title",
            retrieval_paths=(
                CrossrefRetrievalPath(
                    physical_query='"Alpha" "Gamma"',
                    physical_query_index=index % 6,
                    physical_cursor="*",
                    result_rank=index % 20,
                    provider_score=7.5,
                ),
            ),
            completeness=CrossrefMetadataCompleteness(
                title_present=True, abstract_present=index % 2 == 0, doi_present=True
            ),
            canonical_status=(
                CanonicalMatchStatus.MATCH if index % 3 == 0 else CanonicalMatchStatus.INDETERMINATE
            ),
            group_evidence=(
                CanonicalGroupEvidence(
                    group_index=0,
                    group_query='("Alpha" OR "Beta")',
                    status=CanonicalMatchStatus.MATCH,
                    matched_terms=('"Alpha"',),
                    missing_fields=(),
                ),
                CanonicalGroupEvidence(
                    group_index=1,
                    group_query='"Gamma"',
                    status=CanonicalMatchStatus.INDETERMINATE,
                    matched_terms=(),
                    missing_fields=("abstract",),
                ),
                CanonicalGroupEvidence(
                    group_index=2,
                    group_query='"Delta"',
                    status=CanonicalMatchStatus.INDETERMINATE,
                    matched_terms=(),
                    missing_fields=("abstract",),
                ),
            ),
            retention_outcome=RetentionOutcome.RETAINED,
        )
        for index in range(5000)
    ]
    started = time.perf_counter()
    payload = [diagnostic.model_dump(mode="json") for diagnostic in diagnostics]
    serialized = json.dumps(payload)
    elapsed = time.perf_counter() - started
    size_bytes = len(serialized.encode("utf-8"))

    db_path = tmp_path / "scale.db"
    checkpoint_repo = SqliteSearchRunCheckpointRepository(db_path)
    now = datetime.now(timezone.utc)
    checkpoint = SearchRunCheckpoint(
        search_run_id=uuid4(),
        project_id="wp21-scale",
        job_id=uuid4(),
        provider="crossref",
        cursor="*",
        pages_fetched=250,
        fetched_count=5000,
        canonical_accepted_count=1000,
        canonical_rejected_count=1000,
        canonical_indeterminate_count=3000,
        deduplicated_count=0,
        status="partial",
        resumable=True,
        plan_metadata={"record_diagnostics": payload},
        warnings=(),
        created_at=now,
        updated_at=now,
    )
    save_started = time.perf_counter()
    checkpoint_repo.save_checkpoint(checkpoint)
    save_elapsed = time.perf_counter() - save_started

    print(
        f"\nWP2.1 scaling: diagnostics=5000 serialized_bytes={size_bytes} "
        f"dump_encode_s={elapsed:.3f} checkpoint_save_s={save_elapsed:.3f}"
    )
    assert size_bytes < 10 * 1024 * 1024
    restored = checkpoint_repo.get_checkpoints_for_job(checkpoint.job_id)
    assert len(restored) == 1
    assert len(restored[0].plan_metadata.get("record_diagnostics", [])) == 5000
