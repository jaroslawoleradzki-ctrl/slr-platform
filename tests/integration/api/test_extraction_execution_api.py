"""Integration tests for Data Extraction Execution API endpoints (Phase 9.4)."""

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
from app.services.extraction_configuration_service import ExtractionConfigurationService


@pytest.fixture
def api_client(tmp_path, monkeypatch):
    test_db = tmp_path / "test_execution_api.db"
    monkeypatch.setenv("SLR_DATABASE_PATH", str(test_db))

    project_repo = SqliteProjectRepository(test_db)
    template_repo = SqliteExtractionTemplateRepository(test_db)
    pub_repo = SqliteProjectPublicationRepository(test_db)
    decision_repo = SqliteScreeningDecisionRepository(test_db)
    config_service = ExtractionConfigurationService(template_repo=template_repo, project_repo=project_repo)

    # Seed template
    tmpl = ExtractionTemplate(template_id="api_exec_tmpl", name="API Exec Template")
    template_repo.register_template(tmpl)
    ver = ExtractionTemplateVersion(
        template_id="api_exec_tmpl",
        version="1.0.0",
        name="v1",
        is_active=True,
        is_published=True,
        publication_fields=[
            ExtractionFieldDefinition(
                field_key="sample_text", name="Sample", data_type=FieldDataType.TEXT, is_required=True
            )
        ],
    )
    template_repo.register_version(ver)

    # Seed project & configure
    project_repo.create(Project(project_id="proj_api_exec", title="API Exec Project", description="Test"))
    config_service.set_configuration("proj_api_exec", "api_exec_tmpl", "1.0.0")

    # Seed eligible publication
    pub_id = uuid4()
    pub_repo.add_publications("proj_api_exec", [Publication(record_id=pub_id, title="API Pub")])
    decision_repo.save(
        ScreeningDecision(
            project_id="proj_api_exec",
            publication_id=pub_id,
            stage=ScreeningStage.FULL_TEXT,
            reviewer_id="rev_1",
            outcome=ScreeningOutcome.INCLUDE,
        )
    )

    # Seed ineligible publication
    ineligible_pub_id = uuid4()
    pub_repo.add_publications("proj_api_exec", [Publication(record_id=ineligible_pub_id, title="API Ineligible Pub")])
    decision_repo.save(
        ScreeningDecision(
            project_id="proj_api_exec",
            publication_id=ineligible_pub_id,
            stage=ScreeningStage.FULL_TEXT,
            reviewer_id="rev_1",
            outcome=ScreeningOutcome.EXCLUDE,
        )
    )

    with TestClient(app) as client:
        yield {
            "client": client,
            "project_id": "proj_api_exec",
            "publication_id": pub_id,
            "ineligible_publication_id": ineligible_pub_id,
        }


class TestExtractionExecutionAPI:
    def test_get_nonexistent_record_returns_404(self, api_client):
        client = api_client["client"]
        resp = client.get(f"/api/v1/projects/{api_client['project_id']}/extraction/records/{uuid4()}")
        assert resp.status_code == 404

    def test_submit_revision_flow_and_retrieve_latest_and_history(self, api_client):
        client = api_client["client"]
        project_id = api_client["project_id"]
        pub_id = api_client["publication_id"]

        # POST initial revision
        payload1 = {
            "reviewer_id": "rev_1",
            "publication_values": [
                {
                    "field_key": "sample_text",
                    "status": "present",
                    "origin": "reported",
                    "text_value": "First Text",
                    "source_page": "p. 5",
                }
            ],
            "group_items": [],
            "mark_complete": True,
        }
        post_resp1 = client.post(
            f"/api/v1/projects/{project_id}/extraction/records/{pub_id}/revisions",
            json=payload1,
        )
        assert post_resp1.status_code == 201
        rev1_data = post_resp1.json()
        assert rev1_data["revision_index"] == 1
        assert rev1_data["completeness_status"] == "complete"
        assert rev1_data["publication_values"][0]["text_value"] == "First Text"

        # GET record
        rec_resp = client.get(f"/api/v1/projects/{project_id}/extraction/records/{pub_id}")
        assert rec_resp.status_code == 200
        rec_data = rec_resp.json()
        assert rec_data["current_status"] == "complete"
        assert rec_data["latest_revision"]["revision_index"] == 1

        # POST second revision
        payload2 = {
            "reviewer_id": "rev_1",
            "publication_values": [
                {
                    "field_key": "sample_text",
                    "status": "present",
                    "origin": "reviewer_coded",
                    "text_value": "Second Text",
                    "source_page": "p. 6",
                }
            ],
            "group_items": [],
            "mark_complete": True,
        }
        post_resp2 = client.post(
            f"/api/v1/projects/{project_id}/extraction/records/{pub_id}/revisions",
            json=payload2,
        )
        assert post_resp2.status_code == 201
        rev2_data = post_resp2.json()
        assert rev2_data["revision_index"] == 2
        assert rev2_data["reviewer_id"] == "rev_1"

        # GET history
        hist_resp = client.get(f"/api/v1/projects/{project_id}/extraction/records/{pub_id}/history")
        assert hist_resp.status_code == 200
        hist_data = hist_resp.json()
        assert hist_data["total_revisions"] == 2
        assert hist_data["revisions"][0]["revision_index"] == 1
        assert hist_data["revisions"][1]["revision_index"] == 2

    def test_ineligible_publication_post_returns_409(self, api_client):
        client = api_client["client"]
        project_id = api_client["project_id"]
        pub_id = api_client["ineligible_publication_id"]

        payload = {
            "reviewer_id": "rev_1",
            "publication_values": [
                {
                    "field_key": "sample_text",
                    "status": "present",
                    "origin": "reported",
                    "text_value": "Some Text",
                }
            ],
            "group_items": [],
        }
        resp = client.post(
            f"/api/v1/projects/{project_id}/extraction/records/{pub_id}/revisions",
            json=payload,
        )
        assert resp.status_code == 409

    def test_validation_error_returns_422(self, api_client):
        client = api_client["client"]
        project_id = api_client["project_id"]
        pub_id = api_client["publication_id"]

        # Request mark_complete=True without required publication field
        payload = {
            "reviewer_id": "rev_1",
            "publication_values": [],
            "group_items": [],
            "mark_complete": True,
        }
        resp = client.post(
            f"/api/v1/projects/{project_id}/extraction/records/{pub_id}/revisions",
            json=payload,
        )
        assert resp.status_code == 422
