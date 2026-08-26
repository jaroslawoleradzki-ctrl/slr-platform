from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast
from uuid import UUID, uuid4

import pytest

from app.api.dto.search_strategy import (
    SearchStrategyExecutionRequest,
)
from app.domain.author import Author
from app.domain.identifiers import Identifier, IdentifierType
from app.domain.provenance import ProvenanceEntry
from app.domain.publication import DocumentType, Publication
from app.domain.search import (
    SearchQuery,
    SearchRun,
)
from app.providers.search.base import ProviderSearchOutput
from app.repositories.search_result_snapshot_repository import (
    SqliteSearchResultSnapshotRepository,
)
from app.repositories.search_run_checkpoint_repository import (
    SearchRunCheckpoint,
    SqliteSearchRunCheckpointRepository,
)
from app.services.fetch_all_search import (
    FetchAllSearchService,
)


def _build_test_strategy(providers: list[str] | None = None) -> SearchStrategyExecutionRequest:
    return SearchStrategyExecutionRequest(
        publication_year_from=2015,
        publication_year_to=2026,
        providers=cast(Any, providers or ["openalex"]),
        concept_groups=[
            {"id": "g1", "name": "Lean", "terms": ["Lean"]},
            {"id": "g2", "name": "Energy", "terms": ["Energy"]},
            {"id": "g3", "name": "Manufacturing", "terms": ["Manufacturing"]},
        ],
    )



def _make_publication(
    provider: str,
    source_id: str,
    title: str,
    abstract: str | None = "Lean energy in manufacturing.",
    doi: str | None = None,
    run_id: UUID | None = None,
) -> Publication:
    return Publication(
        title=title,
        abstract=abstract,
        authors=[Author(display_name="Ada Author")],
        publication_year=2024,
        document_type=DocumentType.JOURNAL_ARTICLE,
        provenance=[
            ProvenanceEntry(
                source=provider,
                source_record_id=source_id,
                run_id=run_id or uuid4(),
                retrieved_at=datetime.now(timezone.utc),
            )
        ],
        identifiers=[Identifier(type=IdentifierType.DOI, value=doi)] if doi else [],
    )



class MockPaginatingProvider:
    def __init__(
        self,
        name: str,
        pages: dict[str | None, tuple[list[Publication], str | None]],
        fail_on_cursor: str | None = None,
    ) -> None:
        self.name = name
        self.pages = pages
        self.fail_on_cursor = fail_on_cursor
        self.calls: list[str | None] = []

    async def search_with_raw(
        self,
        *,
        search_run: SearchRun,
        search_query: SearchQuery,
        cursor: str | None = None,
        rows: int = 20,
    ) -> ProviderSearchOutput:
        self.calls.append(cursor)
        if self.fail_on_cursor is not None and cursor == self.fail_on_cursor:
            raise RuntimeError(f"Simulated network failure on cursor {cursor}")

        pubs, next_cur = self.pages.get(cursor, ([], None))
        mapped_pubs = []
        for p in pubs:
            mapped_pubs.append(
                p.model_copy(
                    update={
                        "provenance": [
                            p.provenance[0].model_copy(
                                update={
                                    "run_id": search_run.run_id,
                                    "query_id": search_query.query_id,
                                }
                            )
                        ]
                    }
                )
            )
        return ProviderSearchOutput(
            publications=mapped_pubs,
            raw_responses=[],
            next_cursor=next_cur,
            total_count=100,
        )



