"""Migration 0022 tests: Fresh database and Existing DB upgrade with Task 10.3 data."""

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


def test_migration_0022_fresh_database(tmp_path: Path):
    """Verifies that all migrations 0001-0022 execute cleanly on a fresh database."""
    db_path = tmp_path / "fresh_mechanisms.db"
    _apply_migrations_up_to(db_path, "0022_mechanism_synthesis.sql")

    conn = sqlite3.connect(db_path)
    try:
        # Check mechanism tables exist
        c1 = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='synthesis_mechanism_categories';"
        )
        assert c1.fetchone() is not None

        c2 = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='synthesis_mechanism_pathways';")
        assert c2.fetchone() is not None

        # Check indexes exist
        idx = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_synthesis_mechanism_pathways_proj';"
        )
        assert idx.fetchone() is not None

        # PRAGMA checks
        fk_check = conn.execute("PRAGMA foreign_key_check;").fetchall()
        assert fk_check == []

        integrity_check = conn.execute("PRAGMA integrity_check;").fetchone()
        assert integrity_check == ("ok",)
    finally:
        conn.close()


def test_migration_0022_existing_db_upgrade(tmp_path: Path):
    """Verifies that upgrading an existing 0021 DB with Phase 9/10.3 relations preserves all data."""
    db_path = tmp_path / "upgrade_mechanisms.db"

    # Apply migrations 0001 through 0021
    _apply_migrations_up_to(db_path, "0021_analytical_relations.sql")

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")

    # Insert baseline data in project, categories, and analytical relations
    proj_id = "test-proj-mech-upgrade"
    conn.execute(
        "INSERT INTO projects (project_id, title, description) VALUES (?, ?, ?);",
        (proj_id, "Mechanism Upgrade Project", "Desc"),
    )
    conn.execute(
        "INSERT INTO synthesis_lean_categories (category_id, project_id, name) VALUES (?, ?, ?);",
        ("cat-5s", proj_id, "5S Methodology"),
    )
    conn.execute(
        "INSERT INTO synthesis_energy_categories (category_id, project_id, name) VALUES (?, ?, ?);",
        ("cat-elec", proj_id, "Electricity Consumption"),
    )

    rel_id = str(uuid4())
    group_item_id = str(uuid4())
    pub_id = str(uuid4())
    rev_id = str(uuid4())
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
            pub_id,
            rev_id,
            group_item_id,
            1,
            "5S Visual Controls",
            "cat-5s",
            "Power reduction",
            "cat-elec",
            "positive",
            15.0,
            "kWh",
            "empirical",
            "approved",
        ),
    )
    conn.commit()
    conn.close()

    # Now apply migration 0022
    _apply_migrations_up_to(db_path, "0022_mechanism_synthesis.sql")

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")

    # Verify existing analytical relation is intact
    read_rel = conn.execute(
        "SELECT source_practice, magnitude FROM synthesis_analytical_relations WHERE relation_id = ?;",
        (rel_id,),
    ).fetchone()
    assert read_rel == ("5S Visual Controls", 15.0)

    # Insert mechanism category and pathway
    mech_cat_id = "idle_reduction"
    conn.execute(
        "INSERT INTO synthesis_mechanism_categories (project_id, category_id, name) VALUES (?, ?, ?);",
        (proj_id, mech_cat_id, "Idle Reduction Mechanism"),
    )

    pathway_id = str(uuid4())
    conn.execute(
        """
        INSERT INTO synthesis_mechanism_pathways (
            pathway_id, project_id, analytical_relation_id, group_item_id, publication_id,
            latest_revision_id, source_mechanism_text, analytical_mechanism_category_id,
            is_review_synthesized, approval_state
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """,
        (
            pathway_id,
            proj_id,
            rel_id,
            group_item_id,
            pub_id,
            rev_id,
            "Reduced machine standby time by turning off during changeovers.",
            mech_cat_id,
            0,
            "approved",
        ),
    )
    conn.commit()

    # Verify pathway read
    read_pathway = conn.execute(
        "SELECT source_mechanism_text, analytical_mechanism_category_id FROM synthesis_mechanism_pathways WHERE pathway_id = ?;",
        (pathway_id,),
    ).fetchone()
    assert read_pathway == ("Reduced machine standby time by turning off during changeovers.", mech_cat_id)

    # PRAGMA checks
    fk_check = conn.execute("PRAGMA foreign_key_check;").fetchall()
    assert fk_check == []
    integrity_check = conn.execute("PRAGMA integrity_check;").fetchone()
    assert integrity_check == ("ok",)

    conn.close()
