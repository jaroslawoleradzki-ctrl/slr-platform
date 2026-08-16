"""Migration 0026 tests: Fresh database and Existing DB upgrade for Task 10.7 snapshots."""

import sqlite3
from pathlib import Path
from uuid import uuid4


def _apply_migrations_up_to(db_path: Path, max_version: str | None = None) -> None:
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


def test_migration_0026_fresh_database(tmp_path: Path):
    """Verifies that all migrations 0001-0026 execute cleanly on a fresh database."""
    db_path = tmp_path / "fresh_snapshots.db"
    _apply_migrations_up_to(db_path, "0026_synthesis_snapshots.sql")

    conn = sqlite3.connect(db_path)
    try:
        c1 = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='synthesis_snapshots';"
        )
        assert c1.fetchone() is not None

        idx = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_synthesis_snapshots_proj';"
        )
        assert idx.fetchone() is not None

        fk_check = conn.execute("PRAGMA foreign_key_check;").fetchall()
        assert fk_check == []

        integrity_check = conn.execute("PRAGMA integrity_check;").fetchone()
        assert integrity_check == ("ok",)
    finally:
        conn.close()


def test_migration_0026_existing_db_upgrade(tmp_path: Path):
    """Verifies that upgrading an existing 0025 DB preserves prior Phase 10 data."""
    db_path = tmp_path / "upgrade_snapshots.db"

    _apply_migrations_up_to(db_path, "0025_research_gap_synthesis.sql")

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")

    proj_id = "test-proj-snapshot-upgrade"
    rel_id = str(uuid4())
    group_item_id = str(uuid4())
    pub_id = str(uuid4())
    rev_id = str(uuid4())
    conn.execute(
        "INSERT INTO projects (project_id, title, description) VALUES (?, ?, ?);",
        (proj_id, "Snapshot Upgrade Project", "Desc"),
    )
    conn.execute(
        "INSERT INTO synthesis_analytical_relations ("
        "relation_id, project_id, publication_id, latest_revision_id, group_item_id, "
        "item_index, source_practice, source_effect, direction, evidence_character, approval_state"
        ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);",
        (
            rel_id,
            proj_id,
            pub_id,
            rev_id,
            group_item_id,
            1,
            "5S Visual Controls",
            "Power reduction",
            "positive",
            "empirical",
            "approved",
        ),
    )
    gap_id = str(uuid4())
    conn.execute(
        "INSERT INTO synthesis_research_gaps ("
        "project_id, gap_id, gap_type, title, rationale, researcher_id"
        ") VALUES (?, ?, ?, ?, ?, ?);",
        (
            proj_id,
            gap_id,
            "thematic",
            "Under-studied practice",
            "Only one eligible source covers 5S visual controls for power reduction.",
            "researcher-1",
        ),
    )
    conn.commit()
    conn.close()

    _apply_migrations_up_to(db_path, "0026_synthesis_snapshots.sql")

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")

    read_rel = conn.execute(
        "SELECT source_practice, magnitude FROM synthesis_analytical_relations WHERE relation_id = ?;",
        (rel_id,),
    ).fetchone()
    assert read_rel == ("5S Visual Controls", None)

    read_gap = conn.execute(
        "SELECT gap_type, title FROM synthesis_research_gaps WHERE gap_id = ?;",
        (gap_id,),
    ).fetchone()
    assert read_gap == ("thematic", "Under-studied practice")

    snapshot_id = str(uuid4())
    conn.execute(
        "INSERT INTO synthesis_snapshots ("
        "snapshot_id, project_id, version, actor, extraction_dataset_hash, "
        "classification_version, content_hash, content_json"
        ") VALUES (?, ?, ?, ?, ?, ?, ?, ?);",
        (
            snapshot_id,
            proj_id,
            1,
            "researcher-1",
            "a" * 64,
            "b" * 64,
            "c" * 64,
            '{"project_id": "' + proj_id + '"}',
        ),
    )
    conn.commit()

    read_snap = conn.execute(
        "SELECT version, actor, extraction_dataset_hash FROM synthesis_snapshots WHERE snapshot_id = ?;",
        (snapshot_id,),
    ).fetchone()
    assert read_snap == (1, "researcher-1", "a" * 64)

    fk_check = conn.execute("PRAGMA foreign_key_check;").fetchall()
    assert fk_check == []
    integrity_check = conn.execute("PRAGMA integrity_check;").fetchone()
    assert integrity_check == ("ok",)

    conn.close()


def test_migration_0026_project_delete_cascades_snapshots(tmp_path: Path):
    """Verifies project hard-delete cascades to synthesis snapshots."""
    db_path = tmp_path / "cascade_snapshots.db"
    _apply_migrations_up_to(db_path, "0026_synthesis_snapshots.sql")

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    proj_id = "test-proj-snapshot-cascade"
    snapshot_id = str(uuid4())
    conn.execute(
        "INSERT INTO projects (project_id, title, description) VALUES (?, ?, ?);",
        (proj_id, "Cascade", "Desc"),
    )
    conn.execute(
        "INSERT INTO synthesis_snapshots ("
        "snapshot_id, project_id, version, actor, extraction_dataset_hash, "
        "classification_version, content_hash, content_json"
        ") VALUES (?, ?, ?, ?, ?, ?, ?, ?);",
        (
            snapshot_id,
            proj_id,
            1,
            "researcher-1",
            "a" * 64,
            "b" * 64,
            "c" * 64,
            '{"project_id": "' + proj_id + '"}',
        ),
    )
    conn.commit()
    conn.close()

    _apply_migrations_up_to(db_path, "0026_synthesis_snapshots.sql")

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("DELETE FROM projects WHERE project_id = ?;", (proj_id,))
    conn.commit()

    remaining = conn.execute(
        "SELECT COUNT(*) FROM synthesis_snapshots WHERE project_id = ?;",
        (proj_id,),
    ).fetchone()
    assert remaining == (0,)
    fk_check = conn.execute("PRAGMA foreign_key_check;").fetchall()
    assert fk_check == []
    integrity_check = conn.execute("PRAGMA integrity_check;").fetchone()
    assert integrity_check == ("ok",)
    conn.close()
