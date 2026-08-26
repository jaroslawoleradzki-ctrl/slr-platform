"""Dedicated test suite for WP5 — Search Audit & Reproducibility Hardening."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast
from uuid import UUID, uuid4

import pytest

from app.api.dto.search_strategy import SearchStrategyExecutionRequest
from app.domain.author import Author
from app.domain.identifiers import Identifier, IdentifierType
from app.domain.provenance import ProvenanceEntry
from app.domain.publication import DocumentType, Publication
from app.domain.search import (
    SearchQuery,
    SearchRun,
)
from app.providers.search.base import ProviderSearchOutput
from app.providers.search.crossref import CrossrefProvider
from app.repositories.search_result_snapshot_repository import (
    SqliteSearchResultSnapshotRepository,
)
from app.repositories.search_run_checkpoint_repository import (
    SqliteSearchRunCheckpointRepository,
)
from app.services.fetch_all_search import FetchAllSearchService


def _strategy(providers: list[str] | None = None) -> SearchStrategyExecutionRequest:
    return SearchStrategyExecutionRequest(
        publication_year_from=2015,
        publication_year_to=2026,
        providers=cast(Any, providers or ["openalex"]),
        concept_groups=[
            {"id": "g1", "name": "Lean", "terms": ["Lean Management", "Lean Manufacturing"]},
            {"id": "g2", "name": "Energy", "terms": ["Energy Efficiency", "Energy Consumption"]},
            {"id": "g3", "name": "Manufacturing", "terms": ["Manufacturing", "Production"]},
        ],
    )


def _publication(provider: str, source_id: str, title: str, doi: str | None = None) -> Publication:
    return Publication(
        title=title,
        abstract="Lean Management and Energy Efficiency in Manufacturing.",
        authors=[Author(display_name="Ada Author")],

        publication_year=2024,
        document_type=DocumentType.JOURNAL_ARTICLE,
        provenance=[
            ProvenanceEntry(
                source=provider,
                source_record_id=source_id,
                run_id=uuid4(),
                retrieved_at=datetime.now(timezone.utc),
            )
        ],
        identifiers=[Identifier(type=IdentifierType.DOI, value=doi)] if doi else [],
    )


class ScriptedProvider:
    def __init__(self, name: str, pages: dict[str | None, tuple[list[Publication], str | None]]) -> None:
        self.name = name
        self.pages = pages
        self.call_history: list[dict[str, Any]] = []

    async def search_with_raw(
        self,
        *,
        search_run: SearchRun,
        search_query: SearchQuery,
        cursor: str | None = None,
        rows: int = 20,
    ) -> ProviderSearchOutput:
        self.call_history.append({"cursor": cursor, "search_run_id": search_run.run_id})
        pubs, next_cur = self.pages.get(cursor, ([], None))
        mapped = [
            p.model_copy(
                update={
                    "provenance": [
                        p.provenance[0].model_copy(
                            update={"run_id": search_run.run_id, "query_id": search_query.query_id}
                        )
                    ]
                }
            )
            for p in pubs
        ]
        return ProviderSearchOutput(
            publications=mapped,
            raw_responses=[{"status": "ok", "items": len(mapped)}],
            next_cursor=next_cur,
            total_count=50,
        )


@pytest.mark.anyio
async def test_wp5_crossref_physical_query_audit_and_metadata(tmp_path: Path) -> None:
    db_path = tmp_path / "audit_test.db"
    snapshot_repo = SqliteSearchResultSnapshotRepository(db_path)
    checkpoint_repo = SqliteSearchRunCheckpointRepository(db_path)

    pub1 = _publication("crossref", "10.1/1", "Lean Management in Energy Manufacturing", doi="10.1/1")
    cursor_step2 = CrossrefProvider._encode_candidate_cursor(1, "page2")
    pages = {
        "*": ([pub1], cursor_step2),
        cursor_step2: ([], None),
    }
    provider = ScriptedProvider("crossref", pages)
    service = FetchAllSearchService(
        provider_factory=lambda strategy, client: [provider],
        snapshot_repository=snapshot_repo,
        checkpoint_repository=checkpoint_repo,
        max_pages_per_provider=1,
    )

    strat = _strategy(["crossref"])
    start_resp = service.start("proj_audit_crossref", strat)
    await service.wait(start_resp.job_id)

    # Check that checkpoint records candidate queries and current query index
    checkpoints = checkpoint_repo.get_checkpoints_for_job(UUID(start_resp.job_id))
    assert len(checkpoints) == 1
    cp = checkpoints[0]
    assert cp.provider == "crossref"
    assert cp.plan_metadata is not None
    assert "candidate_queries" in cp.plan_metadata
    assert cp.plan_metadata["candidate_queries"] == ['"Lean Management"', '"Lean Manufacturing"']
    assert cp.plan_metadata.get("current_query_index") == 1
    assert cp.plan_metadata.get("current_physical_cursor") == "page2"


@pytest.mark.anyio
async def test_wp5_pagination_sequence_traceability(tmp_path: Path) -> None:
    db_path = tmp_path / "pagination_audit.db"
    snapshot_repo = SqliteSearchResultSnapshotRepository(db_path)
    checkpoint_repo = SqliteSearchRunCheckpointRepository(db_path)

    pub1 = _publication("openalex", "W1", "Lean Energy in Manufacturing 1")
    pub2 = _publication("openalex", "W2", "Lean Energy in Manufacturing 2")
    pages = {
        "*": ([pub1], "cur_page_2"),
        "cur_page_2": ([pub2], None),
    }
    provider = ScriptedProvider("openalex", pages)
    service = FetchAllSearchService(
        provider_factory=lambda strategy, client: [provider],
        snapshot_repository=snapshot_repo,
        checkpoint_repository=checkpoint_repo,
        max_pages_per_provider=5,
    )

    strat = _strategy(["openalex"])
    start_resp = service.start("proj_page_audit", strat)
    job = await service.wait(start_resp.job_id)
    assert job.status == "completed"

    # Verify search run audit saved in DB
    with snapshot_repo._database_path.open() as _:
        import sqlite3
        with sqlite3.connect(db_path) as conn:
            rows = conn.execute("SELECT search_run_id, physical_query, retrieved_count FROM search_run_audits WHERE project_id = 'proj_page_audit'").fetchall()
            assert len(rows) == 1
            assert rows[0][2] == 2  # 2 retrieved across pagination


@pytest.mark.anyio
async def test_wp5_resume_audit_continuity(tmp_path: Path) -> None:
    db_path = tmp_path / "resume_audit.db"
    snapshot_repo = SqliteSearchResultSnapshotRepository(db_path)
    checkpoint_repo = SqliteSearchRunCheckpointRepository(db_path)

    pub1 = _publication("openalex", "W1", "Lean Energy in Manufacturing 1")
    pub2 = _publication("openalex", "W2", "Lean Energy in Manufacturing 2")
    pages = {
        "*": ([pub1], "cur_midway"),
        "cur_midway": ([pub2], None),
    }
    provider = ScriptedProvider("openalex", pages)
    service = FetchAllSearchService(
        provider_factory=lambda strategy, client: [provider],
        snapshot_repository=snapshot_repo,
        checkpoint_repository=checkpoint_repo,
        max_pages_per_provider=1,  # stop after 1 page
    )

    strat = _strategy(["openalex"])
    start1 = service.start("proj_resume_audit", strat)
    await service.wait(start1.job_id)

    # Resume
    service_resume = FetchAllSearchService(
        provider_factory=lambda strategy, client: [provider],
        snapshot_repository=snapshot_repo,
        checkpoint_repository=checkpoint_repo,
        max_pages_per_provider=5,
    )
    start2 = service_resume.start_resume_job("proj_resume_audit", start1.job_id)
    await service_resume.wait(start2.job_id)

    # Check resumed checkpoint contains resumed_from_job_id
    resumed_cps = checkpoint_repo.get_checkpoints_for_job(UUID(start2.job_id))
    assert len(resumed_cps) == 1
    assert resumed_cps[0].plan_metadata is not None
    assert resumed_cps[0].plan_metadata.get("resumed_from_job_id") == start1.job_id

    # Check audit record contains execution resume note
    import sqlite3
    with sqlite3.connect(db_path) as conn:
        row = conn.execute("SELECT translation_warnings FROM search_run_audits WHERE project_id = 'proj_resume_audit'").fetchone()
        assert row is not None
        warnings = json.loads(row[0])
        assert any(start1.job_id in w for w in warnings)


@pytest.mark.anyio
async def test_wp5_retry_and_failure_status_in_audit_checkpoints(tmp_path: Path) -> None:
    db_path = tmp_path / "failure_audit.db"
    snapshot_repo = SqliteSearchResultSnapshotRepository(db_path)
    checkpoint_repo = SqliteSearchRunCheckpointRepository(db_path)

    class FailingProvider(ScriptedProvider):
        async def search_with_raw(self, *args: Any, **kwargs: Any) -> ProviderSearchOutput:
            raise ConnectionError("Simulated network timeout during provider call")

    provider = FailingProvider("openalex", {})
    service = FetchAllSearchService(
        provider_factory=lambda strategy, client: [provider],
        snapshot_repository=snapshot_repo,
        checkpoint_repository=checkpoint_repo,
    )

    strat = _strategy(["openalex"])
    start = service.start("proj_failure_audit", strat)
    await service.wait(start.job_id)

    # Check that failed status and error message are persisted in checkpoint
    cps = checkpoint_repo.get_checkpoints_for_job(UUID(start.job_id))
    assert len(cps) == 1
    assert cps[0].status == "failed"
    assert cps[0].resumable is True


@pytest.mark.anyio
async def test_wp5_complete_run_audit_reconstruction(tmp_path: Path) -> None:
    db_path = tmp_path / "complete_audit.db"
    snapshot_repo = SqliteSearchResultSnapshotRepository(db_path)
    checkpoint_repo = SqliteSearchRunCheckpointRepository(db_path)

    pub1 = _publication("openalex", "W1", "Lean Management and Energy Efficiency in Manufacturing 1", doi="10.1000/1")
    pub2 = _publication("openalex", "W2", "Lean Management and Energy Efficiency in Manufacturing 2", doi="10.1000/2")
    pages = {"*": ([pub1, pub2], None)}
    provider = ScriptedProvider("openalex", pages)
    service = FetchAllSearchService(
        provider_factory=lambda strategy, client: [provider],
        snapshot_repository=snapshot_repo,
        checkpoint_repository=checkpoint_repo,
    )

    strat = _strategy(["openalex"])
    start = service.start("proj_full_reconstruct", strat)
    await service.wait(start.job_id)

    # Reconstruct run from audit row
    import sqlite3
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            """SELECT search_run_id, canonical_hash, provider, physical_endpoint,
                      physical_query, retrieved_count, canonical_accepted_count
               FROM search_run_audits
               WHERE project_id = 'proj_full_reconstruct'"""
        ).fetchone()
        assert row is not None
        assert row[1] is not None
        assert row[2] == "openalex"
        assert row[3] == "https://api.openalex.org/works"
        assert '("Lean Management" OR "Lean Manufacturing")' in row[4]
        assert row[5] == 2
        assert row[6] == 2


@pytest.mark.anyio
async def test_wp5_project_deletion_cleans_all_audits_and_checkpoints(tmp_path: Path) -> None:
    db_path = tmp_path / "deletion_audit.db"
    snapshot_repo = SqliteSearchResultSnapshotRepository(db_path)
    checkpoint_repo = SqliteSearchRunCheckpointRepository(db_path)

    pub1 = _publication("openalex", "W1", "Lean Management and Energy Efficiency in Manufacturing 1", doi="10.1000/1")
    pages = {"*": ([pub1], None)}
    provider = ScriptedProvider("openalex", pages)
    service = FetchAllSearchService(
        provider_factory=lambda strategy, client: [provider],
        snapshot_repository=snapshot_repo,
        checkpoint_repository=checkpoint_repo,
    )

    strat = _strategy(["openalex"])
    start = service.start("proj_to_delete", strat)
    await service.wait(start.job_id)

    # Verify rows exist before deletion
    import sqlite3
    with sqlite3.connect(db_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM search_result_snapshots WHERE project_id = 'proj_to_delete'").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM search_run_audits WHERE project_id = 'proj_to_delete'").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM search_run_checkpoints WHERE project_id = 'proj_to_delete'").fetchone()[0] == 1

    # Delete project
    snapshot_repo.delete_for_project("proj_to_delete")

    # Verify all cleaned up with no orphaned rows
    with sqlite3.connect(db_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM search_result_snapshots WHERE project_id = 'proj_to_delete'").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM search_run_audits WHERE project_id = 'proj_to_delete'").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM search_run_checkpoints WHERE project_id = 'proj_to_delete'").fetchone()[0] == 0


@pytest.mark.anyio
async def test_wp5_crossref_mass_indeterminate_generates_warning_and_preserves_recall(tmp_path: Path) -> None:
    db_path = tmp_path / "crossref_mass_indet.db"
    snapshot_repo = SqliteSearchResultSnapshotRepository(db_path)
    checkpoint_repo = SqliteSearchRunCheckpointRepository(db_path)

    # 100 mock Crossref publications with 0% abstracts, only partial title match (cannot satisfy all 3 canonical blocks)
    pubs = [
        Publication(
            title=f"Lean Management Study #{i}",
            abstract=None,
            authors=[Author(display_name=f"Author {i}")],
            publication_year=2024,
            document_type=DocumentType.JOURNAL_ARTICLE,
            provenance=[
                ProvenanceEntry(
                    source="crossref",
                    source_record_id=f"10.1000/cr_{i}",
                    run_id=uuid4(),
                    retrieved_at=datetime.now(timezone.utc),
                )
            ],
            identifiers=[],
        )
        for i in range(100)
    ]

    pages = {"*": (pubs, None)}
    provider = ScriptedProvider("crossref", pages)
    service = FetchAllSearchService(
        provider_factory=lambda strategy, client: [provider],
        snapshot_repository=snapshot_repo,
        checkpoint_repository=checkpoint_repo,
        max_records_per_provider=200,
    )

    strat = _strategy(["crossref"])
    start_resp = service.start("proj_mass_indet", strat)
    job = await service.wait(start_resp.job_id)

    assert job.status == "completed"
    assert len(job.providers) == 1
    state = job.providers[0]

    # Verify that indeterminate count >= 90 (all 100 in this case)
    assert state.fetched_count == 100
    assert state.canonical_indeterminate_count >= 90
    assert state.canonical_accepted_count == 0
    # Recall preserved (indeterminate records kept)
    assert state.kept_count == 100

    # High indeterminate rate warning generated
    assert any("High indeterminate rate: over 50%" in w for w in state.warnings)
