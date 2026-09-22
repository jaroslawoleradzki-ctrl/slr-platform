from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast
from uuid import UUID, uuid4

import httpx
import pytest

from app.api.dto.search_strategy import SearchStrategyExecutionRequest
from app.domain.identifiers import IdentifierType
from app.domain.search import BooleanOperator, SearchGroup, SearchQuery, SearchRun, SearchTerm
from app.providers.crossref import CrossrefClient
from app.providers.search.crossref import CrossrefProvider, IncompatibleCrossrefPlanError
from app.rendering.crossref import (
    CrossrefQueryRenderer,
    build_crossref_candidate_plan,
    build_crossref_candidate_queries,
    compute_plan_fingerprint,
)
from app.repositories.search_result_snapshot_repository import SqliteSearchResultSnapshotRepository
from app.repositories.search_run_checkpoint_repository import (
    SearchRunCheckpoint,
    SqliteSearchRunCheckpointRepository,
)
from app.services.fetch_all_search import FetchAllSearchService
from app.services.live_search import build_search_query


class RecordingClient:
    def __init__(self) -> None:
        self.requests: list[tuple[str, str | None]] = []

    async def search_works(self, query: str, *, rows: int, cursor: str | None, filters: Any) -> dict[str, Any]:
        self.requests.append((query, cursor))
        return {"message": {"total-results": 0, "items": [], "next-cursor": None}}


def _axis(*values: str) -> SearchGroup:
    return SearchGroup(operator=BooleanOperator.OR, children=[SearchTerm(value=value) for value in values])


# ==============================================================================
# Sol Adversarial Planner Sweep & Normalization (Finding 2 / Requirement 7)
# ==============================================================================


def test_duplicate_text_is_normalized_before_axis_counting() -> None:
    """Duplicate synonyms on an OR branch are deduplicated before axis representation calculation."""
    expression = SearchGroup(
        operator=BooleanOperator.AND,
        children=[_axis("alpha", "alpha", "beta"), _axis("one", "two", "three")],
    )
    plan = build_crossref_candidate_plan(expression)
    assert plan.axis_coverage[0]["available_alternatives"] == 2
    assert plan.axis_coverage[0]["represented_alternatives"] == 2


@pytest.mark.parametrize(
    "shape",
    [
        (3, 3),
        (3,) * 9,
        (7, 6, 4),
        (10, 2),
        (2, 10),
        (7, 7),
        (2,) * 14,
        (3,) * 10,
        (7, 2, 2),
        (2, 7, 2),
        (2, 2, 7),
    ],
)
def test_adversarial_shapes_respect_executable_contract(shape: tuple[int, ...]) -> None:
    """Adversarial shapes respect bounded queries, distinct order, and min(6, Lj) alternative coverage."""
    expression = SearchGroup(
        operator=BooleanOperator.AND,
        children=[_axis(*(f"axis{axis}_value{value}" for value in range(length))) for axis, length in enumerate(shape)],
    )
    first = build_crossref_candidate_plan(expression)
    second = build_crossref_candidate_plan(expression)
    assert first == second
    assert 0 < len(first.queries) <= 6
    assert len(first.queries) == len(set(first.queries))
    assert [part["represented_alternatives"] for part in first.axis_coverage] == [min(6, length) for length in shape]


# ==============================================================================
# Regression F: Canonical Injective Fingerprint Serialization (Blocker 2)
# ==============================================================================


def test_regression_f_fingerprint_must_not_confuse_distinct_query_lists() -> None:
    """Regression F: Ambiguous plans ['a\\nb', 'c'] and ['a', 'b\\nc'] must produce different fingerprints."""
    fp1 = compute_plan_fingerprint(["a\nb", "c"])
    fp2 = compute_plan_fingerprint(["a", "b\nc"])
    assert fp1 != fp2


# ==============================================================================
# Regression A: Legacy two-element cursor + missing candidate queries (Blocker 1)
# ==============================================================================


@pytest.mark.anyio
async def test_regression_a_legacy_cursor_missing_candidate_queries_raises() -> None:
    """Regression A: Legacy two-element cursor without saved candidate queries refuses before HTTP."""
    query = SearchQuery(name="review", expression=_axis("old", "new"))
    rendered = CrossrefQueryRenderer().render(query)
    run = SearchRun(query_id=query.query_id, query_version=1, provider="crossref", rendered_query=rendered.query_string)
    client = RecordingClient()
    provider = CrossrefProvider(client=cast(Any, client))
    old_cursor = CrossrefProvider._encode_candidate_cursor(1, "old-page")

    with pytest.raises(IncompatibleCrossrefPlanError):
        await provider.search_with_raw(search_run=run, search_query=query, cursor=old_cursor)

    assert len(client.requests) == 0


