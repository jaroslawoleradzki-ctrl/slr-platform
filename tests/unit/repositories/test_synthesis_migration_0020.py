"""Tests for Migration 0020: Terminology Classification Persistence."""

import sqlite3
from pathlib import Path
from uuid import uuid4

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


def test_fresh_database_migration_0001_to_0020(tmp_path: Path):
    db_path = tmp_path / "fresh_0020.db"
    _apply_migrations_up_to(db_path, "0020_terminology_classification.sql")

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    try:
        # 1. Verify foreign keys and integrity
        fk_violations = conn.execute("PRAGMA foreign_key_check;").fetchall()
        assert len(fk_violations) == 0, f"FK violations: {fk_violations}"

        integrity = conn.execute("PRAGMA integrity_check;").fetchall()
        assert integrity == [("ok",)]

        # 2. Verify tables exist
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()}
        assert "synthesis_lean_categories" in tables
        assert "synthesis_energy_categories" in tables
        assert "synthesis_term_mappings" in tables

        # 3. Verify indexes exist
        indexes = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='index';").fetchall()}
        assert "idx_synthesis_lean_categories_proj" in indexes
        assert "idx_synthesis_energy_categories_proj" in indexes
        assert "idx_synthesis_term_mappings_lookup" in indexes
    finally:
        conn.close()

    # 4. Perform roundtrip using repositories on fresh DB
    proj_repo = SqliteProjectRepository(db_path)
    proj_repo.create(Project(project_id="proj-fresh", title="Fresh DB Project"))

    from app.domain.synthesis import (
        ClassificationApprovalState,
        EnergyEffectCategory,
        LeanPracticeCategory,
        TermMapping,
        TermType,
    )
    from app.repositories.synthesis_classification_repository import SqliteSynthesisClassificationRepository

    class_repo = SqliteSynthesisClassificationRepository(db_path)

    lean_cat = class_repo.create_lean_category(
        LeanPracticeCategory(
            project_id="proj-fresh",
            category_id="5s",
            name="5S & Visual Management",
            description="5S tools",
            display_order=1,
        )
    )
    assert lean_cat.category_id == "5s"

    energy_cat = class_repo.create_energy_category(
        EnergyEffectCategory(
            project_id="proj-fresh",
            category_id="elec",
            name="Electricity Reduction",
            description="kWh reduction",
            display_order=1,
        )
    )
    assert energy_cat.category_id == "elec"

    mapping = class_repo.save_term_mapping(
        TermMapping(
            project_id="proj-fresh",
            term_type=TermType.LEAN_PRACTICE,
            source_value="5S Visual",
            analytical_category_id="5s",
            approval_state=ClassificationApprovalState.APPROVED,
            approved_by="rev-1",
        )
    )
    assert mapping.source_value == "5S Visual"
    assert mapping.analytical_category_id == "5s"

    # 5. Verify database reopen
    class_repo_reopen = SqliteSynthesisClassificationRepository(db_path)
    reopened_mapping = class_repo_reopen.get_term_mapping("proj-fresh", TermType.LEAN_PRACTICE, "5S Visual")
    assert reopened_mapping is not None
    assert reopened_mapping.analytical_category_id == "5s"
    assert reopened_mapping.approval_state == ClassificationApprovalState.APPROVED

    # 6. Verify PRAGMAs after roundtrip
    conn2 = sqlite3.connect(db_path)
    conn2.execute("PRAGMA foreign_keys = ON;")
    try:
        assert len(conn2.execute("PRAGMA foreign_key_check;").fetchall()) == 0
        assert conn2.execute("PRAGMA integrity_check;").fetchall() == [("ok",)]
    finally:
        conn2.close()


def test_existing_database_migration_from_0019_to_0020(tmp_path: Path):
    db_path = tmp_path / "existing_0019_to_0020.db"

    # 1. Apply up to 0019
    _apply_migrations_up_to(db_path, "0019_group_item_revision_identity.sql")

    # 2. Populate realistic Phase 9 extraction data
    proj_repo = SqliteProjectRepository(db_path)
    proj_repo.create(Project(project_id="proj-mig-test", title="Migration Test Project"))

    template_repo = SqliteExtractionTemplateRepository(db_path)
    template_repo.register_template(ExtractionTemplate(template_id="lean_energy", name="Lean Energy"))
    template_repo.register_version(
        ExtractionTemplateVersion(template_id="lean_energy", version="1.0.0", name="v1", is_published=True)
    )

    extraction_repo = SqliteExtractionRepository(db_path)
    pub_id = uuid4()
    rec = extraction_repo.create_record(
        ExtractionRecord(
            project_id="proj-mig-test", publication_id=pub_id, template_id="lean_energy", template_version="1.0.0"
        )
    )

    group_id_1 = uuid4()
    rev1 = ExtractionRevision(
        record_id=rec.record_id,
        project_id="proj-mig-test",
        publication_id=pub_id,
        revision_index=1,
        reviewer_id="reviewer-1",
        completeness_status=ExtractionCompletenessStatus.COMPLETE,
        publication_values=[
            ExtractedValueState(
                field_key="study_design",
                status=ValueStatus.PRESENT,
                origin=ValueOrigin.REPORTED,
                text_value="Case Study",
            )
        ],
        group_items=[
            ExtractedGroupItemState(
                group_item_id=group_id_1,
                group_key="lean_ee_relationships",
                item_index=1,
                values=[
                    ExtractedValueState(
                        field_key="lean_practice",
                        status=ValueStatus.PRESENT,
                        origin=ValueOrigin.REPORTED,
                        text_value="5S Visual Management",
                    ),
                    ExtractedValueState(
                        field_key="energy_effect_indicator",
                        status=ValueStatus.PRESENT,
                        origin=ValueOrigin.REPORTED,
                        text_value="15% electricity reduction",
                    ),
                ],
            )
        ],
    )
    extraction_repo.append_revision(rev1)

    # 3. Apply migration 0020
    _apply_migrations_up_to(db_path, "0020_terminology_classification.sql")

    # 4. Verify Phase 9 data untouched and complete
    rev_after = extraction_repo.get_latest_revision("proj-mig-test", pub_id)
    assert rev_after is not None
    assert rev_after.revision_id == rev1.revision_id
    assert len(rev_after.group_items) == 1
    assert rev_after.group_items[0].group_item_id == group_id_1
    practice_val = next(v for v in rev_after.group_items[0].values if v.field_key == "lean_practice")
    assert practice_val.text_value == "5S Visual Management"
    effect_val = next(v for v in rev_after.group_items[0].values if v.field_key == "energy_effect_indicator")
    assert effect_val.text_value == "15% electricity reduction"

    # 5. Verify PRAGMAs after migration
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    try:
        fk_violations = conn.execute("PRAGMA foreign_key_check;").fetchall()
        assert len(fk_violations) == 0, f"FK violations: {fk_violations}"

        integrity = conn.execute("PRAGMA integrity_check;").fetchall()
        assert integrity == [("ok",)]
    finally:
        conn.close()
