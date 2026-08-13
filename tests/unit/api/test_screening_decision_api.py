import pytest
from fastapi.testclient import TestClient

from app.api.main import app
from app.api.routers.screening import get_screening_decision_service
from app.domain.publication import Publication
from app.domain.screening import (
    CriterionAssessmentValue,
    ScreeningCriterion,
    ScreeningCriterionStage,
    ScreeningCriterionType,
    ScreeningDecision,
    ScreeningOutcome,
    ScreeningStage,
)
from app.repositories.project_publication_repository import (
    SqliteProjectPublicationRepository,
)
from app.repositories.screening_criterion_repository import (
    SqliteScreeningCriterionRepository,
)
from app.repositories.screening_decision_repository import (
    SqliteScreeningDecisionRepository,
)
from app.services.screening_decision_service import CriterionAssessmentInput, ScreeningDecisionService

client = TestClient(app)


@pytest.fixture
def service_env(tmp_path):
    db_path = tmp_path / "test_api.db"
    pub_repo = SqliteProjectPublicationRepository(db_path)
    crit_repo = SqliteScreeningCriterionRepository(db_path)
    dec_repo = SqliteScreeningDecisionRepository(db_path)
    srv = ScreeningDecisionService(dec_repo, crit_repo, pub_repo)

    def _override():
        return srv

    app.dependency_overrides[get_screening_decision_service] = _override
    yield srv
    app.dependency_overrides.clear()


def test_api_record_and_get_screening_decision(service_env: ScreeningDecisionService) -> None:
    project_id = "lean_energy"
    pub = Publication(title="API Test Paper")
    service_env.publication_repo.add_publications(project_id, [pub])

    criterion = ScreeningCriterion(
        project_id=project_id,
        name="API Criterion",
        criterion_type=ScreeningCriterionType.INCLUSION,
        screening_stage=ScreeningCriterionStage.FULL_TEXT,
        is_active=True,
        is_required=True,
    )
    service_env.criterion_repo.create(criterion)

    payload = {
        "publication_id": str(pub.record_id),
        "stage": "full_text",
        "outcome": "include",
        "reviewer_id": "reviewer-api",
        "rationale": "High quality paper",
        "criterion_assessments": [
            {
                "criterion_id": str(criterion.criterion_id),
                "assessment_value": "met",
                "notes": "Met during API call",
            }
        ],
    }

    # Generic public writes must not bypass the dedicated Full Text workflow.
    response = client.post(f"/api/v1/projects/{project_id}/screening/decisions", json=payload)
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "full_text_workflow_required"

    # Generic reads remain supported for immutable decision history.
    saved = service_env.record_decision(
        project_id, pub.record_id, ScreeningStage.FULL_TEXT, ScreeningOutcome.INCLUDE, "reviewer-api",
        "High quality paper",
        [
            CriterionAssessmentInput(
                criterion_id=criterion.criterion_id,
                assessment_value=CriterionAssessmentValue.MET,
                notes="Met during API call",
            )
        ],
    )
    decision_id = str(saved.decision_id)

    # Get latest decision via GET
    latest_resp = client.get(
        f"/api/v1/projects/{project_id}/screening/decisions/latest",
        params={
            "publication_id": str(pub.record_id),
            "stage": "full_text",
            "reviewer_id": "reviewer-api",
        },
    )
    assert latest_resp.status_code == 200
    latest_data = latest_resp.json()
    assert latest_data["decision_id"] == decision_id

    # Get decision by ID via GET
    get_resp = client.get(f"/api/v1/projects/{project_id}/screening/decisions/{decision_id}")
    assert get_resp.status_code == 200
    get_data = get_resp.json()
    assert get_data["decision_id"] == decision_id
    assert len(get_data["criterion_assessments"]) == 1
    assert get_data["criterion_assessments"][0]["criterion_is_required"] is True


def test_api_list_decision_history(service_env: ScreeningDecisionService) -> None:
    project_id = "lean_energy"
    pub = Publication(title="API History Paper")
    service_env.publication_repo.add_publications(project_id, [pub])

    # Full Text history is append-only; writes are tested through the dedicated
    # workflow, while this generic endpoint remains its public read surface.
    service_env.decision_repo.save(
        ScreeningDecision(
            project_id=project_id, publication_id=pub.record_id, stage=ScreeningStage.FULL_TEXT,
            outcome=ScreeningOutcome.UNCERTAIN, reviewer_id="reviewer-api"
        )
    )
    service_env.decision_repo.save(
        ScreeningDecision(
            project_id=project_id, publication_id=pub.record_id, stage=ScreeningStage.FULL_TEXT,
            outcome=ScreeningOutcome.INCLUDE, reviewer_id="reviewer-api"
        )
    )

    history_resp = client.get(
        f"/api/v1/projects/{project_id}/screening/decisions/history",
        params={
            "publication_id": str(pub.record_id),
            "stage": "full_text",
            "reviewer_id": "reviewer-api",
        },
    )
    assert history_resp.status_code == 200
    history_data = history_resp.json()
    assert history_data["total"] == 2
    assert history_data["items"][0]["outcome"] == "include"
    assert history_data["items"][1]["outcome"] == "uncertain"
