from datetime import datetime, timezone
from uuid import UUID

import pytest

from app.domain.provenance import ProvenanceEntry
from app.domain.publication import Publication
from app.repositories.search_result_snapshot_repository import (
    DuplicateSearchResultSnapshotError,
    SearchResultSnapshot,
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
