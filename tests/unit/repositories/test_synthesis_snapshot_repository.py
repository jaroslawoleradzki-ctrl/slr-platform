"""Unit tests for SqliteSynthesisSnapshotRepository (Task 10.7)."""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest

from app.domain.synthesis import (
    SynthesisSnapshot,
    SynthesisSnapshotContent,
)
from app.repositories.synthesis_snapshot_repository import (
    SqliteSynthesisSnapshotRepository,
    default_synthesis_snapshot_repository,
)


def _apply_migrations(db_path: Path, max_version: str | None = None) -> None:
    migrations_dir = Path(__file__).parents[3] / "migrations"
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    try:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            "version TEXT PRIMARY KEY, "
            "applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP"
            ");"
        )
        applied = {row[0] for row in conn.execute("SELECT version FROM schema_migrations")}
        for sql_file in sorted(migrations_dir.glob("*.sql")):
            if max_version and sql_file.name > max_version:
                continue
            if sql_file.name not in applied:
                conn.executescript(sql_file.read_text(encoding="utf-8"))
                conn.execute("INSERT INTO schema_migrations (version) VALUES (?);", (sql_file.name,))
        conn.commit()
    finally:
        conn.close()


def _make_snapshot(project_id="proj-test", version=1, actor="researcher-1", content_project_id=None):
    return SynthesisSnapshot(
        snapshot_id=uuid4(),
        project_id=project_id,
        version=version,
        actor=actor,
        extraction_dataset_hash="a" * 64,
        classification_version="b" * 64,
        content_hash="c" * 64,
        content=SynthesisSnapshotContent(project_id=content_project_id or project_id),
        created_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def repo(tmp_path: Path):
    db_path = tmp_path / "test_snapshot_repo.db"
    _apply_migrations(db_path)
    proj_id = "test-proj-snapshot-repo"
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute(
        "INSERT INTO projects (project_id, title, description) VALUES (?, ?, ?);",
        (proj_id, "Test Project", "Desc"),
    )
    conn.commit()
    conn.close()
    return SqliteSynthesisSnapshotRepository(db_path), proj_id


def test_b1_save_and_get_snapshot_by_id(repo):
    repo, proj_id = repo
    snap = _make_snapshot(project_id=proj_id)
    repo.save_snapshot(snap)
    loaded = repo.get_snapshot(proj_id, str(snap.snapshot_id))
    assert loaded is not None
    assert loaded.snapshot_id == snap.snapshot_id
    assert loaded.project_id == proj_id
    assert loaded.version == 1
    assert loaded.actor == "researcher-1"
    assert loaded.extraction_dataset_hash == "a" * 64
    assert loaded.classification_version == "b" * 64
    assert loaded.content_hash == "c" * 64
    assert loaded.content.project_id == proj_id


def test_b2_get_snapshot_by_version(repo):
    repo, proj_id = repo
    snap = _make_snapshot(project_id=proj_id, version=3)
    repo.save_snapshot(snap)
    loaded = repo.get_snapshot_by_version(proj_id, 3)
    assert loaded is not None
    assert loaded.snapshot_id == snap.snapshot_id
    assert repo.get_snapshot_by_version(proj_id, 2) is None


def test_b3_list_snapshots_ordered_by_version_ascending(repo):
    repo, proj_id = repo
    for version in (5, 1, 3):
        repo.save_snapshot(_make_snapshot(project_id=proj_id, version=version))
    versions = [s.version for s in repo.list_snapshots(proj_id)]
    assert versions == [1, 3, 5]


def test_b4_duplicate_version_raises_integrity_error(repo):
    repo, proj_id = repo
    repo.save_snapshot(_make_snapshot(project_id=proj_id, version=1))
    with pytest.raises(sqlite3.IntegrityError):
        repo.save_snapshot(_make_snapshot(project_id=proj_id, version=1))


def test_b5_project_isolation(repo):
    repo, proj_id = repo
    repo.save_snapshot(_make_snapshot(project_id=proj_id, version=1))
    assert repo.list_snapshots("other-project") == []
    assert repo.get_snapshot("other-project", "does-not-exist") is None


def test_b6_stored_content_matches_creation_state(repo):
    repo, proj_id = repo
    content = SynthesisSnapshotContent(
        project_id=proj_id,
        qa_profiles=[],
    )
    snap = SynthesisSnapshot(
        snapshot_id=uuid4(),
        project_id=proj_id,
        version=1,
        actor="researcher-1",
        extraction_dataset_hash="a" * 64,
        classification_version="b" * 64,
        content_hash="c" * 64,
        content=content,
        created_at=datetime.now(timezone.utc),
    )
    repo.save_snapshot(snap)
    loaded = repo.get_snapshot(proj_id, str(snap.snapshot_id))
    assert loaded is not None
    assert loaded.content.model_dump() == content.model_dump()
    assert loaded.content_hash == "c" * 64


def test_b7_repo_works_against_fresh_0026_database(tmp_path: Path):
    db_path = tmp_path / "fresh.db"
    _apply_migrations(db_path, "0026_synthesis_snapshots.sql")
    proj_id = "proj-fresh-0026"
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute(
        "INSERT INTO projects (project_id, title, description) VALUES (?, ?, ?);",
        (proj_id, "Fresh", "Desc"),
    )
    conn.commit()
    conn.close()

    repo = SqliteSynthesisSnapshotRepository(db_path)
    snap = _make_snapshot(project_id=proj_id)
    repo.save_snapshot(snap)
    assert repo.get_snapshot(proj_id, str(snap.snapshot_id)) is not None


def test_b8_repo_works_after_upgrade_from_0025(tmp_path: Path):
    db_path = tmp_path / "upgrade.db"
    _apply_migrations(db_path, "0025_research_gap_synthesis.sql")
    proj_id = "proj-upgrade-0026"
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute(
        "INSERT INTO projects (project_id, title, description) VALUES (?, ?, ?);",
        (proj_id, "Upgrade", "Desc"),
    )
    conn.commit()
    conn.close()

    _apply_migrations(db_path, "0026_synthesis_snapshots.sql")

    repo = SqliteSynthesisSnapshotRepository(db_path)
    snap = _make_snapshot(project_id=proj_id)
    repo.save_snapshot(snap)
    assert repo.get_snapshot(proj_id, str(snap.snapshot_id)) is not None


def test_b9_snapshot_cannot_be_updated_in_place(repo):
    repo, proj_id = repo
    snap = _make_snapshot(project_id=proj_id, version=1)
    repo.save_snapshot(snap)
    # No update method exists; only a new version can be created.
    assert not hasattr(repo, "update_snapshot")
    # The stored content is frozen at creation.
    stored = repo.get_snapshot(proj_id, str(snap.snapshot_id))
    assert stored is not None
    assert stored.content.model_dump() == snap.content.model_dump()


def test_b10_delete_for_project_removes_snapshots(repo):
    repo, proj_id = repo
    repo.save_snapshot(_make_snapshot(project_id=proj_id, version=1))
    repo.save_snapshot(_make_snapshot(project_id=proj_id, version=2))
    repo.delete_for_project(proj_id)
    assert repo.list_snapshots(proj_id) == []


def test_b10_default_repository_singleton():
    assert default_synthesis_snapshot_repository().__class__.__name__ == "SqliteSynthesisSnapshotRepository"
