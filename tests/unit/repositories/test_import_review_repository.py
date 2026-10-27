from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

import pytest

from app.domain.import_review import ImportReviewDecision
from app.repositories.import_review_repository import (
    ImportReviewConflictError,
    SqliteImportReviewRepository,
)

PROJECT_ID = "review-project"
IMPORT_ID = UUID("11111111-1111-1111-1111-111111111111")
OTHER_PROJECT = "other-project"
OTHER_IMPORT_ID = UUID("22222222-2222-2222-2222-222222222222")


def _decision(
    *,
    decision: str = "accepted",
    project_id: str = PROJECT_ID,
    import_id: UUID = IMPORT_ID,
    rationale: str | None = None,
) -> ImportReviewDecision:
    return ImportReviewDecision(
        project_id=project_id,
        import_id=import_id,
        decision=decision,
        reviewer_id="reviewer-a",
        rationale=rationale,
        decided_at=datetime(2026, 10, 27, 12, 0, tzinfo=timezone.utc),
        import_status_at_decision="warning",
        warning_snapshot=("Skipped 2 exact DOI duplicate record(s).",),
        affected_source_record_ids=("source-1",),
        affected_publication_ids=("pub-1",),
        removed_publication_snapshots=({"record_id": "pub-1"},),
        deleted_publication_count=1,
        retained_source_record_count=2,
        prisma_treatment="removed_before_screening_rejected_import",
    )


def test_repository_round_trips_accepted_decision(tmp_path: Path) -> None:
    repository = SqliteImportReviewRepository(tmp_path / "review.db")
    created = repository.create(_decision(rationale="Looks correct"))

    loaded = repository.get(PROJECT_ID, IMPORT_ID)

    assert loaded == created
    assert loaded is not None
    assert loaded.decision == "accepted"
    assert loaded.warning_snapshot == ("Skipped 2 exact DOI duplicate record(s).",)
    assert loaded.affected_publication_ids == ("pub-1",)
    assert loaded.removed_publication_snapshots == ({"record_id": "pub-1"},)
    assert loaded.rationale == "Looks correct"


def test_repository_lists_by_project_and_rejected_ids(tmp_path: Path) -> None:
    repository = SqliteImportReviewRepository(tmp_path / "review.db")
    repository.create(_decision())
    repository.create(_decision(decision="rejected", project_id=OTHER_PROJECT, import_id=OTHER_IMPORT_ID))

    project_items = repository.list_for_project(PROJECT_ID)
    rejected_ids = repository.list_rejected_import_ids(PROJECT_ID)

    assert set(project_items) == {IMPORT_ID}
    assert project_items[IMPORT_ID].decision == "accepted"
    assert rejected_ids == set()
    assert repository.list_rejected_import_ids(OTHER_PROJECT) == {OTHER_IMPORT_ID}


def test_repository_rejects_a_second_conflicting_decision(tmp_path: Path) -> None:
    repository = SqliteImportReviewRepository(tmp_path / "review.db")
    repository.create(_decision())

    with pytest.raises(ImportReviewConflictError):
        repository.create(_decision(decision="rejected"))


def test_repository_is_project_isolated(tmp_path: Path) -> None:
    repository = SqliteImportReviewRepository(tmp_path / "review.db")
    repository.create(_decision())
    assert repository.get(OTHER_PROJECT, IMPORT_ID) is None
    assert repository.get(PROJECT_ID, OTHER_IMPORT_ID) is None


def test_migration_is_additive_and_schema_is_healthy(tmp_path: Path) -> None:
    database = tmp_path / "review.db"
    repository = SqliteImportReviewRepository(database)
    repository.create(_decision())

    import sqlite3

    with sqlite3.connect(database) as connection:
        versions = {row[0] for row in connection.execute("SELECT version FROM schema_migrations")}
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        foreign_keys = connection.execute("PRAGMA foreign_key_check").fetchall()
        columns = {row[1] for row in connection.execute("PRAGMA table_info(import_review_decisions)")}

    assert "0038_import_review_decisions.sql" in versions
    assert integrity == "ok"
    assert foreign_keys == []
    assert {
        "decision_id",
        "project_id",
        "import_id",
        "decision",
        "reviewer_id",
        "warning_snapshot_json",
        "affected_publication_ids_json",
        "removed_publication_snapshots_json",
        "prisma_treatment",
    } <= columns
