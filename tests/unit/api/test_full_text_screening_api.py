from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.api.main import app
from app.api.routers.full_text_screening import get_full_text_screening_service
from app.api.routers.screening import get_screening_decision_service
from app.domain.publication import Publication
from app.domain.screening import (
    ScreeningCriterion,
    ScreeningCriterionStage,
    ScreeningCriterionType,
    ScreeningDecision,
    ScreeningOutcome,
    ScreeningStage,
)
from app.repositories.duplicate_review_decision_repository import InMemoryDuplicateReviewDecisionRepository
from app.repositories.full_text_availability_repository import SqliteFullTextAvailabilityRepository
from app.repositories.project_publication_repository import SqliteProjectPublicationRepository
from app.repositories.screening_criterion_repository import SqliteScreeningCriterionRepository
from app.repositories.screening_decision_repository import SqliteScreeningDecisionRepository
from app.services.full_text_screening_service import FullTextScreeningService
from app.services.screening_decision_service import ScreeningDecisionService
from app.services.screening_input_service import ScreeningInputService


@pytest.fixture
def environment(tmp_path):
    database = tmp_path / "full-text-api.db"
    publications = SqliteProjectPublicationRepository(database)
    criteria = SqliteScreeningCriterionRepository(database)
    decisions = SqliteScreeningDecisionRepository(database)
    decision_service = ScreeningDecisionService(decisions, criteria, publications)
    service = FullTextScreeningService(
        ScreeningInputService(publications, InMemoryDuplicateReviewDecisionRepository()),
        criteria,
        decisions,
        decision_service,
        SqliteFullTextAvailabilityRepository(database),
    )
    app.dependency_overrides[get_full_text_screening_service] = lambda: service
    app.dependency_overrides[get_screening_decision_service] = lambda: decision_service
    yield TestClient(app), publications, criteria, decisions
    app.dependency_overrides.clear()


def _publication() -> Publication:
    return Publication(
        record_id=UUID("00000000-0000-0000-0000-000000000001"),
        title="Paper",
        abstract="Abstract",
    )


def _eligible(decisions, paper) -> None:
    decisions.save(
        ScreeningDecision(
            project_id="lean_energy",
            publication_id=paper.record_id,
            stage=ScreeningStage.TITLE_ABSTRACT,
            outcome=ScreeningOutcome.INCLUDE,
            reviewer_id="alice",
        )
    )


def test_full_text_api_workflow_and_generic_bypass_block(environment) -> None:
    client, publications, criteria, decisions = environment
    paper = _publication()
    publications.add_publications("lean_energy", [paper])
    _eligible(decisions, paper)
    criterion = criteria.create(
        ScreeningCriterion(
            project_id="lean_energy",
            name="Population",
            criterion_type=ScreeningCriterionType.INCLUSION,
            screening_stage=ScreeningCriterionStage.FULL_TEXT,
        )
    )
    assert client.get(
        "/api/v1/projects/lean_energy/screening/full-text", params={"reviewer_id": "alice"}
    ).json()["ready"] is True
    availability = client.put(
        f"/api/v1/projects/lean_energy/screening/full-text/records/{paper.record_id}/availability",
        json={"reviewer_id": "alice", "status": "available", "external_url": "https://example.test/full"},
    )
    assert availability.status_code == 200
    invalid = client.post(
        "/api/v1/projects/lean_energy/screening/full-text/decisions",
        json={"publication_id": str(paper.record_id), "reviewer_id": "alice", "outcome": "exclude", "criterion_assessments": [{"criterion_id": str(criterion.criterion_id), "assessment_value": "not_met"}]},
    )
    assert invalid.status_code == 422
    saved = client.post(
        "/api/v1/projects/lean_energy/screening/full-text/decisions",
        json={"publication_id": str(paper.record_id), "reviewer_id": "alice", "outcome": "exclude", "criterion_assessments": [{"criterion_id": str(criterion.criterion_id), "assessment_value": "not_met"}], "exclusion_reason_criterion_ids": [str(criterion.criterion_id)]},
    )
    assert saved.status_code == 201
    assert saved.json()["exclusion_reason_criterion_ids"] == [str(criterion.criterion_id)]
    generic = client.post(
        "/api/v1/projects/lean_energy/screening/decisions",
        json={"publication_id": str(paper.record_id), "reviewer_id": "alice", "stage": "full_text", "outcome": "include"},
    )
    assert generic.status_code == 409
    assert generic.json()["detail"]["code"] == "full_text_workflow_required"


def test_other_reviewer_is_not_eligible(environment) -> None:
    client, publications, _, decisions = environment
    paper = _publication()
    publications.add_publications("lean_energy", [paper])
    decisions.save(ScreeningDecision(project_id="lean_energy", publication_id=paper.record_id, stage=ScreeningStage.TITLE_ABSTRACT, outcome=ScreeningOutcome.INCLUDE, reviewer_id="bob"))
    response = client.get("/api/v1/projects/lean_energy/screening/full-text", params={"reviewer_id": "alice"})
    assert response.status_code == 200
    assert response.json()["readiness_status"] == "waiting_for_title_abstract"