# ==============================================================================
# Regression B: Legacy cursor + malformed candidate queries (Blocker 1)
# ==============================================================================


@pytest.mark.anyio
@pytest.mark.parametrize("malformed", [[], [123], ["valid", ""], ["valid", "   "], ["valid", None]])
async def test_regression_b_legacy_cursor_malformed_candidate_queries_raises(malformed: Any) -> None:
    """Regression B: Legacy cursor with malformed candidate queries refuses before HTTP."""
    query = SearchQuery(name="review", expression=_axis("old", "new"))
    rendered = CrossrefQueryRenderer().render(query)
    run = SearchRun(query_id=query.query_id, query_version=1, provider="crossref", rendered_query=rendered.query_string)
    client = RecordingClient()
    provider = CrossrefProvider(client=cast(Any, client))
    old_cursor = CrossrefProvider._encode_candidate_cursor(1, "old-page")

    with pytest.raises(IncompatibleCrossrefPlanError):
        await provider.search_with_raw(search_run=run, search_query=query, cursor=old_cursor, candidate_queries=malformed)

    assert len(client.requests) == 0


# ==============================================================================
# Regression C: Unpinned single-query physical cursor (Blocker 1)
# ==============================================================================


@pytest.mark.anyio
async def test_regression_c_unpinned_single_query_physical_cursor_raises() -> None:
    """Regression C: Unpinned single-query physical cursor refuses before HTTP unless exact query identity is proven."""
    query = SearchQuery(name="review", expression=SearchTerm(value="new query"))
    rendered = CrossrefQueryRenderer().render(query)
    run = SearchRun(query_id=query.query_id, query_version=1, provider="crossref", rendered_query=rendered.query_string)
    client = RecordingClient()
    provider = CrossrefProvider(client=cast(Any, client))

    with pytest.raises(IncompatibleCrossrefPlanError):
        await provider.search_with_raw(search_run=run, search_query=query, cursor="old-query-page")

    assert len(client.requests) == 0


# ==============================================================================
# Regression D: Valid old saved candidate queries + legacy cursor resumes exact saved query
# ==============================================================================


@pytest.mark.anyio
async def test_regression_d_valid_saved_candidate_queries_resumes_exact_query() -> None:
    """Regression D: Valid saved candidate queries with legacy cursor issues exact physical query at saved index."""
    query = SearchQuery(name="review", expression=_axis("changed_a", "changed_b"))
    run = SearchRun(query_id=query.query_id, query_version=1, provider="crossref", rendered_query="unused")
    client = RecordingClient()
    provider = CrossrefProvider(client=cast(Any, client))
    saved_queries = ["legacy query zero", "legacy query one", "legacy query two"]
    cursor = CrossrefProvider._encode_candidate_cursor(1, "page-token-abc")

    await provider.search_with_raw(
        search_run=run, search_query=query, cursor=cursor, candidate_queries=saved_queries
    )

    assert len(client.requests) == 1
    assert client.requests[0] == ("legacy query one", "page-token-abc")


# ==============================================================================
# Regression E: Versioned cursor + fingerprint mismatch refuses before HTTP
# ==============================================================================


@pytest.mark.anyio
async def test_regression_e_versioned_cursor_fingerprint_mismatch_raises() -> None:
    """Regression E: Versioned cursor whose fingerprint does not match candidate queries refuses before HTTP."""
    query = SearchQuery(name="review", expression=SearchTerm(value="alpha"))
    run = SearchRun(query_id=query.query_id, query_version=1, provider="crossref", rendered_query="unused")
    client = RecordingClient()
    provider = CrossrefProvider(client=cast(Any, client))
    plan = ["query alpha", "query beta"]
    cursor = CrossrefProvider._encode_candidate_cursor(0, "page-token", plan_fingerprint="mismatched_fp_99")

    with pytest.raises(IncompatibleCrossrefPlanError, match="does not match active plan fingerprint"):
        await provider.search_with_raw(search_run=run, search_query=query, cursor=cursor, candidate_queries=plan)

    assert len(client.requests) == 0


