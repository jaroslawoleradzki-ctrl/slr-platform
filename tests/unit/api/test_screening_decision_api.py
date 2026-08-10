
import pytest
from fastapi.testclient import TestClient

from app.api.main import app
from app.api.routers.screening import get_screening_decision_service
from app.domain.publication import Publication
from app.domain.screening import (
    ScreeningCriterion,
    ScreeningCriterionStage,
    ScreeningCriterionType,
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
from app.services.screening_decision_service import ScreeningDecisionService

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
        screening_stage=ScreeningCriterionStage.TITLE_ABSTRACT,
        is_active=True,
        is_required=True,
    )
    service_env.criterion_repo.create(criterion)

    payload = {
        "publication_id": str(pub.record_id),
        "stage": "title_abstract",
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

    # Record decision via POST
    response = client.post(f"/projects/{project_id}/screening/decisions", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["project_id"] == project_id
    assert data["publication_id"] == str(pub.record_id)
    assert data["outcome"] == "include"
    assert data["reviewer_id"] == "reviewer-api"
    decision_id = data["decision_id"]

    # Get latest decision via GET
    latest_resp = client.get(
        f"/projects/{project_id}/screening/decisions/latest",
        params={
            "publication_id": str(pub.record_id),
            "stage": "title_abstract",
            "reviewer_id": "reviewer-api",
        },
    )
    assert latest_resp.status_code == 200
    latest_data = latest_resp.json()
    assert latest_data["decision_id"] == decision_id

    # Get decision by ID via GET
    get_resp = client.get(f"/projects/{project_id}/screening/decisions/{decision_id}")
    assert get_resp.status_code == 200
    get_data = get_resp.json()
    assert get_data["decision_id"] == decision_id
    assert len(get_data["criterion_assessments"]) == 1
    assert get_data["criterion_assessments"][0]["criterion_is_required"] is True


def test_api_list_decision_history(service_env: ScreeningDecisionService) -> None:
    project_id = "lean_energy"
    pub = Publication(title="API History Paper")
    service_env.publication_repo.add_publications(project_id, [pub])

    # Post decision 1
    payload1 = {
        "publication_id": str(pub.record_id),
        "stage": "title_abstract",
        "outcome": "uncertain",
        "reviewer_id": "reviewer-api",
    }
    r1 = client.post(f"/projects/{project_id}/screening/decisions", json=payload1)
    assert r1.status_code == 201

    # Post decision 2
    payload2 = {
        "publication_id": str(pub.record_id),
        "stage": "title_abstract",
        "outcome": "include",
        "reviewer_id": "reviewer-api",
    }
    r2 = client.post(f"/projects/{project_id}/screening/decisions", json=payload2)
    assert r2.status_code == 201

    history_resp = client.get(
        f"/projects/{project_id}/screening/decisions/history",
        params={
            "publication_id": str(pub.record_id),
            "stage": "title_abstract",
            "reviewer_id": "reviewer-api",
        },
    )
    assert history_resp.status_code == 200
    history_data = history_resp.json()
    assert history_data["total"] == 2
    assert history_data["items"][0]["outcome"] == "include"
    assert history_data["items"][1]["outcome"] == "uncertain"
