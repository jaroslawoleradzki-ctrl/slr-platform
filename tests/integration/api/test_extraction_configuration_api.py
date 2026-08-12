"""Integration tests for Data Extraction Configuration & Eligibility API endpoints (Phase 9.3)."""

from uuid import UUID, uuid4

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
from app.domain.quality_assessment import (
    ProjectQualityAssessmentConfiguration,
    QualityAssessment,
    QualityAssessmentResponse,
    QualityAssessmentResponseValue,
    QualityAssessmentTemplate,
    QualityAssessmentTemplateCriterion,
    QualityAssessmentTool,
)
from app.domain.screening import ScreeningDecision, ScreeningOutcome, ScreeningStage
from app.repositories.extraction_template_repository import SqliteExtractionTemplateRepository
from app.repositories.project_publication_repository import SqliteProjectPublicationRepository
from app.repositories.project_repository import Project, SqliteProjectRepository
from app.repositories.screening_decision_repository import SqliteScreeningDecisionRepository
from app.repositories.sqlite_quality_assessment_repository import (
    SqliteProjectQualityAssessmentConfigurationRepository,
    SqliteQualityAssessmentCatalogRepository,
    SqliteQualityAssessmentRepository,
)

PUBLICATION_ID = UUID("00000000-0000-4000-8000-000000000093")
QA_TEMPLATE_ID = UUID("00000000-0000-4000-8000-000000000094")
QA_CRITERION_ID = UUID("00000000-0000-4000-8000-000000000095")


@pytest.fixture
def api_context(tmp_path, monkeypatch):
    test_db = tmp_path / "slr_platform.db"
    monkeypatch.chdir(tmp_path)
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
    pub_repo.add_publications(
        "proj_api", [Publication(record_id=PUBLICATION_ID, title="API Pub")]
    )

    decision_repo.save(
        ScreeningDecision(
            project_id="proj_api",
            publication_id=PUBLICATION_ID,
            stage=ScreeningStage.FULL_TEXT,
            reviewer_id="rev_1",
            outcome=ScreeningOutcome.INCLUDE,
        )
    )

    qa_catalog = SqliteQualityAssessmentCatalogRepository(test_db)
    qa_catalog.create_tool(QualityAssessmentTool(tool_id="api-qa", name="API QA"))
    qa_catalog.create_template_version(
        QualityAssessmentTemplate(
            template_id=QA_TEMPLATE_ID,
            tool_id="api-qa",
            template_key="api-qa-v1",
            name="API QA v1",
            version=1,
            criteria=[
                QualityAssessmentTemplateCriterion(
                    criterion_id=QA_CRITERION_ID,
                    template_id=QA_TEMPLATE_ID,
                    question="Is the study methodologically complete?",
                )
            ],
        )
    )

    with TestClient(app) as client:
        yield {"client": client, "db_path": test_db}


@pytest.fixture
def api_client(api_context):
    return api_context["client"]


def _configure_qa(db_path):
    SqliteProjectQualityAssessmentConfigurationRepository(db_path).save_configuration(
        ProjectQualityAssessmentConfiguration(
            project_id="proj_api", tool_id="api-qa", template_id=QA_TEMPLATE_ID
        )
    )


def _save_qa_assessment(db_path, response_value: QualityAssessmentResponseValue):
    assessment_id = uuid4()
    SqliteQualityAssessmentRepository(db_path).save_assessment(
        QualityAssessment(
            assessment_id=assessment_id,
            project_id="proj_api",
            publication_id=PUBLICATION_ID,
            reviewer_id="rev_1",
            template_id=QA_TEMPLATE_ID,
            responses=[
                QualityAssessmentResponse(
                    assessment_id=assessment_id,
                    criterion_id=QA_CRITERION_ID,
                    question_snapshot="Is the study methodologically complete?",
                    response_value=response_value,
                    justification="Recorded QA response",
                )
            ],
        )
    )


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

    def test_real_api_wiring_blocks_configured_qa_without_assessment(self, api_context):
        client = api_context["client"]
        client.put(
            "/api/v1/projects/proj_api/extraction/configuration",
            json={"template_id": "api_tmpl", "template_version": "1.0.0"},
        )
        _configure_qa(api_context["db_path"])

        response = client.get(
            "/api/v1/projects/proj_api/extraction/eligibility",
            params={"reviewer_id": "rev_1"},
        )

        assert response.status_code == 200
        assert response.json()["eligible_count"] == 0
        assert response.json()["items"][0]["status"] == "blocked_qa_incomplete"

    @pytest.mark.parametrize("response_value", list(QualityAssessmentResponseValue))
    def test_real_api_wiring_treats_all_qa_response_values_as_completion(
        self, api_context, response_value
    ):
        client = api_context["client"]
        client.put(
            "/api/v1/projects/proj_api/extraction/configuration",
            json={"template_id": "api_tmpl", "template_version": "1.0.0"},
        )
        _configure_qa(api_context["db_path"])
        _save_qa_assessment(api_context["db_path"], response_value)

        response = client.get(
            "/api/v1/projects/proj_api/extraction/eligibility",
            params={"reviewer_id": "rev_1"},
        )

        assert response.status_code == 200
        assert response.json()["eligible_count"] == 1
        assert response.json()["items"][0]["status"] == "eligible"

    def test_real_api_wiring_is_reviewer_scoped(self, api_context):
        client = api_context["client"]
        client.put(
            "/api/v1/projects/proj_api/extraction/configuration",
            json={"template_id": "api_tmpl", "template_version": "1.0.0"},
        )
        _configure_qa(api_context["db_path"])
        _save_qa_assessment(api_context["db_path"], QualityAssessmentResponseValue.YES)
        SqliteScreeningDecisionRepository(api_context["db_path"]).save(
            ScreeningDecision(
                project_id="proj_api",
                publication_id=PUBLICATION_ID,
                stage=ScreeningStage.FULL_TEXT,
                reviewer_id="rev_2",
                outcome=ScreeningOutcome.INCLUDE,
            )
        )

        response = client.get(
            "/api/v1/projects/proj_api/extraction/eligibility",
            params={"reviewer_id": "rev_2"},
        )

        assert response.status_code == 200
        assert response.json()["eligible_count"] == 0

    def test_eligibility_requires_reviewer_identity(self, api_client):
        response = api_client.get("/api/v1/projects/proj_api/extraction/eligibility")
        assert response.status_code == 422
