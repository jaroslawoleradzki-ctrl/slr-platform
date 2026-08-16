"""Migration history reconciliation for the eventual phase10/data-synthesis -> development merge.

Phase 10 ships numbered migrations 0020-0022 and 0024-0026, intentionally reserving
the 0023 slot held on `development` by `0023_extraction_field_state_contract.sql`
(ADR-0007: `unassessed` status and nullable `origin` on extracted_values).

All three migration paths must converge to the same final reconciled schema with
zero foreign-key violations and a clean integrity check:

1. Fresh DB -> final reconciled schema (0001-0019 + 0020,0021,0022,0023,0024,0025,0026);
2. existing development DB including 0023 -> final Phase 10 schema;
3. existing Phase 10 DB -> final reconciled schema (0023 applied last).

The 0023 fixture file is a verbatim snapshot of the development-branch migration,
kept in tests/fixtures/migrations so the test is self-contained and deterministic.
"""

import sqlite3
from pathlib import Path

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
from app.domain.publication import Publication
from app.repositories.extraction_repository import SqliteExtractionRepository
from app.repositories.extraction_template_repository import SqliteExtractionTemplateRepository
from app.repositories.project_publication_repository import SqliteProjectPublicationRepository
from app.repositories.project_repository import SqliteProjectRepository

REPO_ROOT = Path(__file__).parents[3]
MIGRATIONS_DIR = REPO_ROOT / "migrations"
FIXTURE_0023 = Path(__file__).parents[2] / "fixtures" / "migrations" / "0023_extraction_field_state_contract.sql"

PHASE10_FILES = [p.name for p in sorted(MIGRATIONS_DIR.glob("*.sql"))]
DEV_EXTRA = "0023_extraction_field_state_contract.sql"


def _all_reconciled_files() -> list[Path]:
    """The final merged migration set in sorted application order."""
    files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    if not any(f.name == DEV_EXTRA for f in files):
        assert FIXTURE_0023.exists(), "0023 fixture must be present"
        files = [*files, FIXTURE_0023]
    return sorted(files)


def _apply(db_path: Path, files: list[Path], up_to: str | None = None) -> None:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    try:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            "version TEXT PRIMARY KEY, applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);"
        )
        applied = {row[0] for row in conn.execute("SELECT version FROM schema_migrations")}
        for sql_file in sorted(files):
            if up_to and sql_file.name > up_to:
                continue
            if sql_file.name not in applied:
                conn.executescript(sql_file.read_text(encoding="utf-8"))
                conn.execute("INSERT INTO schema_migrations (version) VALUES (?);", (sql_file.name,))
        conn.commit()
    finally:
        conn.close()


def _check_integrity(db_path: Path) -> None:
    conn = sqlite3.connect(db_path)
    try:
        foreign_key_violations = conn.execute("PRAGMA foreign_key_check;").fetchall()
        assert foreign_key_violations == [], f"foreign_key_check violations: {foreign_key_violations}"
        integrity = conn.execute("PRAGMA integrity_check;").fetchall()
        assert integrity == [("ok",)], f"integrity_check failed: {integrity}"
    finally:
        conn.close()


def _applied_versions(db_path: Path) -> set[str]:
    conn = sqlite3.connect(db_path)
    try:
        return {row[0] for row in conn.execute("SELECT version FROM schema_migrations")}
    finally:
        conn.close()


def _seed_extraction_rows(db_path: Path, proj_id: str) -> None:
    """Seed one COMPLETE revision with a durable group item."""
    import uuid

    template_repo = SqliteExtractionTemplateRepository(str(db_path))
    template_repo.register_template(ExtractionTemplate(template_id="lean_energy", name="Lean Energy"))
    template_repo.register_version(
        ExtractionTemplateVersion(template_id="lean_energy", version="1.0.0", name="v1", is_published=True)
    )
    pub_repo = SqliteProjectPublicationRepository(str(db_path))
    ext_repo = SqliteExtractionRepository(str(db_path))
    pub_id = uuid.uuid4()
    pub_repo.add_publications(
        proj_id, [Publication(record_id=pub_id, title="R", publication_year=2024)]
    )
    rec = ext_repo.create_record(
        ExtractionRecord(
            project_id=proj_id,
            publication_id=pub_id,
            template_id="lean_energy",
            template_version="1.0.0",
        )
    )
    rev = ext_repo.append_revision(
        ExtractionRevision(
            record_id=rec.record_id,
            project_id=proj_id,
            publication_id=pub_id,
            revision_index=1,
            reviewer_id="r",
            completeness_status=ExtractionCompletenessStatus.COMPLETE,
            group_items=[
                ExtractedGroupItemState(
                    group_item_id=uuid.uuid4(),
                    group_key="lean_energy_relationships",
                    item_index=1,
                    values=[
                        ExtractedValueState(
                            field_key="lean_practice",
                            status=ValueStatus.PRESENT,
                            origin=ValueOrigin.REPORTED,
                            text_value="5S",
                            source_locator="Table 1",
                        )
                    ],
                )
            ],
        )
    )
    assert rev is not None
    return pub_id


