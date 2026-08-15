from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.main import app
from app.api.routers.screening import (
    get_conflict_resolution_service,
    get_multi_reviewer_screening_service,
)
from app.domain.publication import Publication
from app.domain.screening import ScreeningDecision, ScreeningOutcome, ScreeningStage
from app.repositories.conflict_resolution_repository import SqliteConflictResolutionRepository
from app.repositories.duplicate_review_decision_repository import InMemoryDuplicateReviewDecisionRepository
from app.repositories.project_publication_repository import SqliteProjectPublicationRepository
from app.repositories.screening_decision_repository import SqliteScreeningDecisionRepository
from app.repositories.screening_reporting_repository import ScreeningReportingRepository
from app.repositories.screening_reviewer_assignment_repository import SqliteScreeningReviewerAssignmentRepository
from app.services.conflict_resolution_service import ConflictResolutionService
from app.services.multi_reviewer_screening_service import MultiReviewerScreeningService
from app.services.screening_input_service import ScreeningInputService


@pytest.fixture()
def resolution_api(tmp_path):
    database = tmp_path / "resolution-api.db"
    publications = SqliteProjectPublicationRepository(database)
    paper = Publication(record_id=UUID("00000000-0000-0000-0000-000000000101"), title="Conflict paper")
    agreement = Publication(record_id=UUID("00000000-0000-0000-0000-000000000102"), title="Agreement paper")
    incomplete = Publication(record_id=UUID("00000000-0000-0000-0000-000000000103"), title="Incomplete paper")
    publications.add_publications("lean_energy", [paper, agreement, incomplete])
    decisions = SqliteScreeningDecisionRepository(database)
    assignments = SqliteScreeningReviewerAssignmentRepository(database)
    resolutions = SqliteConflictResolutionRepository(database)
    multi = MultiReviewerScreeningService(
        assignments,
        ScreeningReportingRepository(database),
        ScreeningInputService(publications, InMemoryDuplicateReviewDecisionRepository()),
        resolutions,
    )
    service = ConflictResolutionService(multi, resolutions)
    app.dependency_overrides[get_multi_reviewer_screening_service] = lambda: multi
    app.dependency_overrides[get_conflict_resolution_service] = lambda: service
    multi.roster("lean_energy", ScreeningStage.TITLE_ABSTRACT, ["alice", "bob"])
    now = datetime(2026, 8, 11, tzinfo=timezone.utc)

    def save(publication_id: UUID, reviewer: str, outcome: ScreeningOutcome, seconds: int, *, stage=ScreeningStage.TITLE_ABSTRACT):
        decision = ScreeningDecision(
            project_id="lean_energy", publication_id=publication_id, stage=stage,
            outcome=outcome, reviewer_id=reviewer, rationale=f"{reviewer} says {outcome.value}",
            decided_at=now + timedelta(seconds=seconds),
        )
        decisions.save(decision)
        return decision

    save(paper.record_id, "alice", ScreeningOutcome.INCLUDE, 1)
    save(paper.record_id, "bob", ScreeningOutcome.EXCLUDE, 2)
    save(agreement.record_id, "alice", ScreeningOutcome.INCLUDE, 3)
    save(agreement.record_id, "bob", ScreeningOutcome.INCLUDE, 4)
    save(incomplete.record_id, "alice", ScreeningOutcome.UNCERTAIN, 5)
    yield TestClient(app), paper, agreement, incomplete, decisions, multi, service, resolutions, save
    app.dependency_overrides.clear()


def _conflict(client: TestClient, publication_id: UUID) -> dict:
    response = client.get(
        "/api/v1/projects/lean_energy/screening/conflicts",
        params={"stage": "title_abstract", "status": "conflict", "adjudication": True},
    )
    assert response.status_code == 200
    return next(item for item in response.json()["items"] if item["publication_id"] == str(publication_id))


@pytest.mark.parametrize("outcome", ["include", "exclude", "uncertain"])
def test_conflict_detail_and_save_each_resolution_outcome(resolution_api, outcome: str) -> None:
    client, paper, *_ = resolution_api
    detail = _conflict(client, paper.record_id)
    assert {item["reviewer_id"] for item in detail["latest_decisions"]} == {"alice", "bob"}
    assert all(item["decision"]["rationale"] for item in detail["latest_decisions"])
    response = client.post(
        "/api/v1/projects/lean_energy/screening/conflict-resolutions",
        json={
            "publication_id": str(paper.record_id), "stage": "title_abstract",
            "resolved_outcome": outcome, "resolver_id": " independent adjudicator ",
            "rationale": " A required human rationale ",
            "expected_decision_set_key": detail["current_decision_set_key"],
        },
    )
    assert response.status_code == 201
    assert response.json()["resolved_outcome"] == outcome
    assert response.json()["resolver_id"] == "independent adjudicator"
    resolved = client.get(
        "/api/v1/projects/lean_energy/screening/conflicts",
        params={"stage": "title_abstract", "status": "resolved", "adjudication": True},
    )
    assert resolved.status_code == 200
    assert resolved.json()["items"][0]["resolution"]["is_current"] is True


