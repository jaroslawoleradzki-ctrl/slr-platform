import json
import sqlite3
from datetime import datetime, timezone
from uuid import UUID

import pytest

from app.domain.provenance import ProvenanceEntry
from app.domain.publication import Publication
from app.repositories.search_result_snapshot_repository import (
    DuplicateSearchResultSnapshotError,
    SearchResultSnapshot,
    SearchRunAudit,
    SqliteSearchResultSnapshotRepository,
)


def test_duplicate_publication_in_same_search_run_is_controlled_error(tmp_path) -> None:
    run_id = UUID("00000000-0000-0000-0000-000000000010")
    publication = Publication(
        record_id=UUID("00000000-0000-0000-0000-000000000020"),
        title="Result",
        provenance=[ProvenanceEntry(source="openalex", source_record_id="W1", run_id=run_id)],
    )
    repository = SqliteSearchResultSnapshotRepository(tmp_path / "snapshots.db")
    first = SearchResultSnapshot.create(
        project_id="lean_energy", search_run_id=run_id, provider="openalex", source_id="W1", publication=publication
    )
    second = SearchResultSnapshot.create(
        project_id="lean_energy", search_run_id=run_id, provider="openalex", source_id="W1", publication=publication
    )

    repository.save(first)
    with pytest.raises(DuplicateSearchResultSnapshotError):
        repository.save(second)


def test_same_source_in_different_runs_creates_distinct_durable_snapshots(tmp_path) -> None:
    repository = SqliteSearchResultSnapshotRepository(tmp_path / "snapshots.db")
    snapshots = []
    for suffix in (1, 2):
        run_id = UUID(f"00000000-0000-0000-0000-{suffix:012d}")
        publication = Publication(
            title="Result",
            provenance=[
                ProvenanceEntry(
                    source="openalex",
                    source_record_id="W1",
                    run_id=run_id,
                    retrieved_at=datetime(2026, 8, suffix, tzinfo=timezone.utc),
                )
            ],
        )
        snapshots.append(
            repository.save(
                SearchResultSnapshot.create(
                    project_id="lean_energy",
                    search_run_id=run_id,
                    provider="openalex",
                    source_id="W1",
                    publication=publication,
                )
            )
        )

    reopened = SqliteSearchResultSnapshotRepository(tmp_path / "snapshots.db")
    assert snapshots[0].snapshot_id != snapshots[1].snapshot_id
    assert (
        reopened.get("lean_energy", snapshots[0].snapshot_id).search_run_id
        != reopened.get("lean_energy", snapshots[1].snapshot_id).search_run_id
    )


def test_search_run_audit_persists_canonical_translation_and_counts(tmp_path) -> None:
    database = tmp_path / "audits.db"
    repository = SqliteSearchResultSnapshotRepository(database)
    run_id = UUID("00000000-0000-0000-0000-000000000010")
    query_id = UUID("00000000-0000-0000-0000-000000000020")
    repository.save_audit(
        SearchRunAudit(
            search_run_id=run_id,
            project_id="lean_energy",
            canonical_query_id=query_id,
            canonical_version=3,
            canonical_hash="a" * 64,
            provider="crossref",
            physical_endpoint="https://api.crossref.org/works",
            physical_query='"Lean Management" || "Kaizen"',
            translation_lossless=False,
            translation_warnings=("Candidate retrieval; validate locally.",),
            retrieved_count=100,
            canonical_accepted_count=20,
            canonical_rejected_count=80,
            canonical_indeterminate_count=3,
            deduplicated_count=5,
            started_at=datetime(2026, 8, 26, 10, tzinfo=timezone.utc),
            finished_at=datetime(2026, 8, 26, 10, 1, tzinfo=timezone.utc),
        )
    )

    with sqlite3.connect(database) as connection:
        row = connection.execute(
            """SELECT canonical_query_id, canonical_version, canonical_hash,
                      physical_endpoint, physical_query, translation_lossless,
                      translation_warnings, retrieved_count,
                      canonical_accepted_count, canonical_rejected_count,
                      canonical_indeterminate_count,
                      deduplicated_count
               FROM search_run_audits WHERE search_run_id = ?""",
            (str(run_id),),
        ).fetchone()

    assert row is not None
    assert row[:6] == (
        str(query_id),
        3,
        "a" * 64,
        "https://api.crossref.org/works",
        '"Lean Management" || "Kaizen"',
        0,
    )
    assert json.loads(row[6]) == ["Candidate retrieval; validate locally."]
    assert row[7:] == (100, 20, 80, 3, 5)


