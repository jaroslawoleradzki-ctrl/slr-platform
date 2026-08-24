from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.main import app
from app.api.routers.screening import (
    get_screening_decision_service,
    get_title_abstract_screening_service,
)
from app.domain.duplicate_review import DuplicateDecision, DuplicateGroupReviewDecision
from app.domain.identifiers import Identifier, IdentifierType
from app.domain.publication import Publication
from app.domain.screening import ScreeningCriterion, ScreeningCriterionStage, ScreeningCriterionType
from app.repositories.duplicate_review_decision_repository import InMemoryDuplicateReviewDecisionRepository
from app.repositories.project_publication_repository import SqliteProjectPublicationRepository
from app.repositories.screening_criterion_repository import SqliteScreeningCriterionRepository
from app.repositories.screening_decision_repository import SqliteScreeningDecisionRepository
from app.services.duplicate_group_builder import DuplicateGroupBuilder
from app.services.screening_decision_service import ScreeningDecisionService
from app.services.screening_input_service import ScreeningInputService
from app.services.title_abstract_screening_service import TitleAbstractScreeningService


@pytest.fixture
def environment(tmp_path):
    database = tmp_path / "api.db"
    publications = SqliteProjectPublicationRepository(database)
    criteria = SqliteScreeningCriterionRepository(database)
    decisions = SqliteScreeningDecisionRepository(database)
    reviews = InMemoryDuplicateReviewDecisionRepository()
    decision_service = ScreeningDecisionService(decisions, criteria, publications)
    service = TitleAbstractScreeningService(
        ScreeningInputService(publications, reviews),
        criteria,
        decisions,
        decision_service,
    )
    app.dependency_overrides[get_title_abstract_screening_service] = lambda: service
    app.dependency_overrides[get_screening_decision_service] = lambda: decision_service
    yield TestClient(app), publications, criteria, decisions, reviews
    app.dependency_overrides.clear()


def _publication(number: int, doi: str | None = None) -> Publication:
    return Publication(
        record_id=UUID(f"00000000-0000-0000-0000-{number:012d}"),
        title=f"Paper {number}",
        abstract=f"Abstract {number}",
        publication_year=2024,
        identifiers=[] if doi is None else [Identifier(type=IdentifierType.DOI, value=doi)],
    )


def test_overview_records_get_pagination_and_filter(environment) -> None:
    client, publications, criteria, *_ = environment
    records = [_publication(2), _publication(1)]
    publications.add_publications("lean_energy", records)
    visible = criteria.create(
        ScreeningCriterion(
            project_id="lean_energy",
            name="Visible",
            criterion_type=ScreeningCriterionType.INCLUSION,
            screening_stage=ScreeningCriterionStage.TITLE_ABSTRACT,
        )
    )
    criteria.create(
        ScreeningCriterion(
            project_id="lean_energy",
            name="Hidden",
            criterion_type=ScreeningCriterionType.EXCLUSION,
            screening_stage=ScreeningCriterionStage.FULL_TEXT,
        )
    )

    overview = client.get("/api/v1/projects/lean_energy/screening/title-abstract", params={"reviewer_id": "alice"})
    assert overview.status_code == 200
    assert overview.json()["progress"] == {
        "total": 2,
        "unscreened": 2,
        "included": 0,
        "excluded": 0,
        "uncertain": 0,
        "completed": 0,
    }
    assert [item["criterion_id"] for item in overview.json()["criteria"]] == [str(visible.criterion_id)]
    page = client.get(
        "/api/v1/projects/lean_energy/screening/title-abstract/records",
        params={"reviewer_id": "alice", "status": "unscreened", "offset": 1, "limit": 1},
    )
    assert page.status_code == 200 and page.json()["total"] == 2
    assert page.json()["items"][0]["publication_id"] == str(records[0].record_id)
    detail = client.get(
        f"/api/v1/projects/lean_energy/screening/title-abstract/records/{records[1].record_id}",
        params={"reviewer_id": "alice"},
    )
    assert detail.status_code == 200 and detail.json()["abstract"] == "Abstract 1"


