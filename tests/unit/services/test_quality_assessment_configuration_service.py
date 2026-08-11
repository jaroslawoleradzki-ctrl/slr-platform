from pathlib import Path
from uuid import uuid4

import pytest

from app.domain.project import Project
from app.domain.quality_assessment import (
    QualityAssessmentTemplate,
    QualityAssessmentTool,
)
from app.repositories.project_repository import ProjectNotFoundError, SqliteProjectRepository
from app.repositories.sqlite_quality_assessment_repository import (
    SqliteProjectQualityAssessmentConfigurationRepository,
    SqliteQualityAssessmentCatalogRepository,
)
from app.services.quality_assessment_configuration_service import (
    CASP_INSPIRED_TOOL_ID,
    CrossToolTemplateMismatchError,
    DefaultQualityAssessmentConfigurationService,
    InactiveTemplateSelectionError,
    InactiveToolSelectionError,
    SeedCatalogConflictError,
    TemplateVersionNotFoundError,
    ToolNotFoundError,
)


@pytest.fixture
def service_env(tmp_path: Path):
    db_path = tmp_path / "service_test.db"
    catalog_repo = SqliteQualityAssessmentCatalogRepository(db_path)
    config_repo = SqliteProjectQualityAssessmentConfigurationRepository(db_path)
    project_repo = SqliteProjectRepository(db_path)
    service = DefaultQualityAssessmentConfigurationService(
        catalog_repo=catalog_repo,
        config_repo=config_repo,
        project_repo=project_repo,
    )
    return service, catalog_repo, config_repo, project_repo


def test_seed_built_in_catalog_idempotency_and_conflict(service_env):
    service, catalog_repo, _, _ = service_env

    # 1. First seed creates tool
    service.seed_built_in_catalog()
    tool = service.get_tool(CASP_INSPIRED_TOOL_ID)
    assert tool.name == "CASP-inspired Quality Assessment"

    # 2. Second seed is idempotent
    service.seed_built_in_catalog()

    # 3. Conflict detection if name changes
    _ = QualityAssessmentTool(
        tool_id=CASP_INSPIRED_TOOL_ID,
        name="Conflicting Name Tool",
    )
    # Manually insert conflicting tool into DB
    conn = catalog_repo._get_connection()
    conn.execute(
        "UPDATE quality_assessment_tools SET name = ? WHERE tool_id = ?",
        ("Conflicting Name Tool", CASP_INSPIRED_TOOL_ID),
    )
    conn.commit()
    conn.close()

    with pytest.raises(SeedCatalogConflictError, match="conflicts with seed tool name"):
        service.seed_built_in_catalog()


def test_configure_project_validations_and_cross_tool_mismatch(service_env):
    service, catalog_repo, _, project_repo = service_env
    service.seed_built_in_catalog()

    # Create dummy project
    project_repo.create(Project(project_id="lean_energy", title="Lean Energy"))

    # Tool A and Tool B
    tool_b = QualityAssessmentTool(tool_id="jbi_tool", name="JBI Tool")
    catalog_repo.create_tool(tool_b)

    tid_a = uuid4()
    tmpl_a = QualityAssessmentTemplate(
        template_id=tid_a,
        tool_id=CASP_INSPIRED_TOOL_ID,
        template_key="test_template_a",
        name="Template A v1",
        version=1,
    )
    catalog_repo.create_template_version(tmpl_a)

    tid_b = uuid4()
    tmpl_b = QualityAssessmentTemplate(
        template_id=tid_b,
        tool_id="jbi_tool",
        template_key="test_template_b",
        name="Template B v1",
        version=1,
    )
    catalog_repo.create_template_version(tmpl_b)

    # 1. Missing project
    with pytest.raises(ProjectNotFoundError):
        service.configure_project("missing_proj", CASP_INSPIRED_TOOL_ID, tid_a)

    # 2. Missing tool
    with pytest.raises(ToolNotFoundError):
        service.configure_project("lean_energy", "missing_tool", tid_a)

    # 3. Missing template
    with pytest.raises(TemplateVersionNotFoundError):
        service.configure_project("lean_energy", CASP_INSPIRED_TOOL_ID, uuid4())

    # 4. Cross-tool mismatch: Selected Tool B, but template belongs to Tool A
    with pytest.raises(CrossToolTemplateMismatchError):
        service.configure_project("lean_energy", "jbi_tool", tid_a)

    # 5. Valid configuration
    config = service.configure_project("lean_energy", CASP_INSPIRED_TOOL_ID, tid_a)
    assert config.project_id == "lean_energy"
    assert config.tool_id == CASP_INSPIRED_TOOL_ID
    assert config.template_id == tid_a


def test_configure_project_inactive_tool_and_template_rejection(service_env):
    service, catalog_repo, _, project_repo = service_env
    project_repo.create(Project(project_id="proj_100", title="Project 100"))

    inactive_tool = QualityAssessmentTool(tool_id="inactive_tool", name="Inactive Tool", is_active=False)
    catalog_repo.create_tool(inactive_tool)

    active_tool = QualityAssessmentTool(tool_id="active_tool", name="Active Tool", is_active=True)
    catalog_repo.create_tool(active_tool)

    tid_inactive = uuid4()
    tmpl_inactive = QualityAssessmentTemplate(
        template_id=tid_inactive,
        tool_id="active_tool",
        template_key="key",
        name="Inactive Tmpl",
        version=1,
        is_active=False,
    )
    catalog_repo.create_template_version(tmpl_inactive)

    tid_for_inactive_tool = uuid4()
    tmpl_for_inactive_tool = QualityAssessmentTemplate(
        template_id=tid_for_inactive_tool,
        tool_id="inactive_tool",
        template_key="key_in",
        name="Tmpl Inactive Tool",
        version=1,
        is_active=True,
    )
    catalog_repo.create_template_version(tmpl_for_inactive_tool)

    tid_active = uuid4()
    tmpl_active = QualityAssessmentTemplate(
        template_id=tid_active,
        tool_id="active_tool",
        template_key="key2",
        name="Active Tmpl",
        version=2,
        is_active=True,
    )
    catalog_repo.create_template_version(tmpl_active)

    # Attempting to configure inactive tool -> Rejected
    with pytest.raises(InactiveToolSelectionError):
        service.configure_project("proj_100", "inactive_tool", tid_for_inactive_tool)

    # Attempting to configure inactive template -> Rejected
    with pytest.raises(InactiveTemplateSelectionError):
        service.configure_project("proj_100", "active_tool", tid_inactive)

    # Valid active selection -> Success
    config = service.configure_project("proj_100", "active_tool", tid_active)
    assert config.template_id == tid_active

    # Existing configuration with inactive tool/template remains readable!
    catalog_repo.set_template_version_active(tid_active, False)
    fetched_config = service.get_project_configuration("proj_100")
    assert fetched_config is not None
    assert fetched_config.template_id == tid_active
