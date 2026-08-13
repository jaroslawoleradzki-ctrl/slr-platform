from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.main import app
from app.domain.author import Author
from app.domain.project import Project
from app.domain.publication import Publication
from app.domain.quality_assessment import (
    ProjectQualityAssessmentConfiguration,
    QualityAssessmentResponseValue,
    QualityAssessmentTemplate,
    QualityAssessmentTemplateCriterion,
    QualityAssessmentTool,
)
from app.domain.screening import (
    ScreeningDecision,
    ScreeningOutcome,
    ScreeningStage,
)
from app.repositories.project_publication_repository import SqliteProjectPublicationRepository
from app.repositories.project_repository import SqliteProjectRepository
from app.repositories.screening_decision_repository import SqliteScreeningDecisionRepository
from app.repositories.sqlite_quality_assessment_repository import (
    SqliteProjectQualityAssessmentConfigurationRepository,
    SqliteQualityAssessmentCatalogRepository,
    SqliteQualityAssessmentRepository,
)
from app.services.quality_assessment_execution_service import (
    DefaultQualityAssessmentExecutionService,
)


@pytest.fixture
def exec_api_client(tmp_path: Path):
    db_path = tmp_path / "exec_api_test.db"
    project_repo = SqliteProjectRepository(db_path)
    pub_repo = SqliteProjectPublicationRepository(db_path)
    decision_repo = SqliteScreeningDecisionRepository(db_path)
    catalog_repo = SqliteQualityAssessmentCatalogRepository(db_path)
    config_repo = SqliteProjectQualityAssessmentConfigurationRepository(db_path)
    qa_repo = SqliteQualityAssessmentRepository(db_path)

    service = DefaultQualityAssessmentExecutionService(
        project_repo=project_repo,
        publication_repo=pub_repo,
        screening_decision_repo=decision_repo,
        catalog_repo=catalog_repo,
        config_repo=config_repo,
        quality_assessment_repo=qa_repo,
    )

    project_repo.create(Project(project_id="proj_api", title="API Project"))

    pub1 = Publication(record_id=uuid4(), title="Included Paper", authors=[Author(display_name="Author A")])
    pub_repo.add_publications("proj_api", [pub1])

    # Full-text decision INCLUDE
    decision_repo.save(
        ScreeningDecision(
            project_id="proj_api",
            publication_id=pub1.record_id,
            stage=ScreeningStage.FULL_TEXT,
            reviewer_id="rev_1",
            outcome=ScreeningOutcome.INCLUDE,
            rationale="Include",
        )
    )

    # Seed tool & template
    tool = QualityAssessmentTool(tool_id="casp", name="CASP Tool")
    catalog_repo.create_tool(tool)

    tid = uuid4()
    crit1_id = uuid4()
    crit1 = QualityAssessmentTemplateCriterion(
        criterion_id=crit1_id,
        template_id=tid,
        display_order=1,
        question="Did the study address a focused issue?",
        is_required=True,
    )
    tmpl = QualityAssessmentTemplate(
        template_id=tid,
        tool_id="casp",
        template_key="cohort",
        name="CASP Cohort v1",
        version=1,
        criteria=[crit1],
    )
    catalog_repo.create_template_version(tmpl)

    config_repo.save_configuration(
        ProjectQualityAssessmentConfiguration(
            project_id="proj_api",
            tool_id="casp",
            template_id=tid,
        )
    )

    from app.api.routers.quality_assessment import get_execution_service

    app.dependency_overrides[get_execution_service] = lambda: service

    with TestClient(app) as client:
        yield client, pub1.record_id, crit1_id, db_path

    app.dependency_overrides.clear()


def test_quality_assessment_execution_api_flow(exec_api_client):
    client, pub_id, crit_id, _ = exec_api_client

    # 1. GET Overview
    overview_resp = client.get(
        "/api/v1/projects/proj_api/quality-assessment/overview",
        params={"reviewer_id": "rev_1"},
    )
    assert overview_resp.status_code == 200
    overview_data = overview_resp.json()
    assert overview_data["readiness"] == "ready"
    assert overview_data["total_eligible"] == 1
    assert overview_data["total_assessed"] == 0

    # 2. GET Records
    records_resp = client.get(
        "/api/v1/projects/proj_api/quality-assessment/records",
        params={"reviewer_id": "rev_1"},
    )
    assert records_resp.status_code == 200
    records_data = records_resp.json()
    assert records_data["total"] == 1
    assert records_data["items"][0]["has_assessment"] is False

    # 3. GET Record Detail
    detail_resp = client.get(
        f"/api/v1/projects/proj_api/quality-assessment/records/{pub_id}",
        params={"reviewer_id": "rev_1"},
    )
    assert detail_resp.status_code == 200
    detail_data = detail_resp.json()
    assert detail_data["is_currently_eligible"] is True
    assert len(detail_data["template"]["criteria"]) == 1

    # 4. POST Save Assessment
    save_payload = {
        "reviewer_id": "rev_1",
        "publication_id": str(pub_id),
        "responses": [
            {
                "criterion_id": str(crit_id),
                "response_value": QualityAssessmentResponseValue.YES,
                "justification": "Clear methodology",
            }
        ],
    }
    save_resp = client.post(
        "/api/v1/projects/proj_api/quality-assessment/assessments",
        json=save_payload,
    )
    assert save_resp.status_code == 201
    save_data = save_resp.json()
    assert save_data["project_id"] == "proj_api"
    assert len(save_data["responses"]) == 1

    # 5. GET History
    history_resp = client.get(
        f"/api/v1/projects/proj_api/quality-assessment/records/{pub_id}/history",
        params={"reviewer_id": "rev_1"},
    )
    assert history_resp.status_code == 200
    history_data = history_resp.json()
    assert len(history_data) == 1


def test_quality_assessment_execution_api_errors(exec_api_client):
    client, pub_id, crit_id, _ = exec_api_client

    # 1. Missing project -> 404
    resp = client.get(
        "/api/v1/projects/missing_proj/quality-assessment/overview",
        params={"reviewer_id": "rev_1"},
    )
    assert resp.status_code == 404

    # 2. Save for non-eligible reviewer -> 422
    save_payload = {
        "reviewer_id": "rev_unauthorized",
        "publication_id": str(pub_id),
        "responses": [
            {
                "criterion_id": str(crit_id),
                "response_value": QualityAssessmentResponseValue.YES,
                "justification": "Clear methodology",
            }
        ],
    }
    save_resp = client.post(
        "/api/v1/projects/proj_api/quality-assessment/assessments",
        json=save_payload,
    )
    assert save_resp.status_code == 422