@pytest.mark.anyio
async def test_wp4_openalex_resume_starts_from_saved_cursor(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    snapshot_repo = SqliteSearchResultSnapshotRepository(db_path)
    checkpoint_repo = SqliteSearchRunCheckpointRepository(db_path)

    # 3 pages for OpenAlex: page 1 (cursor "*") -> page 2 ("cursor_page_2") -> page 3 ("cursor_page_3") -> end
    pub1 = _make_publication("openalex", "W1", "Lean Energy in Manufacturing 1")
    pub2 = _make_publication("openalex", "W2", "Lean Energy in Manufacturing 2")
    pub3 = _make_publication("openalex", "W3", "Lean Energy in Manufacturing 3")

    pages = {
        "*": ([pub1], "cursor_page_2"),
        "cursor_page_2": ([pub2], "cursor_page_3"),
        "cursor_page_3": ([pub3], None),
    }

    mock_provider = MockPaginatingProvider("openalex", pages)
    # Stop after 1 page by max_pages_per_provider=1
    service = FetchAllSearchService(
        provider_factory=lambda strategy, client: [mock_provider],
        snapshot_repository=snapshot_repo,
        checkpoint_repository=checkpoint_repo,
        max_pages_per_provider=1,
    )

    strategy = _build_test_strategy(["openalex"])
    start_resp = service.start("proj_resume", strategy)
    job = await service.wait(start_resp.job_id)

    assert job.status == "completed"  # fetch-all completed with partial provider
    status = service.get_status(start_resp.job_id)
    assert status.providers[0].status == "partial"
    assert status.providers[0].resumable is True
    assert status.resumable is True
    assert status.providers[0].fetched_count == 1
    assert job.result is not None
    assert len(job.result.results) == 1
    assert [r.source_id for r in job.result.results] == ["W1"]

    # Checkpoint exists in SQLite DB
    checkpoints = checkpoint_repo.get_checkpoints_for_job(UUID(start_resp.job_id))
    assert len(checkpoints) == 1
    assert checkpoints[0].cursor == "cursor_page_2"
    assert checkpoints[0].resumable is True

    # Now resume!
    mock_provider.calls.clear()
    service_resume = FetchAllSearchService(
        provider_factory=lambda strategy, client: [mock_provider],
        snapshot_repository=snapshot_repo,
        checkpoint_repository=checkpoint_repo,
        max_pages_per_provider=10,
    )
    resume_resp = service_resume.start_resume_job("proj_resume", start_resp.job_id)
    resume_job = await service_resume.wait(resume_resp.job_id)

    assert resume_job.status == "completed"
    resume_status = service_resume.get_status(resume_resp.job_id)
    assert resume_status.providers[0].status == "complete"
    assert resume_status.providers[0].fetched_count == 3
    assert resume_status.providers[0].pages_fetched == 3
    # Provider was called with "cursor_page_2" first, then "cursor_page_3", NOT "*"
    assert mock_provider.calls == ["cursor_page_2", "cursor_page_3"]
    # Final result MUST contain all 3 publications from both sessions!
    assert resume_job.result is not None
    assert len(resume_job.result.results) == 3
    assert [r.source_id for r in resume_job.result.results] == ["W1", "W2", "W3"]


@pytest.mark.anyio
async def test_wp4_crossref_multi_query_resume_does_not_repeat_completed_queries(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    snapshot_repo = SqliteSearchResultSnapshotRepository(db_path)
    checkpoint_repo = SqliteSearchRunCheckpointRepository(db_path)

    # Crossref candidate cursor format: "crossref-plan:..."
    from app.providers.search.crossref import CrossrefProvider
    cursor_q1_p2 = CrossrefProvider._encode_candidate_cursor(1, "cursor_q1_page2")
    cursor_q2_done = CrossrefProvider._encode_candidate_cursor(2, "*")

    pub1 = _make_publication("crossref", "10.1000/1", "Lean Energy in Manufacturing 1", doi="10.1000/1")
    pub2 = _make_publication("crossref", "10.1000/2", "Lean Energy in Manufacturing 2", doi="10.1000/2")
    pub3 = _make_publication("crossref", "10.1000/3", "Lean Energy in Manufacturing 3", doi="10.1000/3")

    pages = {
        "*": ([pub1], cursor_q1_p2),
        cursor_q1_p2: ([pub2], cursor_q2_done),
        cursor_q2_done: ([pub3], None),
    }

    mock_provider = MockPaginatingProvider("crossref", pages)
    # Stop after 1 page
    service = FetchAllSearchService(
        provider_factory=lambda strategy, client: [mock_provider],
        snapshot_repository=snapshot_repo,
        checkpoint_repository=checkpoint_repo,
        max_pages_per_provider=1,
    )

    strategy = _build_test_strategy(["crossref"])
    start_resp = service.start("proj_crossref_resume", strategy)
    await service.wait(start_resp.job_id)

    # Resume from checkpoint
    mock_provider.calls.clear()
    service_resume = FetchAllSearchService(
        provider_factory=lambda strategy, client: [mock_provider],
        snapshot_repository=snapshot_repo,
        checkpoint_repository=checkpoint_repo,
        max_pages_per_provider=10,
    )
    resume_resp = service_resume.start_resume_job("proj_crossref_resume")
    resume_job = await service_resume.wait(resume_resp.job_id)

    assert resume_job.status == "completed"
    resume_status = service_resume.get_status(resume_resp.job_id)
    assert resume_status.providers[0].status == "complete"
    assert resume_status.providers[0].fetched_count == 3
    # First call was directly with cursor_q1_p2, query 0 was NOT restarted!
    assert mock_provider.calls == [cursor_q1_p2, cursor_q2_done]
    assert resume_job.result is not None
    assert len(resume_job.result.results) == 3
    assert [r.source_id for r in resume_job.result.results] == ["10.1000/1", "10.1000/2", "10.1000/3"]


@pytest.mark.anyio
async def test_wp4_semantic_scholar_continuation_token_resume(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    snapshot_repo = SqliteSearchResultSnapshotRepository(db_path)
    checkpoint_repo = SqliteSearchRunCheckpointRepository(db_path)

    pub1 = _make_publication("semantic_scholar", "S1", "Lean Energy in Manufacturing 1")
    pub2 = _make_publication("semantic_scholar", "S2", "Lean Energy in Manufacturing 2")

    pages = {
        "*": ([pub1], "s2_token_chunk2"),
        "s2_token_chunk2": ([pub2], None),
    }

    mock_provider = MockPaginatingProvider("semantic_scholar", pages)
    service = FetchAllSearchService(
        provider_factory=lambda strategy, client: [mock_provider],
        snapshot_repository=snapshot_repo,
        checkpoint_repository=checkpoint_repo,
        max_pages_per_provider=1,
    )

    strategy = _build_test_strategy(["semantic_scholar"])
    start_resp = service.start("proj_s2_resume", strategy)
    await service.wait(start_resp.job_id)

    # Resume
    mock_provider.calls.clear()
    service_resume = FetchAllSearchService(
        provider_factory=lambda strategy, client: [mock_provider],
        snapshot_repository=snapshot_repo,
        checkpoint_repository=checkpoint_repo,
        max_pages_per_provider=5,
    )
    resume_resp = service_resume.start_resume_job("proj_s2_resume")
    resume_job = await service_resume.wait(resume_resp.job_id)

    assert resume_job.status == "completed"
    assert mock_provider.calls == ["s2_token_chunk2"]
    assert resume_job.result is not None
    assert len(resume_job.result.results) == 2
    assert [r.source_id for r in resume_job.result.results] == ["S1", "S2"]


@pytest.mark.anyio
async def test_wp4_cancellation_saves_checkpoint_and_enables_resume(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    snapshot_repo = SqliteSearchResultSnapshotRepository(db_path)
    checkpoint_repo = SqliteSearchRunCheckpointRepository(db_path)

    pub1 = _make_publication("openalex", "W1", "Lean Energy in Manufacturing 1")
    pub2 = _make_publication("openalex", "W2", "Lean Energy in Manufacturing 2")

    pages = {
        "*": ([pub1], "cursor_cancel_2"),
        "cursor_cancel_2": ([pub2], None),
    }

    class CancellingProvider(MockPaginatingProvider):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, **kwargs)
            self.service: FetchAllSearchService | None = None
            self.job_id: str | None = None

        async def search_with_raw(self, *args: Any, **kwargs: Any) -> ProviderSearchOutput:
            out = await super().search_with_raw(*args, **kwargs)
            if self.service is not None and self.job_id is not None:
                self.service.request_cancel(self.job_id)
            return out

    mock_provider = CancellingProvider("openalex", pages)
    service = FetchAllSearchService(
        provider_factory=lambda strategy, client: [mock_provider],
        snapshot_repository=snapshot_repo,
        checkpoint_repository=checkpoint_repo,
        max_pages_per_provider=5,
    )
    mock_provider.service = service

    strategy = _build_test_strategy(["openalex"])
    start_resp = service.start("proj_cancel", strategy)
    mock_provider.job_id = start_resp.job_id
    await service.wait(start_resp.job_id)

    status = service.get_status(start_resp.job_id)
    assert status.status == "cancelled"
    assert status.resumable is True
    assert status.providers[0].fetched_count == 1

    # Resume after cancellation
    resume_mock_provider = MockPaginatingProvider("openalex", pages)
    service_resume = FetchAllSearchService(
        provider_factory=lambda strategy, client: [resume_mock_provider],
        snapshot_repository=snapshot_repo,
        checkpoint_repository=checkpoint_repo,
        max_pages_per_provider=5,
    )
    resume_resp = service_resume.start_resume_job("proj_cancel")
    resume_job = await service_resume.wait(resume_resp.job_id)

    assert resume_job.status == "completed"
    assert resume_mock_provider.calls == ["cursor_cancel_2"]
    assert resume_job.result is not None
    assert len(resume_job.result.results) == 2
    assert [r.source_id for r in resume_job.result.results] == ["W1", "W2"]


@pytest.mark.anyio
async def test_wp4_provider_failure_preserves_checkpoint_for_resume(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    snapshot_repo = SqliteSearchResultSnapshotRepository(db_path)
    checkpoint_repo = SqliteSearchRunCheckpointRepository(db_path)

    pub1 = _make_publication("openalex", "W1", "Lean Energy in Manufacturing 1")
    pub2 = _make_publication("openalex", "W2", "Lean Energy in Manufacturing 2")

    pages = {
        "*": ([pub1], "cursor_fail_2"),
        "cursor_fail_2": ([pub2], None),
    }

    # Fails when trying to fetch cursor_fail_2
    mock_provider = MockPaginatingProvider("openalex", pages, fail_on_cursor="cursor_fail_2")
    service = FetchAllSearchService(
        provider_factory=lambda strategy, client: [mock_provider],
        snapshot_repository=snapshot_repo,
        checkpoint_repository=checkpoint_repo,
        max_pages_per_provider=5,
    )

    strategy = _build_test_strategy(["openalex"])
    start_resp = service.start("proj_fail", strategy)
    await service.wait(start_resp.job_id)

    status = service.get_status(start_resp.job_id)
    assert status.providers[0].status == "partial"
    assert status.providers[0].resumable is True

    # Now fix failure and resume!
    mock_provider.fail_on_cursor = None
    mock_provider.calls.clear()
    service_resume = FetchAllSearchService(
        provider_factory=lambda strategy, client: [mock_provider],
        snapshot_repository=snapshot_repo,
        checkpoint_repository=checkpoint_repo,
        max_pages_per_provider=5,
    )
    resume_resp = service_resume.start_resume_job("proj_fail")
    resume_job = await service_resume.wait(resume_resp.job_id)

    resume_status = service_resume.get_status(resume_resp.job_id)
    assert resume_status.providers[0].status == "complete"
    assert mock_provider.calls == ["cursor_fail_2"]
    assert resume_job.result is not None
    assert len(resume_job.result.results) == 2
    assert [r.source_id for r in resume_job.result.results] == ["W1", "W2"]


@pytest.mark.anyio
async def test_wp4_idempotency_on_checkpoint_boundary(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    snapshot_repo = SqliteSearchResultSnapshotRepository(db_path)
    checkpoint_repo = SqliteSearchRunCheckpointRepository(db_path)

    # Overlapping publication on boundary
    pub1 = _make_publication("openalex", "W1", "Lean Energy in Manufacturing 1", doi="10.1000/shared")
    pub1_repeat = _make_publication("openalex", "W1", "Lean Energy in Manufacturing 1", doi="10.1000/shared")
    pub2 = _make_publication("openalex", "W2", "Lean Energy in Manufacturing 2", doi="10.1000/unique2")

    pages = {
        "*": ([pub1], "cursor_idempotent_2"),
        "cursor_idempotent_2": ([pub1_repeat, pub2], None),
    }

    mock_provider = MockPaginatingProvider("openalex", pages)
    service = FetchAllSearchService(
        provider_factory=lambda strategy, client: [mock_provider],
        snapshot_repository=snapshot_repo,
        checkpoint_repository=checkpoint_repo,
        max_pages_per_provider=1,
    )

    strategy = _build_test_strategy(["openalex"])
    start_resp = service.start("proj_idempotent", strategy)
    await service.wait(start_resp.job_id)

    # Resume with overlap
    service_resume = FetchAllSearchService(
        provider_factory=lambda strategy, client: [mock_provider],
        snapshot_repository=snapshot_repo,
        checkpoint_repository=checkpoint_repo,
        max_pages_per_provider=5,
    )
    resume_resp = service_resume.start_resume_job("proj_idempotent")
    resume_job = await service_resume.wait(resume_resp.job_id)

    assert resume_job.result is not None
    # No duplicate result records in final response!
    assert len(resume_job.result.results) == 2
    assert [r.source_id for r in resume_job.result.results] == ["W1", "W2"]


@pytest.mark.anyio
async def test_wp4_backend_restart_simulation(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    snapshot_repo = SqliteSearchResultSnapshotRepository(db_path)
    checkpoint_repo = SqliteSearchRunCheckpointRepository(db_path)

    pub1 = _make_publication("openalex", "W1", "Lean Energy in Manufacturing 1")
    pub2 = _make_publication("openalex", "W2", "Lean Energy in Manufacturing 2")

    pages = {
        "*": ([pub1], "cursor_restart_2"),
        "cursor_restart_2": ([pub2], None),
    }

    mock_provider = MockPaginatingProvider("openalex", pages)
    service1 = FetchAllSearchService(
        provider_factory=lambda strategy, client: [mock_provider],
        snapshot_repository=snapshot_repo,
        checkpoint_repository=checkpoint_repo,
        max_pages_per_provider=1,
    )

    strategy = _build_test_strategy(["openalex"])
    start_resp = service1.start("proj_restart", strategy)
    await service1.wait(start_resp.job_id)

    # Simulate backend crash/restart: create completely new service instance with no in-memory state
    fresh_snapshot_repo = SqliteSearchResultSnapshotRepository(db_path)
    fresh_checkpoint_repo = SqliteSearchRunCheckpointRepository(db_path)
    service2 = FetchAllSearchService(
        provider_factory=lambda strategy, client: [mock_provider],
        snapshot_repository=fresh_snapshot_repo,
        checkpoint_repository=fresh_checkpoint_repo,
        max_pages_per_provider=10,
    )

    # Durable get_status reads from DB
    durable_status = service2.get_status(start_resp.job_id)
    assert durable_status.resumable is True
    assert durable_status.providers[0].status == "partial"

    # Resume from project without passing job_id (picks latest checkpoint from DB)
    mock_provider.calls.clear()
    resume_resp = service2.start_resume_job("proj_restart")
    resume_job = await service2.wait(resume_resp.job_id)

    assert resume_job.status == "completed"
    assert mock_provider.calls == ["cursor_restart_2"]
    assert resume_job.result is not None
    assert len(resume_job.result.results) == 2
    assert [r.source_id for r in resume_job.result.results] == ["W1", "W2"]


@pytest.mark.anyio
async def test_wp4_multi_step_resume_across_three_sessions(tmp_path: Path) -> None:
    """Requirement B: session 1 -> cp, session 2 -> cp, session 3 -> complete."""
    db_path = tmp_path / "multi_resume.db"
    snapshot_repo = SqliteSearchResultSnapshotRepository(db_path)
    checkpoint_repo = SqliteSearchRunCheckpointRepository(db_path)

    pub1 = _make_publication("openalex", "W1", "Lean Energy in Manufacturing 1")
    pub2 = _make_publication("openalex", "W2", "Lean Energy in Manufacturing 2")
    pub3 = _make_publication("openalex", "W3", "Lean Energy in Manufacturing 3")

    pages = {
        "*": ([pub1], "cursor_step_2"),
        "cursor_step_2": ([pub2], "cursor_step_3"),
        "cursor_step_3": ([pub3], None),
    }

    mock_provider = MockPaginatingProvider("openalex", pages)

    # Session 1: fetch 1 page
    svc1 = FetchAllSearchService(
        provider_factory=lambda s, c: [mock_provider],
        snapshot_repository=snapshot_repo,
        checkpoint_repository=checkpoint_repo,
        max_pages_per_provider=1,
    )
    s1 = svc1.start("proj_multi_step", _build_test_strategy(["openalex"]))
    j1 = await svc1.wait(s1.job_id)
    assert j1.status == "completed"
    assert svc1.get_status(s1.job_id).providers[0].status == "partial"
    assert j1.result is not None
    assert len(j1.result.results) == 1
    assert [r.source_id for r in j1.result.results] == ["W1"]

    # Session 2: resume with max_pages_per_provider=2 (fetches page 2, still partial)
    mock_provider.calls.clear()
    svc2 = FetchAllSearchService(
        provider_factory=lambda s, c: [mock_provider],
        snapshot_repository=snapshot_repo,
        checkpoint_repository=checkpoint_repo,
        max_pages_per_provider=2,
    )
    s2 = svc2.start_resume_job("proj_multi_step", s1.job_id)
    j2 = await svc2.wait(s2.job_id)
    assert j2.status == "completed"
    assert svc2.get_status(s2.job_id).providers[0].status == "partial"
    assert mock_provider.calls == ["cursor_step_2"]
    assert j2.result is not None
    assert len(j2.result.results) == 2
    assert [r.source_id for r in j2.result.results] == ["W1", "W2"]

    # Session 3: resume with max_pages_per_provider=10 (fetches page 3, completes)
    mock_provider.calls.clear()
    svc3 = FetchAllSearchService(
        provider_factory=lambda s, c: [mock_provider],
        snapshot_repository=snapshot_repo,
        checkpoint_repository=checkpoint_repo,
        max_pages_per_provider=10,
    )
    s3 = svc3.start_resume_job("proj_multi_step", s2.job_id)
    j3 = await svc3.wait(s3.job_id)
    assert j3.status == "completed"
    assert svc3.get_status(s3.job_id).providers[0].status == "complete"
    assert mock_provider.calls == ["cursor_step_3"]
    assert j3.result is not None
    assert len(j3.result.results) == 3
    assert [r.source_id for r in j3.result.results] == ["W1", "W2", "W3"]
    assert j3.result.returned_count == 3
    assert j3.result.retrieved_count == 3
    assert j3.result.canonical_accepted_count == 3


@pytest.mark.anyio
async def test_wp4_multi_provider_resume_with_completed_and_resumed_providers(tmp_path: Path) -> None:
    """Multi-provider resume: provider A is complete in session 1, provider B resumes in session 2."""
    db_path = tmp_path / "multi_provider.db"
    snapshot_repo = SqliteSearchResultSnapshotRepository(db_path)
    checkpoint_repo = SqliteSearchRunCheckpointRepository(db_path)

    pub_a1 = _make_publication("openalex", "A1", "Lean Energy in Manufacturing A1")
    pub_a2 = _make_publication("openalex", "A2", "Lean Energy in Manufacturing A2")
    pub_b1 = _make_publication("semantic_scholar", "B1", "Lean Energy in Manufacturing B1")
    pub_b2 = _make_publication("semantic_scholar", "B2", "Lean Energy in Manufacturing B2")

    pages_a = {"*": ([pub_a1, pub_a2], None)}  # OpenAlex completes in 1 page
    pages_b = {"*": ([pub_b1], "s2_page_2"), "s2_page_2": ([pub_b2], None)}  # S2 has 2 pages

    mock_a = MockPaginatingProvider("openalex", pages_a)
    mock_b = MockPaginatingProvider("semantic_scholar", pages_b)

    # Session 1: max_pages_per_provider=1 -> OpenAlex completes, Semantic Scholar is partial
    svc1 = FetchAllSearchService(
        provider_factory=lambda s, c: [mock_a, mock_b],
        snapshot_repository=snapshot_repo,
        checkpoint_repository=checkpoint_repo,
        max_pages_per_provider=1,
    )
    s1 = svc1.start("proj_multi_prov", _build_test_strategy(["openalex", "semantic_scholar"]))
    j1 = await svc1.wait(s1.job_id)
    assert j1.status == "completed"
    st1 = svc1.get_status(s1.job_id)
    assert st1.providers[0].status == "complete"
    assert st1.providers[1].status == "partial"
    assert j1.result is not None
    assert len(j1.result.results) == 3
    assert {r.source_id for r in j1.result.results} == {"A1", "A2", "B1"}

    # Session 2: resume -> OpenAlex skipped, Semantic Scholar finishes page 2
    mock_a.calls.clear()
    mock_b.calls.clear()
    svc2 = FetchAllSearchService(
        provider_factory=lambda s, c: [mock_a, mock_b],
        snapshot_repository=snapshot_repo,
        checkpoint_repository=checkpoint_repo,
        max_pages_per_provider=10,
    )
    s2 = svc2.start_resume_job("proj_multi_prov", s1.job_id)
    j2 = await svc2.wait(s2.job_id)
    assert j2.status == "completed"
    st2 = svc2.get_status(s2.job_id)
    assert st2.providers[0].status == "complete"
    assert st2.providers[1].status == "complete"
    assert mock_a.calls == []  # OpenAlex was not called
    assert mock_b.calls == ["s2_page_2"]

    # Final result MUST contain all 4 records from both providers across both sessions
    assert j2.result is not None
    assert len(j2.result.results) == 4
    assert {r.source_id for r in j2.result.results} == {"A1", "A2", "B1", "B2"}


@pytest.mark.anyio
async def test_wp4_resume_rejects_cross_project_job_id(tmp_path: Path) -> None:
    """Requirement D: Checkpoint from project A + attempt resume in project B must be rejected."""
    db_path = tmp_path / "cross_project.db"
    snapshot_repo = SqliteSearchResultSnapshotRepository(db_path)
    checkpoint_repo = SqliteSearchRunCheckpointRepository(db_path)

    pub1 = _make_publication("openalex", "W1", "Lean Energy in Manufacturing 1")
    mock_provider = MockPaginatingProvider("openalex", {"*": ([pub1], "cursor_p2")})

    svc = FetchAllSearchService(
        provider_factory=lambda s, c: [mock_provider],
        snapshot_repository=snapshot_repo,
        checkpoint_repository=checkpoint_repo,
        max_pages_per_provider=1,
    )

    # Start and stop job for project_A
    start_resp_a = svc.start("project_A", _build_test_strategy(["openalex"]))
    await svc.wait(start_resp_a.job_id)

    # Attempt to resume job_a_id under project_B
    with pytest.raises(ValueError, match="does not belong to project 'project_B'"):
        svc.start_resume_job("project_B", job_id=start_resp_a.job_id)


@pytest.mark.anyio
async def test_wp4_duplicate_snapshot_error_handled_specifically(tmp_path: Path) -> None:
    """Requirement E: DuplicateSearchResultSnapshotError is specifically caught without masking errors."""
    db_path = tmp_path / "duplicate_snapshot.db"
    snapshot_repo = SqliteSearchResultSnapshotRepository(db_path)
    checkpoint_repo = SqliteSearchRunCheckpointRepository(db_path)

    pub1 = _make_publication("openalex", "W1", "Lean Energy in Manufacturing 1")
    pages = {
        "*": ([pub1], "cursor_page_2"),
        "cursor_page_2": ([pub1], None),  # Same publication returned again
    }

    mock_provider = MockPaginatingProvider("openalex", pages)
    svc1 = FetchAllSearchService(
        provider_factory=lambda s, c: [mock_provider],
        snapshot_repository=snapshot_repo,
        checkpoint_repository=checkpoint_repo,
        max_pages_per_provider=1,
    )
    s1 = svc1.start("proj_dup", _build_test_strategy(["openalex"]))
    await svc1.wait(s1.job_id)

    # Resume: pub1 already has a snapshot in SQLite from run 1
    svc2 = FetchAllSearchService(
        provider_factory=lambda s, c: [mock_provider],
        snapshot_repository=snapshot_repo,
        checkpoint_repository=checkpoint_repo,
        max_pages_per_provider=5,
    )
    s2 = svc2.start_resume_job("proj_dup", s1.job_id)
    j2 = await svc2.wait(s2.job_id)
    assert j2.status == "completed"
    assert j2.result is not None
    assert len(j2.result.results) == 1
    assert j2.result.results[0].source_id == "W1"


@pytest.mark.anyio
async def test_wp4_missing_strategy_metadata_raises_controlled_error(tmp_path: Path) -> None:
    """Requirement F: Missing/corrupt strategy metadata raises controlled ValueError without ValidationError."""
    db_path = tmp_path / "missing_strategy.db"
    checkpoint_repo = SqliteSearchRunCheckpointRepository(db_path)

    # Save a checkpoint with no strategy metadata
    run_id = uuid4()
    job_id = uuid4()
    cp = SearchRunCheckpoint(
        search_run_id=run_id,
        project_id="proj_no_strat",
        job_id=job_id,
        provider="openalex",
        cursor="cursor_page_2",
        pages_fetched=1,
        fetched_count=1,
        canonical_accepted_count=1,
        canonical_rejected_count=0,
        canonical_indeterminate_count=0,
        deduplicated_count=0,
        status="partial",
        resumable=True,
        plan_metadata=None,  # No strategy metadata
        warnings=(),
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    checkpoint_repo.save_checkpoint(cp)

    svc = FetchAllSearchService(
        checkpoint_repository=checkpoint_repo,
    )

    with pytest.raises(ValueError, match="search strategy metadata is missing"):
        svc.start_resume_job("proj_no_strat", job_id=job_id)
