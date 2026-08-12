"""Unit tests for ExtractionConfigurationService (Phase 9.3)."""

from uuid import uuid4

import pytest

from app.domain.extraction import (
    ExtractionConfigurationLockedError,
    ExtractionFieldDefinition,
    ExtractionRecord,
    ExtractionTemplate,
    ExtractionTemplateVersion,
    FieldDataType,
)
from app.repositories.extraction_repository import (
    SqliteExtractionRepository,
)
from app.repositories.extraction_template_repository import (
    ExtractionTemplateNotFoundError,
    SqliteExtractionTemplateRepository,
)
from app.repositories.project_repository import (
    Project,
    ProjectNotFoundError,
    SqliteProjectRepository,
)
from app.services.extraction_configuration_service import (
    ExtractionConfigurationService,
)
from app.services.project_deletion_service import (
    SqliteProjectDeletionService,
)


@pytest.fixture
def temp_db(tmp_path):
    return tmp_path / "test_slr.db"


@pytest.fixture
def project_repo(temp_db):
    return SqliteProjectRepository(temp_db)


@pytest.fixture
def template_repo(temp_db):
    return SqliteExtractionTemplateRepository(temp_db)


@pytest.fixture
def extraction_repo(temp_db):
    return SqliteExtractionRepository(temp_db)


@pytest.fixture
def config_service(extraction_repo, template_repo, project_repo):
    return ExtractionConfigurationService(
        extraction_repo=extraction_repo,
        template_repo=template_repo,
        project_repo=project_repo,
    )


@pytest.fixture
def active_published_version(template_repo):
    tmpl = ExtractionTemplate(template_id="gen_tmpl", name="Generic Template")
    template_repo.register_template(tmpl)

    fdef = ExtractionFieldDefinition(
        field_key="sample_val", name="Sample", data_type=FieldDataType.TEXT
    )
    ver = ExtractionTemplateVersion(
        template_id="gen_tmpl",
        version="1.0.0",
        name="v1",
        is_active=True,
        is_published=True,
        publication_fields=[fdef],
    )
    template_repo.register_version(ver)

    ver2 = ExtractionTemplateVersion(
        template_id="gen_tmpl",
        version="2.0.0",
        name="v2",
        is_active=True,
        is_published=True,
        publication_fields=[fdef],
    )
    template_repo.register_version(ver2)
    return ver


@pytest.fixture
def sample_project(project_repo):
    p = Project(project_id="proj_101", title="Project 101", description="Test")
    project_repo.create(p)
    return p


class TestExtractionConfigurationService:
    def test_no_config_returns_none(self, config_service, sample_project):
        assert config_service.get_configuration(sample_project.project_id) is None

    def test_set_and_get_valid_configuration(
        self, config_service, sample_project, active_published_version
    ):
        config = config_service.set_configuration("proj_101", "gen_tmpl", "1.0.0")
        assert config.project_id == "proj_101"
        assert config.template_id == "gen_tmpl"
        assert config.template_version == "1.0.0"

        fetched = config_service.get_configuration("proj_101")
        assert fetched is not None
        assert fetched.template_id == "gen_tmpl"
        assert fetched.template_version == "1.0.0"

    def test_nonexistent_project_raises_not_found(self, config_service, active_published_version):
        with pytest.raises(ProjectNotFoundError):
            config_service.set_configuration("nonexistent_proj", "gen_tmpl", "1.0.0")

    def test_nonexistent_template_or_version_raises_error(
        self, config_service, sample_project, active_published_version
    ):
        with pytest.raises(ExtractionTemplateNotFoundError):
            config_service.set_configuration("proj_101", "unknown_tmpl", "1.0.0")

        with pytest.raises(ExtractionTemplateNotFoundError):
            config_service.set_configuration("proj_101", "gen_tmpl", "9.9.9")

    def test_unpublished_or_inactive_version_raises_value_error(
        self, config_service, sample_project, template_repo
    ):
        tmpl = ExtractionTemplate(template_id="draft_tmpl", name="Draft Template")
        template_repo.register_template(tmpl)
        ver_draft = ExtractionTemplateVersion(
            template_id="draft_tmpl",
            version="1.0.0",
            name="Draft v1",
            is_active=True,
            is_published=False,  # Not published!
        )
        template_repo.register_version(ver_draft)

        with pytest.raises(ValueError, match="is not active and published"):
            config_service.set_configuration("proj_101", "draft_tmpl", "1.0.0")

    def test_update_config_before_records_exist_succeeds(
        self, config_service, sample_project, active_published_version
    ):
        config_service.set_configuration("proj_101", "gen_tmpl", "1.0.0")
        updated = config_service.set_configuration("proj_101", "gen_tmpl", "2.0.0")
        assert updated.template_version == "2.0.0"

    def test_change_config_locked_after_extraction_records_exist(
        self, config_service, extraction_repo, sample_project, active_published_version
    ):
        config_service.set_configuration("proj_101", "gen_tmpl", "1.0.0")

        rec = ExtractionRecord(
            project_id="proj_101",
            publication_id=uuid4(),
            template_id="gen_tmpl",
            template_version="1.0.0",
        )
        extraction_repo.create_record(rec)

        with pytest.raises(
            ExtractionConfigurationLockedError,
            match="Cannot change extraction configuration for project 'proj_101'",
        ):
            config_service.set_configuration("proj_101", "gen_tmpl", "2.0.0")

    def test_project_isolation(
        self, config_service, project_repo, active_published_version
    ):
        p1 = Project(project_id="proj_A", title="Project A", description="Test")
        p2 = Project(project_id="proj_B", title="Project B", description="Test")
        project_repo.create(p1)
        project_repo.create(p2)

        config_service.set_configuration("proj_A", "gen_tmpl", "1.0.0")
        assert config_service.get_configuration("proj_A").template_version == "1.0.0"
        assert config_service.get_configuration("proj_B") is None

    def test_project_hard_delete_cleans_configuration(
        self, temp_db, config_service, project_repo, active_published_version
    ):
        p1 = Project(project_id="proj_del", title="Delete Me", description="Test")
        project_repo.create(p1)
        config_service.set_configuration("proj_del", "gen_tmpl", "1.0.0")

        deletion_service = SqliteProjectDeletionService(project_repo=project_repo)
        deletion_service.delete_project("proj_del")

        assert config_service.get_configuration("proj_del") is None
        # Global templates survive project deletion
        template_repo = SqliteExtractionTemplateRepository(temp_db)
        assert template_repo.get_version("gen_tmpl", "1.0.0") is not None
