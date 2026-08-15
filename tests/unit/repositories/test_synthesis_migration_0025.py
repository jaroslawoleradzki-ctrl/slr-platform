"""Migration 0025 tests: Fresh database and Existing DB upgrade for Task 10.6 research gaps."""

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


def test_migration_0025_fresh_database(tmp_path: Path):
    """Verifies that all migrations 0001-0025 execute cleanly on a fresh database."""
    db_path = tmp_path / "fresh_research_gaps.db"
    _apply_migrations_up_to(db_path, "0025_research_gap_synthesis.sql")

    conn = sqlite3.connect(db_path)
    try:
        c1 = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='synthesis_research_gaps';"
        )
        assert c1.fetchone() is not None

        c2 = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='synthesis_research_gap_links';"
        )
        assert c2.fetchone() is not None

        idx = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_synthesis_research_gaps_proj';"
        )
        assert idx.fetchone() is not None

        idx_links = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_synthesis_research_gap_links_proj';"
        )
        assert idx_links.fetchone() is not None

        fk_check = conn.execute("PRAGMA foreign_key_check;").fetchall()
        assert fk_check == []

        integrity_check = conn.execute("PRAGMA integrity_check;").fetchone()
        assert integrity_check == ("ok",)
    finally:
        conn.close()


def test_migration_0025_existing_db_upgrade(tmp_path: Path):
    """Verifies that upgrading an existing 0024 DB preserves prior Phase 10 data."""
    db_path = tmp_path / "upgrade_research_gaps.db"

    _apply_migrations_up_to(db_path, "0024_context_synthesis.sql")

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")

    proj_id = "test-proj-gap-upgrade"
    rel_id = str(uuid4())
    group_item_id = str(uuid4())
    pub_id = str(uuid4())
    rev_id = str(uuid4())
    conn.execute(
        "INSERT INTO projects (project_id, title, description) VALUES (?, ?, ?);",
        (proj_id, "Research Gap Upgrade Project", "Desc"),
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
    conn.commit()
    conn.close()

    _apply_migrations_up_to(db_path, "0025_research_gap_synthesis.sql")

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")

    read_rel = conn.execute(
        "SELECT source_practice, magnitude FROM synthesis_analytical_relations WHERE relation_id = ?;",
        (rel_id,),
    ).fetchone()
    assert read_rel == ("5S Visual Controls", None)

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
    link_id = str(uuid4())
    conn.execute(
        "INSERT INTO synthesis_research_gap_links ("
        "link_id, project_id, gap_id, link_type, target_id, group_item_id, publication_id, latest_revision_id"
        ") VALUES (?, ?, ?, ?, ?, ?, ?, ?);",
        (
            link_id,
            proj_id,
            gap_id,
            "analytical_relation",
            rel_id,
            group_item_id,
            pub_id,
            rev_id,
        ),
    )
    conn.commit()

    read_gap = conn.execute(
        "SELECT gap_type, title FROM synthesis_research_gaps WHERE gap_id = ?;",
        (gap_id,),
    ).fetchone()
    assert read_gap == ("thematic", "Under-studied practice")

    read_link = conn.execute(
        "SELECT link_type, target_id FROM synthesis_research_gap_links WHERE link_id = ?;",
        (link_id,),
    ).fetchone()
    assert read_link == ("analytical_relation", rel_id)

    fk_check = conn.execute("PRAGMA foreign_key_check;").fetchall()
    assert fk_check == []
    integrity_check = conn.execute("PRAGMA integrity_check;").fetchone()
    assert integrity_check == ("ok",)

    conn.close()