def test_delete_for_project_removes_both_snapshots_and_audits(tmp_path) -> None:
    database = tmp_path / "lifecycle.db"
    repository = SqliteSearchResultSnapshotRepository(database)
    run_id_a = UUID("00000000-0000-0000-0000-000000000010")
    run_id_b = UUID("00000000-0000-0000-0000-000000000020")
    query_id = UUID("00000000-0000-0000-0000-000000000030")

    # Project A snapshot & audit
    pub_a = Publication(
        title="Result A",
        provenance=[ProvenanceEntry(source="openalex", source_record_id="W1", run_id=run_id_a)],
    )
    repository.save(
        SearchResultSnapshot.create(
            project_id="proj_a", search_run_id=run_id_a, provider="openalex", source_id="W1", publication=pub_a
        )
    )
    repository.save_audit(
        SearchRunAudit(
            search_run_id=run_id_a,
            project_id="proj_a",
            canonical_query_id=query_id,
            canonical_version=1,
            canonical_hash="a" * 64,
            provider="openalex",
            physical_endpoint="https://api.openalex.org/works",
            physical_query="test",
            translation_lossless=True,
            translation_warnings=(),
            retrieved_count=10,
            canonical_accepted_count=10,
            canonical_rejected_count=0,
            canonical_indeterminate_count=0,
            deduplicated_count=0,
            started_at=datetime(2026, 8, 26, 10, tzinfo=timezone.utc),
            finished_at=datetime(2026, 8, 26, 10, 1, tzinfo=timezone.utc),
        )
    )

    # Project B snapshot & audit
    pub_b = Publication(
        title="Result B",
        provenance=[ProvenanceEntry(source="openalex", source_record_id="W2", run_id=run_id_b)],
    )
    repository.save(
        SearchResultSnapshot.create(
            project_id="proj_b", search_run_id=run_id_b, provider="openalex", source_id="W2", publication=pub_b
        )
    )
    repository.save_audit(
        SearchRunAudit(
            search_run_id=run_id_b,
            project_id="proj_b",
            canonical_query_id=query_id,
            canonical_version=1,
            canonical_hash="b" * 64,
            provider="openalex",
            physical_endpoint="https://api.openalex.org/works",
            physical_query="test",
            translation_lossless=True,
            translation_warnings=(),
            retrieved_count=5,
            canonical_accepted_count=5,
            canonical_rejected_count=0,
            canonical_indeterminate_count=0,
            deduplicated_count=0,
            started_at=datetime(2026, 8, 26, 10, tzinfo=timezone.utc),
            finished_at=datetime(2026, 8, 26, 10, 1, tzinfo=timezone.utc),
        )
    )

    # Delete Project A
    repository.delete_for_project("proj_a")

    with sqlite3.connect(database) as connection:
        snapshots_a = connection.execute("SELECT COUNT(*) FROM search_result_snapshots WHERE project_id = 'proj_a'").fetchone()[0]
        audits_a = connection.execute("SELECT COUNT(*) FROM search_run_audits WHERE project_id = 'proj_a'").fetchone()[0]
        snapshots_b = connection.execute("SELECT COUNT(*) FROM search_result_snapshots WHERE project_id = 'proj_b'").fetchone()[0]
        audits_b = connection.execute("SELECT COUNT(*) FROM search_run_audits WHERE project_id = 'proj_b'").fetchone()[0]

    assert snapshots_a == 0
    assert audits_a == 0
    assert snapshots_b == 1
    assert audits_b == 1