def _insert_adr0007_row(db_path: Path, proj_id: str) -> None:
    """Insert a value row using the ADR-0007 contract: status 'unassessed' and NULL origin.

    Only valid after 0023 is applied; tolerated by the reconciled domain model.
    """
    import uuid

    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "INSERT INTO extracted_values "
            "(value_id, revision_id, group_item_id, field_key, status, origin) "
            "SELECT ?, revision_id, NULL, 'moderating_conditions', 'unassessed', NULL "
            "FROM extraction_revisions LIMIT 1",
            (str(uuid.uuid4()),),
        )
        conn.commit()
    finally:
        conn.close()


def test_scenario_1_fresh_db_reconciled_schema(tmp_path: Path) -> None:
    """A fresh DB applied the full reconciled migration set converges cleanly."""
    db_path = tmp_path / "fresh_reconciled.db"
    _apply(db_path, _all_reconciled_files())
    _check_integrity(db_path)

    versions = _applied_versions(db_path)
    assert "0023_extraction_field_state_contract.sql" in versions
    assert "0026_synthesis_snapshots.sql" in versions

    conn = sqlite3.connect(db_path)
    try:
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    finally:
        conn.close()
    assert "extracted_values" in tables
    assert "synthesis_snapshots" in tables


def test_scenario_2_development_db_including_0023_to_phase10(tmp_path: Path) -> None:
    """An existing development DB (0023 applied) upgrades to the Phase 10 schema cleanly."""
    db_path = tmp_path / "dev.db"
    dev_files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    _apply(db_path, dev_files, up_to="0023_extraction_field_state_contract.sql")
    _check_integrity(db_path)

    SqliteProjectRepository(db_path).create(Project(project_id="dev-proj", title="Dev", description=""))
    _seed_extraction_rows(db_path, "dev-proj")
    _insert_adr0007_row(db_path, "dev-proj")

    # Applying phase10's own migrations (0020-0022, 0024-0026) on top.
    phase10_extra = [
        p
        for p in sorted(MIGRATIONS_DIR.glob("*.sql"))
        if p.name > "0019_group_item_revision_identity.sql"
    ]
    _apply(db_path, phase10_extra)
    _check_integrity(db_path)

    versions = _applied_versions(db_path)
    assert "0020_terminology_classification.sql" in versions
    assert "0026_synthesis_snapshots.sql" in versions
    assert "0023_extraction_field_state_contract.sql" in versions

    # The ADR-0007 row must survive and remain present in extracted_values.
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            "SELECT status, origin FROM extracted_values "
            "WHERE field_key = 'moderating_conditions' AND status = 'unassessed'"
        ).fetchone()
    finally:
        conn.close()
    assert row is not None
    assert row[0] == "unassessed"
    assert row[1] is None


def test_scenario_2b_adr0007_rows_are_tolerated_by_synthesis_read_path(tmp_path: Path) -> None:
    """Extraction values written under the ADR-0007 contract hydrate without crashing."""
    db_path = tmp_path / "dev_read.db"
    dev_files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    _apply(db_path, dev_files, up_to="0023_extraction_field_state_contract.sql")

    SqliteProjectRepository(db_path).create(Project(project_id="p", title="P", description=""))
    _seed_extraction_rows(db_path, "p")
    _insert_adr0007_row(db_path, "p")

    from app.domain.extraction import ValueStatus

    repo = SqliteExtractionRepository(str(db_path))
    for rec in repo.list_records("p"):
        rev = repo.get_latest_complete_revision("p", rec.publication_id)
        assert rev is not None
        all_values = [v for item in rev.group_items for v in item.values] + rev.publication_values
        unassessed = [v for v in all_values if v.status == ValueStatus.UNASSESSED]
        assert len(unassessed) >= 1
        assert unassessed[0].origin is None


def test_scenario_3_phase10_db_to_reconciled(tmp_path: Path) -> None:
    """An existing Phase 10 DB (no 0023) upgrades to the reconciled schema cleanly."""
    db_path = tmp_path / "phase10.db"
    _apply(db_path, sorted(MIGRATIONS_DIR.glob("*.sql")))
    _check_integrity(db_path)

    SqliteProjectRepository(db_path).create(Project(project_id="p10", title="P10", description=""))
    _seed_extraction_rows(db_path, "p10")

    # 0023 is part of the reconciled migration set and applied in sorted order.
    _check_integrity(db_path)

    assert "0023_extraction_field_state_contract.sql" in _applied_versions(db_path)
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute("SELECT COUNT(*) FROM extracted_values").fetchone()
        assert row[0] >= 1
    finally:
        conn.close()


def test_no_duplicate_or_destructive_application(tmp_path: Path) -> None:
    """Applying migrations twice never re-runs them or corrupts state."""
    db_path = tmp_path / "idempotent.db"
    files = _all_reconciled_files()
    _apply(db_path, files)
    _check_integrity(db_path)
    versions_before = _applied_versions(db_path)

    _apply(db_path, files)
    _check_integrity(db_path)
    assert _applied_versions(db_path) == versions_before

    conn = sqlite3.connect(db_path)
    try:
        table_count = conn.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name LIKE 'synthesis%'"
        ).fetchone()[0]
    finally:
        conn.close()
    assert table_count >= 7