# ==============================================================================
# Regression G: Cursor from first plan applied to second refuses before HTTP
# ==============================================================================


@pytest.mark.anyio
async def test_regression_g_cursor_from_first_plan_applied_to_second_raises() -> None:
    """Regression G: Cursor created for first plan applied to second plan refuses before HTTP."""
    query = SearchQuery(name="review", expression=SearchTerm(value="alpha"))
    run = SearchRun(query_id=query.query_id, query_version=1, provider="crossref", rendered_query="unused")
    client = RecordingClient()
    provider = CrossrefProvider(client=cast(Any, client))
    old_plan = ["a\nb", "c"]
    new_plan = ["a", "b\nc"]
    cursor = CrossrefProvider._encode_candidate_cursor(1, "old-page", compute_plan_fingerprint(old_plan))

    with pytest.raises(IncompatibleCrossrefPlanError):
        await provider.search_with_raw(search_run=run, search_query=query, cursor=cursor, candidate_queries=new_plan)

    assert len(client.requests) == 0


# ==============================================================================
# Regression H: Literal query delimiter ' || ' must remain ONE physical query (Major 3)
# ==============================================================================


@pytest.mark.anyio
async def test_regression_h_delimiter_inside_single_query_is_sent_intact() -> None:
    """Regression H: Literal ' || ' inside a query string is not split and is sent intact to Crossref."""
    query = SearchQuery(name="review", expression=SearchTerm(value="alpha || beta"))
    rendered = CrossrefQueryRenderer().render(query)
    run = SearchRun(query_id=query.query_id, query_version=1, provider="crossref", rendered_query=rendered.query_string)
    client = RecordingClient()
    provider = CrossrefProvider(client=cast(Any, client))

    await provider.search_with_raw(search_run=run, search_query=query)

    assert len(client.requests) == 1
    assert client.requests[0] == (rendered.metadata["candidate_queries"][0], "*")
    assert client.requests[0][0] == '"alpha || beta"'


# ==============================================================================
# Regression I: Cursor index outside candidate queries refuses before HTTP
# ==============================================================================


@pytest.mark.anyio
@pytest.mark.parametrize("bad_index", [2, 5, 99])
async def test_regression_i_cursor_index_outside_candidate_queries_raises(bad_index: int) -> None:
    """Regression I: Cursor query index outside candidate queries raises explicit incompatibility before HTTP."""
    query = SearchQuery(name="review", expression=SearchTerm(value="alpha"))
    run = SearchRun(query_id=query.query_id, query_version=1, provider="crossref", rendered_query="unused")
    client = RecordingClient()
    provider = CrossrefProvider(client=cast(Any, client))
    plan = ["single query"]
    cursor = CrossrefProvider._encode_candidate_cursor(bad_index, "page-token", compute_plan_fingerprint(plan))

    with pytest.raises(IncompatibleCrossrefPlanError, match="out of bounds"):
        await provider.search_with_raw(search_run=run, search_query=query, cursor=cursor, candidate_queries=plan)

    assert len(client.requests) == 0


# ==============================================================================
# Regression J: Malformed plan metadata + in-flight cursor in FetchAllSearchService
# ==============================================================================


