"""Migration regression tests for 0018 -> 0019 extraction schema upgrade."""

import sqlite3
from pathlib import Path
from uuid import uuid4

import pytest

from app.domain.extraction import (
    ExtractedGroupItemState,
    ExtractedValueState,
    ExtractionCompletenessStatus,
    ExtractionRecord,
    ExtractionRevision,
    ExtractionTemplate,
    ExtractionTemplateVersion,
    ValueOrigin,
    ValueStatus,
)
from app.domain.project import Project
from app.repositories.extraction_repository import SqliteExtractionRepository
from app.repositories.extraction_template_repository import SqliteExtractionTemplateRepository
from app.repositories.project_repository import SqliteProjectRepository


def _apply_migrations_up_to(db_path: Path, max_migration: str) -> None:
    """Apply migrations up to and including max_migration."""
    migrations_dir = Path(__file__).parents[3] / "migrations"
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations (version TEXT PRIMARY KEY, applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"
        )
        applied = {row[0] for row in conn.execute("SELECT version FROM schema_migrations")}
        for sql_file in sorted(migrations_dir.glob("*.sql")):
            if sql_file.name <= max_migration and sql_file.name not in applied:
                conn.executescript(sql_file.read_text(encoding="utf-8"))
                conn.execute("INSERT INTO schema_migrations(version) VALUES (?)", (sql_file.name,))


