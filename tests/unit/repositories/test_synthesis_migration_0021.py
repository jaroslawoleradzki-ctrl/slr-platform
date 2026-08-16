"""Migration 0021 tests: Fresh database and Existing DB upgrade with Phase 9 & 10 data."""

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


def test_migration_0021_fresh_database(tmp_path: Path):
    """Verifies that all migrations 0001-0021 execute cleanly on a fresh database."""
    db_path = tmp_path / "fresh_synthesis.db"
    _apply_migrations_up_to(db_path, "0021_analytical_relations.sql")

    conn = sqlite3.connect(db_path)
    try:
        # Check table exists
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='synthesis_analytical_relations';"
        )
        assert cursor.fetchone() is not None

        # Check indexes exist
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_synthesis_relations_proj_cats';"
        )
        assert cursor.fetchone() is not None

        # PRAGMA checks
        fk_check = conn.execute("PRAGMA foreign_key_check;").fetchall()
        assert fk_check == []

        integrity_check = conn.execute("PRAGMA integrity_check;").fetchone()
        assert integrity_check == ("ok",)
    finally:
        conn.close()


def test_migration_0021_existing_db_upgrade(tmp_path: Path):
    """Verifies that upgrading an existing 0020 DB with categories and mappings preserves all data."""
    db_path = tmp_path / "upgrade_synthesis.db"

    # Apply migrations 0001 through 0020
    _apply_migrations_up_to(db_path, "0020_terminology_classification.sql")

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")

    # Insert baseline data in project, categories, and mappings
    proj_id = "test-proj-upgrade"
    conn.execute(
        "INSERT INTO projects (project_id, title, description) VALUES (?, ?, ?);",
        (proj_id, "Upgrade Test Project", "Desc"),
    )
    conn.execute(
        "INSERT INTO synthesis_lean_categories (category_id, project_id, name) VALUES (?, ?, ?);",
        ("cat-5s", proj_id, "5S Methodology"),
    )
    conn.execute(
        "INSERT INTO synthesis_energy_categories (category_id, project_id, name) VALUES (?, ?, ?);",
        ("cat-elec", proj_id, "Electricity Consumption"),
    )
    conn.execute(
        """
        INSERT INTO synthesis_term_mappings (
            mapping_id, project_id, term_type, source_value, analytical_category_id, approval_state
        ) VALUES (?, ?, ?, ?, ?, ?);
        """,
        (str(uuid4()), proj_id, "lean_practice", "5S Visuals", "cat-5s", "approved"),
    )
    conn.commit()
    conn.close()

    # Now apply migration 0021
    _apply_migrations_up_to(db_path, "0021_analytical_relations.sql")

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")

    # Verify existing categories and mappings are intact
    l_cat = conn.execute(
        "SELECT name FROM synthesis_lean_categories WHERE project_id = ? AND category_id = ?;",
        (proj_id, "cat-5s"),
    ).fetchone()
    assert l_cat == ("5S Methodology",)

    mapping = conn.execute(
        "SELECT source_value, approval_state FROM synthesis_term_mappings WHERE project_id = ?;",
        (proj_id,),
    ).fetchone()
    assert mapping == ("5S Visuals", "approved")

    # Verify we can insert and read an analytical relation
    rel_id = str(uuid4())
    group_item_id = str(uuid4())
    conn.execute(
        """
        INSERT INTO synthesis_analytical_relations (
            relation_id, project_id, publication_id, latest_revision_id, group_item_id,
            item_index, source_practice, analytical_lean_category_id, source_effect,
            analytical_energy_category_id, direction, magnitude, original_unit,
            evidence_character, approval_state
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """,
        (
            rel_id,
            proj_id,
            str(uuid4()),
            str(uuid4()),
            group_item_id,
            1,
            "5S Visuals",
            "cat-5s",
            "10 kWh reduction",
            "cat-elec",
            "positive",
            10.0,
            "kWh",
            "empirical",
            "approved",
        ),
    )
    conn.commit()

    read_rel = conn.execute(
        "SELECT source_practice, magnitude FROM synthesis_analytical_relations WHERE relation_id = ?;",
        (rel_id,),
    ).fetchone()
    assert read_rel == ("5S Visuals", 10.0)

    # PRAGMA checks
    fk_check = conn.execute("PRAGMA foreign_key_check;").fetchall()
    assert fk_check == []
    integrity_check = conn.execute("PRAGMA integrity_check;").fetchone()
    assert integrity_check == ("ok",)

    conn.close()