@pytest.mark.anyio
@pytest.mark.parametrize(
    "bad_plan_fields",
    [
        {"candidate_queries": None},
        {"candidate_queries": []},
        {"candidate_queries": [123]},
        {"candidate_queries": ["valid", ""]},
        {"candidate_queries": ["valid"], "plan_fingerprint": ""},
        {"candidate_queries": ["valid"], "planner_version": ""},
    ],
)
async def test_regression_j_malformed_plan_metadata_with_inflight_cursor_raises(tmp_path: Path, bad_plan_fields: Any) -> None:
    """Regression J: Malformed plan metadata with in-flight cursor marks job failed with zero HTTP requests."""
    db_path = tmp_path / f"malformed-{uuid4().hex[:8]}.db"
    snapshot_repo = SqliteSearchResultSnapshotRepository(db_path)
    checkpoint_repo = SqliteSearchRunCheckpointRepository(db_path)
    requests_issued: list[tuple[str, str]] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests_issued.append((str(request.url), ""))
        return httpx.Response(200, json={"message": {"items": []}}, request=request)

    strategy = SearchStrategyExecutionRequest(
        publication_year_from=2015,
        publication_year_to=2026,
        providers=["crossref"],
        concept_groups=[
            {"id": "g1", "name": "Lean", "terms": ["Lean"]},
            {"id": "g2", "name": "Energy", "terms": ["Energy"]},
        ],
    )
    job_id = uuid4()
    search_run_id = uuid4()
    cursor = CrossrefProvider._encode_candidate_cursor(1, "legacy-page-2")

    plan_metadata = {"strategy": strategy.model_dump(mode="json"), **bad_plan_fields}
    checkpoint = SearchRunCheckpoint(
        search_run_id=search_run_id,
        project_id="bad-meta-proj",
        job_id=job_id,
        provider="crossref",
        cursor=cursor,
        pages_fetched=1,
        fetched_count=1,
        canonical_accepted_count=1,
        canonical_rejected_count=0,
        canonical_indeterminate_count=0,
        deduplicated_count=0,
        status="partial",
        resumable=True,
        plan_metadata=plan_metadata,
        warnings=(),
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    checkpoint_repo.save_checkpoint(checkpoint)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        service = FetchAllSearchService(
            provider_factory=lambda s, c: [CrossrefProvider(client=CrossrefClient(http_client=http_client), paginate=True)],
            snapshot_repository=snapshot_repo,
            checkpoint_repository=checkpoint_repo,
        )
        started = service.start_resume_job("bad-meta-proj", job_id)
        await service.wait(started.job_id)

        assert len(requests_issued) == 0
        status = service.get_status(started.job_id)
        cr_state = status.providers[0]
        assert cr_state.status == "failed"
        assert cr_state.resumable is False
        assert "IncompatibleCrossrefPlanError" in (cr_state.message or "")


@pytest.mark.anyio
@pytest.mark.parametrize("missing_or_corrupt", [None, "corrupt string"])
async def test_regression_j_missing_or_non_dict_plan_metadata_with_inflight_cursor_refuses_before_http(
    tmp_path: Path, missing_or_corrupt: Any
) -> None:
    """Regression J (corrupt/missing plan_metadata): Refuses before any HTTP request."""
    db_path = tmp_path / f"corrupt-{uuid4().hex[:8]}.db"
    snapshot_repo = SqliteSearchResultSnapshotRepository(db_path)
    checkpoint_repo = SqliteSearchRunCheckpointRepository(db_path)
    requests_issued: list[tuple[str, str]] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests_issued.append((str(request.url), ""))
        return httpx.Response(200, json={"message": {"items": []}}, request=request)

    job_id = uuid4()
    search_run_id = uuid4()
    cursor = CrossrefProvider._encode_candidate_cursor(1, "legacy-page-2")

    checkpoint = SearchRunCheckpoint(
        search_run_id=search_run_id,
        project_id="corrupt-meta-proj",
        job_id=job_id,
        provider="crossref",
        cursor=cursor,
        pages_fetched=1,
        fetched_count=1,
        canonical_accepted_count=1,
        canonical_rejected_count=0,
        canonical_indeterminate_count=0,
        deduplicated_count=0,
        status="partial",
        resumable=True,
        plan_metadata=missing_or_corrupt,
        warnings=(),
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    checkpoint_repo.save_checkpoint(checkpoint)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        service = FetchAllSearchService(
            provider_factory=lambda s, c: [CrossrefProvider(client=CrossrefClient(http_client=http_client), paginate=True)],
            snapshot_repository=snapshot_repo,
            checkpoint_repository=checkpoint_repo,
        )
        with pytest.raises(ValueError):
            service.start_resume_job("corrupt-meta-proj", job_id)

        assert len(requests_issued) == 0


# ==============================================================================
# Requirement 8: Integration Scenarios Owned by WP3
# ==============================================================================


@pytest.mark.anyio
async def test_integration_7x6x4_plan_exact_physical_requests_and_provenance() -> None:
    """Requirement 8.1: 7x6x4 balanced plan verified end-to-end:

    - Generates 6 distinct physical queries covering min(6, Lj) alternatives per axis.
    - Executes exact physical queries in deterministic order.
    - Yields WP2-compatible provenance fields: query, query index, cursor, rank, score.
    """
    lean_terms = ["Lean Mgmt", "Lean Mfg", "Lean Prod", "TPS", "Kaizen", "Cont Impr", "JIT"]  # 7
    energy_terms = ["Energy Eff", "Energy Cons", "Energy Perf", "Energy Save", "Energy Mgmt", "Energy Use"]  # 6
    mfg_terms = ["Manufacturing", "Production", "Industrial", "Factory"]  # 4

    query = SearchQuery(
        name="7x6x4 Test",
        expression=SearchGroup(
            operator=BooleanOperator.AND,
            children=[_axis(*lean_terms), _axis(*energy_terms), _axis(*mfg_terms)],
        ),
    )
    plan = build_crossref_candidate_plan(query.expression)
    assert len(plan.queries) == 6
    assert len(set(plan.queries)) == 6
    assert plan.possible_combinations == 7 * 6 * 4  # 168

    # Verify min(6, Lj) representation
    assert [p["represented_alternatives"] for p in plan.axis_coverage] == [6, 6, 4]

    requests_recorded: list[dict[str, Any]] = []

    def make_response_for_query(q_str: str, cur: str) -> dict[str, Any]:
        idx = plan.queries.index(q_str)
        items = [
            {
                "DOI": f"10.1000/q{idx}-rank0",
                "title": [f"Result Q{idx} R0"],
                "type": "journal-article",
                "score": 15.5 + idx,
                "published": {"date-parts": [[2024]]},
            },
            {
                "DOI": f"10.1000/q{idx}-rank1",
                "title": [f"Result Q{idx} R1"],
                "type": "journal-article",
                "score": 12.0 + idx,
                "published": {"date-parts": [[2024]]},
            },
        ]
        return {
            "message": {
                "total-results": 2,
                "items": items,
                "next-cursor": None,
            }
        }

    async def mock_handler(request: httpx.Request) -> httpx.Response:
        q = request.url.params["query"]
        cur = request.url.params["cursor"]
        rows = int(request.url.params["rows"])
        requests_recorded.append({"query": q, "cursor": cur, "rows": rows})
        resp = make_response_for_query(q, cur)
        return httpx.Response(200, json=resp, request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(mock_handler)) as http_client:
        provider = CrossrefProvider(
            client=CrossrefClient(http_client=http_client, requests_per_second=None),
            paginate=True,
            max_results=50,
        )
        rendered = CrossrefQueryRenderer().render(query)
        run = SearchRun(
            query_id=query.query_id,
            query_version=1,
            provider="crossref",
            rendered_query=rendered.query_string,
        )
        output = await provider.search_with_raw(
            search_run=run,
            search_query=query,
            candidate_queries=rendered.metadata["candidate_queries"],
        )

    # 1. Exact physical requests in order
    assert len(requests_recorded) == 6
    assert [r["query"] for r in requests_recorded] == list(plan.queries)
    assert all(r["cursor"] == "*" for r in requests_recorded)

    # 2. Output publications and records
    assert len(output.publications) == 12
    assert output.raw_count == 12
    assert output.mapped_count == 12

    # 3. Verify WP2-compatible retrieval fields across items
    for q_idx, query_str in enumerate(plan.queries):
        raw_resp = output.raw_responses[q_idx]
        items = raw_resp["message"]["items"]
        assert len(items) == 2
        for rank, item in enumerate(items):
            # Provenance items match exact query, rank, score
            assert item["DOI"] == f"10.1000/q{q_idx}-rank{rank}"
            assert item["score"] > 0
            # Corresponding publication mapped
            pub = output.publications[q_idx * 2 + rank]
            doi_identifiers = [i.value for i in pub.identifiers if i.type == IdentifierType.DOI]
            assert doi_identifiers == [f"10.1000/q{q_idx}-rank{rank}"]
            assert pub.provenance[0].source == "crossref"


@pytest.mark.anyio
async def test_integration_balanced_six_query_resume_no_replayed_positions(tmp_path: Path) -> None:
    """Requirement 8.2: Balanced six-query resume verified end-to-end:

    - Starts a 6-query run with 2 pages per query (12 total physical pages).
    - Interrupts execution after 4 physical requests (partway through query 1).
    - Resumes with saved checkpoint containing structured plan provenance.
    - Verifies NO physical (query, cursor) position is replayed after restart.
    - All 12 requests complete exactly once across initial + resumed execution.
    """
    db_path = tmp_path / "balanced-six-resume.db"
    snapshot_repo = SqliteSearchResultSnapshotRepository(db_path)
    checkpoint_repo = SqliteSearchRunCheckpointRepository(db_path)

    strategy = SearchStrategyExecutionRequest(
        publication_year_from=2015,
        publication_year_to=2026,
        providers=["crossref"],
        concept_groups=[
            {"id": "g1", "name": "Lean", "terms": ["Lean", "Kaizen", "TPS", "Agile", "Quality", "Efficiency"]},
            {"id": "g2", "name": "Energy", "terms": ["Energy"]},
            {"id": "g3", "name": "Mfg", "terms": ["Manufacturing"]},
        ],
    )
    search_query = build_search_query(strategy)
    queries = build_crossref_candidate_queries(search_query.expression)
    assert len(queries) == 6
    query_to_idx = {q: idx for idx, q in enumerate(queries)}

    all_issued_requests: list[tuple[str, str]] = []

    def make_items(q_idx: int, page: int) -> list[dict[str, Any]]:
        return [
            {
                "DOI": f"10.1000/six-q{q_idx}-p{page}-{i}",
                "title": [f"Paper {q_idx}-{page}-{i}"],
                "type": "journal-article",
                "score": 10.0,
                "published": {"date-parts": [[2024]]},
            }
            for i in range(2)
        ]

    async def handler(request: httpx.Request) -> httpx.Response:
        q = request.url.params["query"]
        cur = request.url.params["cursor"]
        all_issued_requests.append((q, cur))
        q_idx = query_to_idx[q]
        if cur == "*":
            next_cur = f"q{q_idx}-cursor-page2"
            items = make_items(q_idx, 1)
        else:
            assert cur == f"q{q_idx}-cursor-page2"
            next_cur = None
            items = make_items(q_idx, 2)
        return httpx.Response(
            200,
            json={"message": {"total-results": 4, "items": items, "next-cursor": next_cur}},
            request=request,
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        def provider_factory(strat: SearchStrategyExecutionRequest, client: httpx.AsyncClient) -> list[CrossrefProvider]:
            return [
                CrossrefProvider(
                    client=CrossrefClient(http_client=http_client, requests_per_second=None),
                    paginate=True,
                    max_physical_requests_per_call=1,
                )
            ]

        # Phase 1: Run with max_pages=4 (stops after 4 requests: Q0 p1, Q0 p2, Q1 p1, Q1 p2)
        svc1 = FetchAllSearchService(
            provider_factory=provider_factory,
            snapshot_repository=snapshot_repo,
            checkpoint_repository=checkpoint_repo,
            max_pages_per_provider=4,
        )
        started1 = svc1.start("six-query-proj", strategy)
        job1 = await svc1.wait(started1.job_id)

        assert job1.status == "completed"  # fetch-all job completed phase
        phase1_requests = list(all_issued_requests)
        assert len(phase1_requests) == 4
        assert phase1_requests == [
            (queries[0], "*"),
            (queries[0], "q0-cursor-page2"),
            (queries[1], "*"),
            (queries[1], "q1-cursor-page2"),
        ]

        # Verify durable checkpoint is resumable and points to Q2 p1
        cps = checkpoint_repo.get_checkpoints_for_job(UUID(started1.job_id))
        assert len(cps) == 1
        cp = cps[0]
        assert cp.resumable is True
        q_idx, phys_cur, fp = CrossrefProvider._decode_candidate_cursor_payload(cp.cursor)
        assert q_idx == 2
        assert phys_cur == "*"
        assert fp == compute_plan_fingerprint(queries)

        # Phase 2: Resume with max_pages=50 (finishes all remaining queries Q2..Q5)
        svc2 = FetchAllSearchService(
            provider_factory=provider_factory,
            snapshot_repository=snapshot_repo,
            checkpoint_repository=checkpoint_repo,
            max_pages_per_provider=50,
        )
        started2 = svc2.start_resume_job("six-query-proj", started1.job_id)
        job2 = await svc2.wait(started2.job_id)

        assert job2.status == "completed"
        phase2_requests = all_issued_requests[len(phase1_requests):]

        # Crucial invariant: ZERO physical position replayed after restart!
        assert not set(phase1_requests).intersection(phase2_requests)

        # Total 12 distinct physical requests
        assert len(all_issued_requests) == 12
        assert len(set(all_issued_requests)) == 12

        # Resumed execution begins at query 2
        assert phase2_requests[0] == (queries[2], "*")
        assert phase2_requests[-1] == (queries[5], "q5-cursor-page2")