@pytest.mark.parametrize(
    "outcome,status_value", [("include", "included"), ("exclude", "excluded"), ("uncertain", "uncertain")]
)
def test_post_decision_forces_title_abstract_and_updates_latest(environment, outcome, status_value) -> None:
    client, publications, *_ = environment
    publication = _publication(1)
    publications.add_publications("lean_energy", [publication])
    response = client.post(
        "/api/v1/projects/lean_energy/screening/title-abstract/decisions",
        json={
            "publication_id": str(publication.record_id),
            "reviewer_id": "alice",
            "outcome": outcome,
            "criterion_assessments": [],
        },
    )
    assert response.status_code == 201
    assert response.json()["stage"] == "title_abstract"
    detail = client.get(
        f"/api/v1/projects/lean_energy/screening/title-abstract/records/{publication.record_id}",
        params={"reviewer_id": "alice"},
    )
    assert detail.json()["status"] == status_value
    invalid_stage = client.post(
        "/api/v1/projects/lean_energy/screening/title-abstract/decisions",
        json={
            "publication_id": str(publication.record_id),
            "reviewer_id": "alice",
            "outcome": outcome,
            "stage": "full_text",
        },
    )
    assert invalid_stage.status_code == 422


def test_validation_not_ready_and_missing_reviewer(environment) -> None:
    client, publications, _, _, reviews = environment
    records = [_publication(1, "10.1/x"), _publication(2, "10.1/x")]
    publications.add_publications("lean_energy", records)
    overview = client.get("/api/v1/projects/lean_energy/screening/title-abstract", params={"reviewer_id": "alice"})
    assert overview.json()["readiness_status"] == "unresolved_duplicates"
    blocked = client.get("/api/v1/projects/lean_energy/screening/title-abstract/records", params={"reviewer_id": "alice"})
    assert blocked.status_code == 409
    assert blocked.json()["detail"]["readiness_status"] == "unresolved_duplicates"
    assert client.get("/api/v1/projects/lean_energy/screening/title-abstract/records").status_code == 422
    assert (
        client.get("/api/v1/projects/lean_energy/screening/title-abstract/records", params={"reviewer_id": "   "}).status_code
        == 422
    )


def test_approved_but_unmerged_duplicates_block_screening(environment) -> None:
    client, publications, _, _, reviews = environment
    records = [_publication(2, "10.1/x"), _publication(1, "10.1/x")]
    publications.add_publications("lean_energy", records)
    group = DuplicateGroupBuilder().build(records)[0]
    reviews.save_decision(
        "lean_energy", str(group.group_id), DuplicateGroupReviewDecision(decision=DuplicateDecision.APPROVE)
    )
    noncanonical = client.post(
        "/api/v1/projects/lean_energy/screening/title-abstract/decisions",
        json={"publication_id": str(records[0].record_id), "reviewer_id": "alice", "outcome": "include"},
    )
    assert noncanonical.status_code == 409
    generic_bypass = client.post(
        "/api/v1/projects/lean_energy/screening/decisions",
        json={
            "publication_id": str(records[0].record_id),
            "stage": "title_abstract",
            "reviewer_id": "alice",
            "outcome": "include",
        },
    )
    assert generic_bypass.status_code == 409
    assert generic_bypass.json()["detail"]["code"] == "title_abstract_workflow_required"
    canonical = client.post(
        "/api/v1/projects/lean_energy/screening/title-abstract/decisions",
        json={"publication_id": str(records[1].record_id), "reviewer_id": "alice", "outcome": "include"},
    )
    assert canonical.status_code == 409
    foreign = client.get(
        f"/api/v1/projects/ai_architecture/screening/title-abstract/records/{records[1].record_id}",
        params={"reviewer_id": "alice"},
    )
    assert foreign.status_code == 404
    missing = client.get(
        f"/api/v1/projects/lean_energy/screening/title-abstract/records/{uuid4()}", params={"reviewer_id": "alice"}
    )
    assert missing.status_code == 409


def test_required_criterion_validation_is_422(environment) -> None:
    client, publications, criteria, *_ = environment
    publication = _publication(1)
    publications.add_publications("lean_energy", [publication])
    criteria.create(
        ScreeningCriterion(
            project_id="lean_energy",
            name="Required",
            criterion_type=ScreeningCriterionType.INCLUSION,
            screening_stage=ScreeningCriterionStage.BOTH,
            is_required=True,
        )
    )
    response = client.post(
        "/api/v1/projects/lean_energy/screening/title-abstract/decisions",
        json={"publication_id": str(publication.record_id), "reviewer_id": "alice", "outcome": "include"},
    )
    assert response.status_code == 422