def test_incomplete_and_agreement_cannot_be_resolved_and_validation_is_authoritative(resolution_api) -> None:
    client, _, agreement, incomplete, *_ = resolution_api
    all_items = client.get(
        "/api/v1/projects/lean_energy/screening/conflicts",
        params={"stage": "title_abstract", "adjudication": True},
    ).json()["items"]
    by_id = {item["publication_id"]: item for item in all_items}
    for publication in (agreement, incomplete):
        response = client.post(
            "/api/v1/projects/lean_energy/screening/conflict-resolutions",
            json={
                "publication_id": str(publication.record_id), "stage": "title_abstract",
                "resolved_outcome": "include", "resolver_id": "resolver", "rationale": "reason",
                "expected_decision_set_key": by_id[str(publication.record_id)]["current_decision_set_key"],
            },
        )
        assert response.status_code == 422
    conflict = next(item for item in all_items if item["status"] == "conflict")
    base = {
        "publication_id": conflict["publication_id"], "stage": "title_abstract",
        "resolved_outcome": "include", "resolver_id": "resolver", "rationale": "reason",
        "expected_decision_set_key": conflict["current_decision_set_key"],
    }
    for field in ("resolver_id", "rationale"):
        response = client.post(
            "/api/v1/projects/lean_energy/screening/conflict-resolutions",
            json={**base, field: "   "},
        )
        assert response.status_code == 422


def test_history_stale_key_409_and_append_only_reresolution(resolution_api) -> None:
    client, paper, _, _, _, _, _, _, save = resolution_api
    detail = _conflict(client, paper.record_id)
    first = client.post(
        "/api/v1/projects/lean_energy/screening/conflict-resolutions",
        json={
            "publication_id": str(paper.record_id), "stage": "title_abstract",
            "resolved_outcome": "include", "resolver_id": "one", "rationale": "first",
            "expected_decision_set_key": detail["current_decision_set_key"],
        },
    )
    assert first.status_code == 201
    save(paper.record_id, "bob", ScreeningOutcome.UNCERTAIN, 20)
    stale = client.get(
        "/api/v1/projects/lean_energy/screening/conflicts",
        params={"stage": "title_abstract", "status": "stale_resolution", "adjudication": True},
    )
    assert stale.status_code == 200 and stale.json()["total"] == 1
    current = stale.json()["items"][0]
    conflict_response = client.post(
        "/api/v1/projects/lean_energy/screening/conflict-resolutions",
        json={
            "publication_id": str(paper.record_id), "stage": "title_abstract",
            "resolved_outcome": "exclude", "resolver_id": "two", "rationale": "outdated",
            "expected_decision_set_key": detail["current_decision_set_key"],
        },
    )
    assert conflict_response.status_code == 409
    assert conflict_response.json()["detail"]["code"] == "decision_set_changed"
    second = client.post(
        "/api/v1/projects/lean_energy/screening/conflict-resolutions",
        json={
            "publication_id": str(paper.record_id), "stage": "title_abstract",
            "resolved_outcome": "exclude", "resolver_id": "two", "rationale": "fresh",
            "expected_decision_set_key": current["current_decision_set_key"],
        },
    )
    assert second.status_code == 201
    history = client.get(
        f"/api/v1/projects/lean_energy/screening/conflict-resolutions/{paper.record_id}/history",
        params={"stage": "title_abstract"},
    )
    assert history.status_code == 200
    assert [item["resolution_id"] for item in history.json()["resolutions"]] == [
        second.json()["resolution_id"], first.json()["resolution_id"]
    ]
    assert [item["is_current"] for item in history.json()["resolutions"]] == [True, False]
    assert history.json()["total"] == 2
    assert {
        (item["reviewer_id"], item["outcome"])
        for item in history.json()["resolutions"][0]["reviewer_outcomes"]
    } == {("alice", "include"), ("bob", "uncertain")}
    page = client.get(
        f"/api/v1/projects/lean_energy/screening/conflict-resolutions/{paper.record_id}/history",
        params={"stage": "title_abstract", "offset": 1, "limit": 1},
    )
    assert page.status_code == 200
    assert page.json()["total"] == 2
    assert page.json()["offset"] == 1
    assert [item["resolution_id"] for item in page.json()["resolutions"]] == [first.json()["resolution_id"]]


def test_resolution_api_project_stage_and_missing_resource_isolation(resolution_api) -> None:
    client, paper, *_ = resolution_api
    detail = _conflict(client, paper.record_id)
    saved = client.post(
        "/api/v1/projects/lean_energy/screening/conflict-resolutions",
        json={
            "publication_id": str(paper.record_id), "stage": "title_abstract",
            "resolved_outcome": "include", "resolver_id": "resolver", "rationale": "scope",
            "expected_decision_set_key": detail["current_decision_set_key"],
        },
    )
    assert saved.status_code == 201
    wrong_project = client.get(
        f"/api/v1/projects/ai_architecture/screening/conflict-resolutions/{paper.record_id}/history",
        params={"stage": "title_abstract"},
    )
    assert wrong_project.status_code == 404
    missing = client.get(
        f"/api/v1/projects/lean_energy/screening/conflict-resolutions/{uuid4()}/history",
        params={"stage": "title_abstract"},
    )
    assert missing.status_code == 404
    other_stage = client.get(
        f"/api/v1/projects/lean_energy/screening/conflict-resolutions/{paper.record_id}/history",
        params={"stage": "full_text"},
    )
    assert other_stage.status_code == 404
    missing_project = client.post(
        "/api/v1/projects/nonexistent-project/screening/conflict-resolutions",
        json={
            "publication_id": str(paper.record_id), "stage": "title_abstract",
            "resolved_outcome": "include", "resolver_id": "resolver", "rationale": "missing",
            "expected_decision_set_key": detail["current_decision_set_key"],
        },
    )
    assert missing_project.status_code == 404
