"""Integration tests for Data Extraction Configuration & Eligibility API endpoints (Phase 9.3)."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.main import app
from app.domain.extraction import (
    ExtractionFieldDefinition,
    ExtractionTemplate,
    ExtractionTemplateVersion,
    FieldDataType,
)
from app.domain.publication import Publication
from app.domain.screening import ScreeningDecision, ScreeningOutcome, ScreeningStage
from app.repositories.extraction_template_repository import SqliteExtractionTemplateRepository
from app.repositories.project_publication_repository import SqliteProjectPublicationRepository
from app.repositories.project_repository import Project, SqliteProjectRepository
from app.repositories.screening_decision_repository import SqliteScreeningDecisionRepository


@pytest.fixture
def api_client(tmp_path, monkeypatch):
    test_db = tmp_path / "test_api.db"
    monkeypatch.setenv("SLR_DATABASE_PATH", str(test_db))

    project_repo = SqliteProjectRepository(test_db)
    template_repo = SqliteExtractionTemplateRepository(test_db)
    pub_repo = SqliteProjectPublicationRepository(test_db)
    decision_repo = SqliteScreeningDecisionRepository(test_db)

    # Seed catalog template
    tmpl = ExtractionTemplate(template_id="api_tmpl", name="API Template")
    template_repo.register_template(tmpl)
    ver = ExtractionTemplateVersion(
        template_id="api_tmpl",
        version="1.0.0",
        name="v1",
        is_active=True,
        is_published=True,
        publication_fields=[
            ExtractionFieldDefinition(field_key="field1", name="Field 1", data_type=FieldDataType.TEXT)
        ],
    )
    template_repo.register_version(ver)

    # Seed project & publication
    project_repo.create(Project(project_id="proj_api", title="API Project", description="Test"))
    pub_id = uuid4()
    pub_repo.add_publications("proj_api", [Publication(record_id=pub_id, title="API Pub")])

    decision_repo.save(
        ScreeningDecision(
            project_id="proj_api",
            publication_id=pub_id,
            stage=ScreeningStage.FULL_TEXT,
            reviewer_id="rev_1",
            outcome=ScreeningOutcome.INCLUDE,
        )
    )

    with TestClient(app) as client:
        yield client


class TestExtractionConfigurationAPI:
    def test_get_unconfigured_project_returns_404(self, api_client):
        response = api_client.get("/api/v1/projects/proj_api/extraction/configuration")
        assert response.status_code == 404

    def test_set_and_get_configuration_flow(self, api_client):
        put_resp = api_client.put(
            "/api/v1/projects/proj_api/extraction/configuration",
            json={"template_id": "api_tmpl", "template_version": "1.0.0"},
        )
        assert put_resp.status_code == 200
        data = put_resp.json()
        assert data["project_id"] == "proj_api"
        assert data["template_id"] == "api_tmpl"
        assert data["template_version"] == "1.0.0"

        get_resp = api_client.get("/api/v1/projects/proj_api/extraction/configuration")
        assert get_resp.status_code == 200
        assert get_resp.json()["template_version"] == "1.0.0"

    def test_set_configuration_nonexistent_project_returns_404(self, api_client):
        resp = api_client.put(
            "/api/v1/projects/nonexistent/extraction/configuration",
            json={"template_id": "api_tmpl", "template_version": "1.0.0"},
        )
        assert resp.status_code == 404

    def test_get_eligibility_flow(self, api_client):
        # Configure project first
        api_client.put(
            "/api/v1/projects/proj_api/extraction/configuration",
            json={"template_id": "api_tmpl", "template_version": "1.0.0"},
        )

        resp = api_client.get("/api/v1/projects/proj_api/extraction/eligibility?reviewer_id=rev_1")
        assert resp.status_code == 200
        body = resp.json()
        assert body["project_id"] == "proj_api"
        assert body["total_publications"] == 1
        assert body["eligible_count"] == 1
        assert body["items"][0]["status"] == "eligible"
        assert body["items"][0]["is_eligible"] is True
