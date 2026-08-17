import sqlite3
from pathlib import Path
from uuid import uuid4

import pytest

from app.domain.quality_assessment import (
    ProjectQualityAssessmentConfiguration,
    QualityAssessmentTemplate,
    QualityAssessmentTool,
)
from app.repositories.quality_assessment_repository import (
    ProjectQualityAssessmentConfigurationRepository,
)
from app.repositories.sqlite_quality_assessment_repository import (
    SqliteProjectQualityAssessmentConfigurationRepository,
    SqliteQualityAssessmentCatalogRepository,
)


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "test_qa_config.db"


def test_configuration_repository_protocol_runtime_checkable(tmp_path: Path):
    assert isinstance(
        SqliteProjectQualityAssessmentConfigurationRepository(tmp_path / "dummy.db"),
        ProjectQualityAssessmentConfigurationRepository,
    )


def test_sqlite_repository_automatically_applies_0014_migration(tmp_path: Path):
    db = tmp_path / "auto_migration_14.db"
    _ = SqliteProjectQualityAssessmentConfigurationRepository(db)

    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    applied = {row[0] for row in conn.execute("SELECT version FROM schema_migrations")}
    assert "0014_quality_assessment_configuration.sql" in applied

    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "project_quality_assessment_configurations" in tables
    conn.close()


def test_migration_0014_upgrades_existing_0013_database(tmp_path: Path):
    """Regression test: An existing 8.1 database with 0013 applied upgrades cleanly to 0014."""
    db_path = tmp_path / "existing_81.db"
    migrations_dir = Path(__file__).parents[3] / "migrations"

    # 1. Apply migrations 0001..0013 manually
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version TEXT PRIMARY KEY,
            applied_at TEXT NOT NULL
        )
        """
    )
    for m in sorted(migrations_dir.glob("*.sql")):
        if m.name == "0014_quality_assessment_configuration.sql":
            continue
        conn.executescript(m.read_text(encoding="utf-8"))
        conn.execute(
            "INSERT INTO schema_migrations (version, applied_at) VALUES (?, '2026-08-11T08:00:00Z')",
            (m.name,),
        )
    conn.commit()

    # 2. Insert existing 8.1 data
    conn.execute(
        "INSERT INTO quality_assessment_tools (tool_id, name, description, created_at) VALUES ('casp_81', 'CASP 8.1', '8.1 Tool', '2026-08-11T08:00:00Z')"
    )
    conn.commit()
    conn.close()

    # 3. Instantiate 8.2 repository (triggers 0014 migration on existing DB)
    _ = SqliteProjectQualityAssessmentConfigurationRepository(db_path)

    # 4. Verify 0014 is recorded and existing data upgraded
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    applied = {row[0] for row in conn.execute("SELECT version FROM schema_migrations")}
    assert "0014_quality_assessment_configuration.sql" in applied

    # Verify existing tool row got default is_active = 1 from ALTER TABLE
    row = conn.execute("SELECT tool_id, name, is_active FROM quality_assessment_tools WHERE tool_id = 'casp_81'").fetchone()
    assert row is not None
    assert row["tool_id"] == "casp_81"
    assert row["is_active"] == 1
    conn.close()


def test_project_qa_configuration_save_get_and_update(db_path: Path):
    catalog_repo = SqliteQualityAssessmentCatalogRepository(db_path)
    config_repo = SqliteProjectQualityAssessmentConfigurationRepository(db_path)

    tool = QualityAssessmentTool(tool_id="casp_inspired", name="CASP Tool")
    catalog_repo.create_tool(tool)

    tid1 = uuid4()
    tmpl1 = QualityAssessmentTemplate(
        template_id=tid1,
        tool_id="casp_inspired",
        template_key="lean_energy",
        name="Lean Energy QA v1",
        version=1,
    )
    catalog_repo.create_template_version(tmpl1)

    # Save initial configuration
    config1 = ProjectQualityAssessmentConfiguration(
        project_id="proj_100",
        tool_id="casp_inspired",
        template_id=tid1,
    )
    config_repo.save_configuration(config1)

    fetched = config_repo.get_configuration("proj_100")
    assert fetched is not None
    assert fetched.project_id == "proj_100"
    assert fetched.tool_id == "casp_inspired"
    assert fetched.template_id == tid1

    # Save update (v1 -> v2)
    tid2 = uuid4()
    tmpl2 = QualityAssessmentTemplate(
        template_id=tid2,
        tool_id="casp_inspired",
        template_key="lean_energy",
        name="Lean Energy QA v2",
        version=2,
    )
    catalog_repo.create_template_version(tmpl2)

    config2 = ProjectQualityAssessmentConfiguration(
        project_id="proj_100",
        tool_id="casp_inspired",
        template_id=tid2,
        configured_at=config1.configured_at,
    )
    config_repo.save_configuration(config2)

    updated = config_repo.get_configuration("proj_100")
    assert updated is not None
    assert updated.template_id == tid2
    assert updated.configured_at == config1.configured_at


def test_project_qa_configuration_isolation_and_delete(db_path: Path):
    catalog_repo = SqliteQualityAssessmentCatalogRepository(db_path)
    config_repo = SqliteProjectQualityAssessmentConfigurationRepository(db_path)

    tool = QualityAssessmentTool(tool_id="casp_inspired", name="CASP Tool")
    catalog_repo.create_tool(tool)

    tid = uuid4()
    tmpl = QualityAssessmentTemplate(
        template_id=tid,
        tool_id="casp_inspired",
        template_key="lean_energy",
        name="Lean Energy QA v1",
        version=1,
    )
    catalog_repo.create_template_version(tmpl)

    c1 = ProjectQualityAssessmentConfiguration(project_id="proj_A", tool_id="casp_inspired", template_id=tid)
    c2 = ProjectQualityAssessmentConfiguration(project_id="proj_B", tool_id="casp_inspired", template_id=tid)

    config_repo.save_configuration(c1)
    config_repo.save_configuration(c2)

    # Delete proj_A
    config_repo.delete_for_project("proj_A")

    assert config_repo.get_configuration("proj_A") is None
    assert config_repo.get_configuration("proj_B") is not None
    # Catalog elements remain intact
    assert catalog_repo.get_tool("casp_inspired") is not None