def test_existing_database_migration_0018_to_0019_preserves_data_and_enables_durable_identity(tmp_path: Path):
    """Verifies that an existing database running 0018 can safely migrate to 0019 without data loss,

    maintaining full relational integrity and enabling durable group_item_id across revisions.
    """
    db_path = tmp_path / "migration_test.db"

    # Step 1: Initialize DB with migrations strictly up to 0018
    _apply_migrations_up_to(db_path, "0018_data_extraction.sql")

    # Step 2: Seed project and template via SQL (avoid calling SqliteExtractionTemplateRepository which applies all migrations)
    with sqlite3.connect(db_path) as conn:
        conn.execute("INSERT INTO projects (project_id, title) VALUES ('proj-mig', 'Migration Study')")
        conn.execute(
            "INSERT INTO extraction_templates (template_id, name, created_at) VALUES ('lean_ee', 'Lean EE', '2026-08-15T00:00:00Z')"
        )
        conn.execute(
            """INSERT INTO extraction_template_versions (template_id, version, is_active, is_published, schema_json, created_at)
            VALUES ('lean_ee', '1.0.0', 1, 1, '{"template_id":"lean_ee","version":"1.0.0","name":"Lean EE v1","is_published":true,"is_active":true,"publication_fields":[],"repeating_groups":[]}', '2026-08-15T00:00:00Z')"""
        )

    # Step 3: Insert realistic Phase 9 extraction data on old 0018 schema
    pub_id = uuid4()
    rec_id = uuid4()
    rev1_id = uuid4()
    group_id_1 = uuid4()
    val_pub_id = uuid4()
    val_child_1_id = uuid4()
    val_child_2_id = uuid4()

    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute(
            """INSERT INTO extraction_records
            (record_id, project_id, publication_id, template_id, template_version, current_status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                str(rec_id),
                "proj-mig",
                str(pub_id),
                "lean_ee",
                "1.0.0",
                "in_progress",
                "2026-08-15T00:00:00Z",
                "2026-08-15T00:00:00Z",
            ),
        )
        conn.execute(
            """INSERT INTO extraction_revisions
            (revision_id, record_id, project_id, publication_id, revision_index, reviewer_id, completeness_status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                str(rev1_id),
                str(rec_id),
                "proj-mig",
                str(pub_id),
                1,
                "rev_alice",
                "in_progress",
                "2026-08-15T00:00:00Z",
            ),
        )
        conn.execute(
            """INSERT INTO extracted_values
            (value_id, revision_id, group_item_id, field_key, status, origin, text_value, source_page, source_quote, reviewer_note)
            VALUES (?, ?, NULL, ?, ?, ?, ?, ?, ?, ?)""",
            (
                str(val_pub_id),
                str(rev1_id),
                "study_design",
                "present",
                "reported",
                "Case Study",
                "Page 3",
                "Empirical assessment in manufacturing",
                "Reviewer note on design",
            ),
        )
        conn.execute(
            """INSERT INTO extracted_group_items
            (group_item_id, revision_id, group_key, item_index, created_at)
            VALUES (?, ?, ?, ?, ?)""",
            (str(group_id_1), str(rev1_id), "lean_ee_relationships", 1, "2026-08-15T00:00:00Z"),
        )
        conn.execute(
            """INSERT INTO extracted_values
            (value_id, revision_id, group_item_id, field_key, status, origin, text_value, float_value, unit_value, source_page, source_locator)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                str(val_child_1_id),
                str(rev1_id),
                str(group_id_1),
                "practice",
                "present",
                "reported",
                "Value Stream Mapping",
                None,
                None,
                "Page 4",
                "Section 3.1",
            ),
        )
        conn.execute(
            """INSERT INTO extracted_values
            (value_id, revision_id, group_item_id, field_key, status, origin, text_value, float_value, unit_value, source_page, source_locator)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                str(val_child_2_id),
                str(rev1_id),
                str(group_id_1),
                "effect",
                "present",
                "reported",
                None,
                14.2,
                "%",
                "Page 5",
                "Table 2",
            ),
        )

    # Step 4: Verify that on old 0018 schema, inserting revision 2 with the same group_item_id FAILS
    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        rev2_test_id = uuid4()
        conn.execute(
            """INSERT INTO extraction_revisions
            (revision_id, record_id, project_id, publication_id, revision_index, reviewer_id, completeness_status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                str(rev2_test_id),
                str(rec_id),
                "proj-mig",
                str(pub_id),
                2,
                "rev_alice",
                "in_progress",
                "2026-08-15T01:00:00Z",
            ),
        )
        with pytest.raises(
            sqlite3.IntegrityError, match="UNIQUE constraint failed: extracted_group_items.group_item_id"
        ):
            conn.execute(
                """INSERT INTO extracted_group_items
                (group_item_id, revision_id, group_key, item_index, created_at)
                VALUES (?, ?, ?, ?, ?)""",
                (str(group_id_1), str(rev2_test_id), "lean_ee_relationships", 1, "2026-08-15T01:00:00Z"),
            )
        # Roll back test rev2
        conn.execute("DELETE FROM extraction_revisions WHERE revision_id = ?", (str(rev2_test_id),))

    # Step 5: Run migration 0019
    _apply_migrations_up_to(db_path, "0019_group_item_revision_identity.sql")

    # Step 6: Verify PRAGMA foreign_key_check and PRAGMA integrity_check
    with sqlite3.connect(db_path) as conn:
        fk_violations = conn.execute("PRAGMA foreign_key_check").fetchall()
        assert fk_violations == [], f"Foreign key violations found after migration 0019: {fk_violations}"

        integrity = conn.execute("PRAGMA integrity_check").fetchall()
        assert integrity == [("ok",)], f"Integrity check failed: {integrity}"

        # Verify row counts are preserved
        assert conn.execute("SELECT COUNT(*) FROM extraction_records").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM extraction_revisions").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM extracted_group_items").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM extracted_values").fetchone()[0] == 3

    # Step 7: Hydrate using repository and verify exact data preservation
    extraction_repo = SqliteExtractionRepository(db_path)
    hydrated_r1 = extraction_repo.get_latest_revision("proj-mig", pub_id)
    assert hydrated_r1 is not None
    assert hydrated_r1.revision_index == 1
    assert len(hydrated_r1.publication_values) == 1
    assert hydrated_r1.publication_values[0].field_key == "study_design"
    assert hydrated_r1.publication_values[0].text_value == "Case Study"
    assert hydrated_r1.publication_values[0].source_page == "Page 3"
    assert hydrated_r1.publication_values[0].reviewer_note == "Reviewer note on design"

    assert len(hydrated_r1.group_items) == 1
    assert hydrated_r1.group_items[0].group_item_id == group_id_1
    assert hydrated_r1.group_items[0].item_index == 1
    child_vals = {v.field_key: v for v in hydrated_r1.group_items[0].values}
    assert child_vals["practice"].text_value == "Value Stream Mapping"
    assert child_vals["practice"].source_locator == "Section 3.1"
    assert child_vals["effect"].float_value == 14.2
    assert child_vals["effect"].unit_value == "%"

    # Step 8: Append Revision 2 reusing group_id_1 with modified values and a new group item
    group_id_2 = uuid4()
    r2 = ExtractionRevision(
        record_id=rec_id,
        project_id="proj-mig",
        publication_id=pub_id,
        revision_index=2,
        reviewer_id="rev_bob",
        completeness_status=ExtractionCompletenessStatus.COMPLETE,
        publication_values=[
            ExtractedValueState(
                field_key="study_design",
                status=ValueStatus.PRESENT,
                origin=ValueOrigin.REPORTED,
                text_value="Case Study (Updated)",
            )
        ],
        group_items=[
            ExtractedGroupItemState(
                group_item_id=group_id_1,  # Same durable ID
                group_key="lean_ee_relationships",
                item_index=1,
                values=[
                    ExtractedValueState(
                        field_key="practice",
                        status=ValueStatus.PRESENT,
                        origin=ValueOrigin.REPORTED,
                        text_value="Value Stream Mapping Extended",
                    ),
                    ExtractedValueState(
                        field_key="effect",
                        status=ValueStatus.PRESENT,
                        origin=ValueOrigin.REPORTED,
                        float_value=16.5,
                        unit_value="%",
                    ),
                ],
            ),
            ExtractedGroupItemState(
                group_item_id=group_id_2,  # New durable ID
                group_key="lean_ee_relationships",
                item_index=2,
                values=[
                    ExtractedValueState(
                        field_key="practice", status=ValueStatus.PRESENT, origin=ValueOrigin.REPORTED, text_value="5S"
                    ),
                    ExtractedValueState(
                        field_key="effect",
                        status=ValueStatus.PRESENT,
                        origin=ValueOrigin.REPORTED,
                        float_value=5.0,
                        unit_value="%",
                    ),
                ],
            ),
        ],
    )
    extraction_repo.append_revision(r2)

    # Step 9: Verify foreign key check & integrity check on multi-revision state
    with sqlite3.connect(db_path) as conn:
        fk_violations = conn.execute("PRAGMA foreign_key_check").fetchall()
        assert fk_violations == [], f"Foreign key violations: {fk_violations}"
        assert conn.execute("PRAGMA integrity_check").fetchall() == [("ok",)]

    # Step 10: Verify both revisions remain independently and accurately readable
    history = extraction_repo.list_revision_history("proj-mig", pub_id)
    assert len(history) == 2

    # Revision 1 history check
    assert history[0].revision_index == 1
    assert [item.group_item_id for item in history[0].group_items] == [group_id_1]
    h1_vals = {v.field_key: v for v in history[0].group_items[0].values}
    assert h1_vals["practice"].text_value == "Value Stream Mapping"
    assert h1_vals["effect"].float_value == 14.2

    # Revision 2 history check
    assert history[1].revision_index == 2
    assert [item.group_item_id for item in history[1].group_items] == [group_id_1, group_id_2]
    h2_vals_1 = {v.field_key: v for v in history[1].group_items[0].values}
    assert h2_vals_1["practice"].text_value == "Value Stream Mapping Extended"
    assert h2_vals_1["effect"].float_value == 16.5
    h2_vals_2 = {v.field_key: v for v in history[1].group_items[1].values}
    assert h2_vals_2["practice"].text_value == "5S"
    assert h2_vals_2["effect"].float_value == 5.0


def test_fresh_database_full_migration_chain_integrity(tmp_path: Path):
    """Verifies that a fresh database applying 0001 through 0019 in sequence achieves 100% schema integrity."""
    db_path = tmp_path / "fresh_chain_test.db"

    # Apply all migrations from scratch
    _apply_migrations_up_to(db_path, "9999_final.sql")

    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        fk_violations = conn.execute("PRAGMA foreign_key_check").fetchall()
        assert fk_violations == [], f"Foreign key violations in fresh DB: {fk_violations}"

        integrity = conn.execute("PRAGMA integrity_check").fetchall()
        assert integrity == [("ok",)], f"Integrity check failed in fresh DB: {integrity}"

        # Verify composite primary key on extracted_group_items
        table_info = conn.execute("PRAGMA table_info(extracted_group_items)").fetchall()
        # pk flag is column index 5 (0-indexed)
        pk_cols = [row[1] for row in table_info if row[5] > 0]
        assert set(pk_cols) == {"revision_id", "group_item_id"}

    # Test full extraction lifecycle on fresh database
    project_repo = SqliteProjectRepository(db_path)
    project_repo.create(Project(project_id="proj-fresh", title="Fresh DB Study"))
    template_repo = SqliteExtractionTemplateRepository(db_path)
    template_repo.register_template(ExtractionTemplate(template_id="t1", name="T1"))
    template_repo.register_version(
        ExtractionTemplateVersion(template_id="t1", version="1.0.0", name="T1 v1", is_published=True)
    )

    extraction_repo = SqliteExtractionRepository(db_path)
    pub_id = uuid4()
    rec = extraction_repo.create_record(
        ExtractionRecord(project_id="proj-fresh", publication_id=pub_id, template_id="t1", template_version="1.0.0")
    )

    shared_group_id = uuid4()
    r1 = ExtractionRevision(
        record_id=rec.record_id,
        project_id="proj-fresh",
        publication_id=pub_id,
        revision_index=1,
        reviewer_id="rev_1",
        completeness_status=ExtractionCompletenessStatus.IN_PROGRESS,
        group_items=[
            ExtractedGroupItemState(
                group_item_id=shared_group_id,
                group_key="relations",
                item_index=1,
                values=[
                    ExtractedValueState(
                        field_key="val", status=ValueStatus.PRESENT, origin=ValueOrigin.REPORTED, text_value="v1"
                    )
                ],
            )
        ],
    )
    r2 = ExtractionRevision(
        record_id=rec.record_id,
        project_id="proj-fresh",
        publication_id=pub_id,
        revision_index=2,
        reviewer_id="rev_1",
        completeness_status=ExtractionCompletenessStatus.COMPLETE,
        group_items=[
            ExtractedGroupItemState(
                group_item_id=shared_group_id,
                group_key="relations",
                item_index=1,
                values=[
                    ExtractedValueState(
                        field_key="val", status=ValueStatus.PRESENT, origin=ValueOrigin.REPORTED, text_value="v2"
                    )
                ],
            )
        ],
    )
    extraction_repo.append_revision(r1)
    extraction_repo.append_revision(r2)

    with sqlite3.connect(db_path) as conn:
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
        assert conn.execute("PRAGMA integrity_check").fetchall() == [("ok",)]

    history = extraction_repo.list_revision_history("proj-fresh", pub_id)
    assert len(history) == 2
    assert history[0].group_items[0].values[0].text_value == "v1"
    assert history[1].group_items[0].values[0].text_value == "v2"
    assert history[0].group_items[0].group_item_id == shared_group_id
    assert history[1].group_items[0].group_item_id == shared_group_id
