from datetime import datetime, timedelta, timezone
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.api.main import app
from app.api.routers.screening import (
    get_conflict_resolution_service,
    get_multi_reviewer_screening_service,
    get_screening_reporting_service,
)
from app.domain.conflict_resolution import ResolvedOutcome
from app.domain.publication import Publication
from app.domain.screening import ScreeningDecision, ScreeningOutcome, ScreeningStage
from app.repositories.conflict_resolution_repository import SqliteConflictResolutionRepository
from app.repositories.duplicate_review_decision_repository import (
    InMemoryDuplicateReviewDecisionRepository,
)
from app.repositories.project_publication_repository import (
    SqliteProjectPublicationRepository,
)
from app.repositories.screening_decision_repository import (
    SqliteScreeningDecisionRepository,
)
from app.repositories.screening_reporting_repository import ScreeningReportingRepository
from app.repositories.screening_reviewer_assignment_repository import (
    SqliteScreeningReviewerAssignmentRepository,
)
from app.services.conflict_resolution_service import ConflictResolutionService
from app.services.multi_reviewer_screening_service import MultiReviewerScreeningService
from app.services.screening_input_service import ScreeningInputService
from app.services.screening_reporting_service import ScreeningReportingService


@pytest.fixture
def environment(tmp_path):
    database = tmp_path / "reporting-api.db"
    publications = SqliteProjectPublicationRepository(database)
    decisions = SqliteScreeningDecisionRepository(database)
    resolutions = SqliteConflictResolutionRepository(database)
    assignments = SqliteScreeningReviewerAssignmentRepository(database)
    input_service = ScreeningInputService(publications, InMemoryDuplicateReviewDecisionRepository())
    multi = MultiReviewerScreeningService(
        assignments, ScreeningReportingRepository(database), input_service, resolutions
    )
    resolution_service = ConflictResolutionService(multi, resolutions)
    service = ScreeningReportingService(
        input_service,
        ScreeningReportingRepository(database),
        publications,
        resolutions,
    )
    app.dependency_overrides[get_screening_reporting_service] = lambda: service
    app.dependency_overrides[get_multi_reviewer_screening_service] = lambda: multi
    app.dependency_overrides[get_conflict_resolution_service] = lambda: resolution_service
    yield TestClient(app), publications, decisions, multi, resolution_service, database
    app.dependency_overrides.clear()


def test_report_and_audit_are_reviewer_and_project_scoped(environment) -> None:
    client, publications, decisions, _, _, _ = environment
    paper = Publication(
        record_id=UUID("00000000-0000-0000-0000-000000000001"),
        title="Audited paper",
    )
    publications.add_publications("lean_energy", [paper])
    now = datetime(2026, 8, 11, tzinfo=timezone.utc)
    decisions.save(
        ScreeningDecision(
            project_id="lean_energy",
            publication_id=paper.record_id,
            stage=ScreeningStage.TITLE_ABSTRACT,
            outcome=ScreeningOutcome.UNCERTAIN,
            reviewer_id="alice",
            decided_at=now,
        )
    )
    decisions.save(
        ScreeningDecision(
            project_id="lean_energy",
            publication_id=paper.record_id,
            stage=ScreeningStage.TITLE_ABSTRACT,
            outcome=ScreeningOutcome.INCLUDE,
            reviewer_id="alice",
            decided_at=now + timedelta(minutes=1),
        )
    )
    decisions.save(
        ScreeningDecision(
            project_id="lean_energy",
            publication_id=paper.record_id,
            stage=ScreeningStage.TITLE_ABSTRACT,
            outcome=ScreeningOutcome.EXCLUDE,
            reviewer_id="bob",
            decided_at=now + timedelta(minutes=2),
        )
    )

    report = client.get("/projects/lean_energy/screening/report", params={"reviewer_id": "alice"})
    audit = client.get(
        "/projects/lean_energy/screening/audit",
        params={"reviewer_id": "alice", "outcome": "include"},
    )

    assert report.status_code == 200
    assert report.json()["title_abstract"] == {
        "total_eligible": 1,
        "screened": 1,
        "remaining": 0,
        "included": 1,
        "excluded": 0,
        "uncertain": 0,
    }
    assert report.json()["transitions"]["full_text_eligible"] == 1
    assert audit.status_code == 200
    assert audit.json()["total"] == 1
    assert audit.json()["items"][0]["revision_index"] == 2
    assert audit.json()["items"][0]["previous_outcome"] == "uncertain"
    assert audit.json()["items"][0]["is_latest_for_reviewer"] is True
    assert audit.json()["items"][0]["event_type"] == "DECISION"


def test_reviewer_roster_and_conflict_api(environment) -> None:
    client, publications, decisions, _, _, _ = environment
    paper = Publication(
        record_id=UUID("00000000-0000-0000-0000-000000000002"),
        title="Conflicted paper",
    )
    publications.add_publications("lean_energy", [paper])
    roster = client.put(
        "/projects/lean_energy/screening/reviewers",
        params={"stage": "title_abstract"},
        json={"reviewer_ids": ["alice", "bob"]},
    )
    assert roster.status_code == 200
    now = datetime(2026, 8, 11, tzinfo=timezone.utc)
    decisions.save(
        ScreeningDecision(
            project_id="lean_energy", publication_id=paper.record_id,
            stage=ScreeningStage.TITLE_ABSTRACT, outcome=ScreeningOutcome.INCLUDE,
            reviewer_id="alice", decided_at=now,
        )
    )
    decisions.save(
        ScreeningDecision(
            project_id="lean_energy", publication_id=paper.record_id,
            stage=ScreeningStage.TITLE_ABSTRACT, outcome=ScreeningOutcome.EXCLUDE,
            reviewer_id="bob", decided_at=now + timedelta(seconds=1),
        )
    )
    conflicts = client.get(
        "/projects/lean_energy/screening/conflicts",
        params={"stage": "title_abstract", "status": "conflict", "viewer_reviewer_id": "alice"},
    )
    assert conflicts.status_code == 200
    assert conflicts.json()["total"] == 1
    assert conflicts.json()["items"][0]["status"] == "conflict"
    assert len(conflicts.json()["items"][0]["latest_decisions"]) == 2

    blind = client.get(
        "/projects/lean_energy/screening/conflicts",
        params={"stage": "title_abstract", "viewer_reviewer_id": "carol"},
    )
    assert blind.status_code == 200
    assert blind.json()["items"][0]["latest_decisions"] == []


def test_unified_audit_orders_pages_and_marks_stale_resolution(environment) -> None:
    client, publications, decisions, multi, resolution_service, _ = environment
    paper = Publication(
        record_id=UUID("00000000-0000-0000-0000-000000000003"),
        title="Resolved audit paper",
    )
    publications.add_publications("lean_energy", [paper])
    multi.roster("lean_energy", ScreeningStage.TITLE_ABSTRACT, ["alice", "bob"])
    now = datetime.now(timezone.utc) - timedelta(minutes=5)
    for seconds, reviewer, outcome in (
        (0, "alice", ScreeningOutcome.INCLUDE),
        (1, "bob", ScreeningOutcome.EXCLUDE),
    ):
        decisions.save(
            ScreeningDecision(
                project_id="lean_energy", publication_id=paper.record_id,
                stage=ScreeningStage.TITLE_ABSTRACT, outcome=outcome,
                reviewer_id=reviewer, rationale=f"{reviewer} rationale",
                decided_at=now + timedelta(seconds=seconds),
            )
        )
    state = multi.publication_state("lean_energy", paper.record_id, ScreeningStage.TITLE_ABSTRACT)
    assert state is not None
    resolution = resolution_service.resolve(
        "lean_energy", paper.record_id, ScreeningStage.TITLE_ABSTRACT,
        ResolvedOutcome.INCLUDE, "adjudicator", "Audit resolution rationale",
        state.current_decision_set_key,
    )

    other = Publication(
        record_id=UUID("00000000-0000-0000-0000-000000000004"),
        title="Other project's resolution",
    )
    publications.add_publications("ai_architecture", [other])
    multi.roster("ai_architecture", ScreeningStage.TITLE_ABSTRACT, ["alice", "bob"])
    for seconds, reviewer, outcome in (
        (0, "alice", ScreeningOutcome.INCLUDE),
        (1, "bob", ScreeningOutcome.EXCLUDE),
    ):
        decisions.save(
            ScreeningDecision(
                project_id="ai_architecture", publication_id=other.record_id,
                stage=ScreeningStage.TITLE_ABSTRACT, outcome=outcome,
                reviewer_id=reviewer, decided_at=now + timedelta(seconds=seconds),
            )
        )
    other_state = multi.publication_state(
        "ai_architecture", other.record_id, ScreeningStage.TITLE_ABSTRACT
    )
    assert other_state is not None
    other_resolution = resolution_service.resolve(
        "ai_architecture", other.record_id, ScreeningStage.TITLE_ABSTRACT,
        ResolvedOutcome.EXCLUDE, "other-adjudicator", "Other project rationale",
        other_state.current_decision_set_key,
    )

    current = client.get(
        "/projects/lean_energy/screening/audit",
        params={"stage": "title_abstract", "publication_id": str(paper.record_id)},
    )
    assert current.status_code == 200
    resolution_event = next(item for item in current.json()["items"] if item["event_type"] == "RESOLUTION")
    assert resolution_event["resolution_id"] == str(resolution.resolution_id)
    assert resolution_event["status"] == "CURRENT"
    assert resolution_event["resolver_id"] == "adjudicator"
    assert {item["reviewer_id"] for item in resolution_event["reviewer_outcomes"]} == {"alice", "bob"}
    assert all(item.get("resolution_id") != str(other_resolution.resolution_id) for item in current.json()["items"])

    decisions.save(
        ScreeningDecision(
            project_id="lean_energy", publication_id=paper.record_id,
            stage=ScreeningStage.TITLE_ABSTRACT, outcome=ScreeningOutcome.UNCERTAIN,
            reviewer_id="bob", rationale="Changed after adjudication",
            decided_at=datetime.now(timezone.utc) + timedelta(minutes=1),
        )
    )
    stale = client.get(
        "/projects/lean_energy/screening/audit",
        params={"stage": "title_abstract", "publication_id": str(paper.record_id)},
    )
    assert stale.status_code == 200
    items = stale.json()["items"]
    stale_resolution = next(item for item in items if item["event_type"] == "RESOLUTION")
    assert stale_resolution["status"] == "STALE"
    assert items[0]["event_type"] == "DECISION"
    assert items[0]["decision"]["rationale"] == "Changed after adjudication"

    first_page = client.get(
        "/projects/lean_energy/screening/audit",
        params={"publication_id": str(paper.record_id), "offset": 0, "limit": 1},
    ).json()
    second_page = client.get(
        "/projects/lean_energy/screening/audit",
        params={"publication_id": str(paper.record_id), "offset": 1, "limit": 1},
    ).json()
    assert first_page["total"] == 4
    assert first_page["items"][0]["event_type"] == "DECISION"
    assert second_page["items"][0]["event_type"] == "RESOLUTION"

    full_text = client.get(
        "/projects/lean_energy/screening/audit",
        params={"stage": "full_text", "publication_id": str(paper.record_id)},
    )
    assert full_text.status_code == 200
    assert full_text.json()["items"] == []


def test_reporting_counts_current_stale_and_project_outcomes(environment) -> None:
    client, publications, decisions, multi, resolution_service, _ = environment
    papers = [
        Publication(
            record_id=UUID(f"00000000-0000-0000-0000-00000000001{index}"),
            title=f"Reporting paper {index}",
        )
        for index in range(1, 5)
    ]
    publications.add_publications("lean_energy", papers)
    multi.roster("lean_energy", ScreeningStage.TITLE_ABSTRACT, ["alice", "bob"])
    now = datetime(2026, 8, 11, tzinfo=timezone.utc)

    def decide(paper: Publication, reviewer: str, outcome: ScreeningOutcome, seconds: int) -> None:
        decisions.save(
            ScreeningDecision(
                project_id="lean_energy", publication_id=paper.record_id,
                stage=ScreeningStage.TITLE_ABSTRACT, outcome=outcome,
                reviewer_id=reviewer, decided_at=now + timedelta(seconds=seconds),
            )
        )

    # Agreement INCLUDE, unresolved conflict, currently resolved EXCLUDE, and stale resolution.
    for index, paper in enumerate(papers):
        decide(paper, "alice", ScreeningOutcome.INCLUDE, index * 10)
        decide(
            paper,
            "bob",
            ScreeningOutcome.INCLUDE if index == 0 else ScreeningOutcome.EXCLUDE,
            index * 10 + 1,
        )
    for paper, outcome, resolver in (
        (papers[2], ResolvedOutcome.EXCLUDE, "current-resolver"),
        (papers[3], ResolvedOutcome.UNCERTAIN, "stale-resolver"),
    ):
        state = multi.publication_state("lean_energy", paper.record_id, ScreeningStage.TITLE_ABSTRACT)
        assert state is not None
        resolution_service.resolve(
            "lean_energy", paper.record_id, ScreeningStage.TITLE_ABSTRACT,
            outcome, resolver, "Reporting rationale", state.current_decision_set_key,
        )
    decide(papers[3], "bob", ScreeningOutcome.UNCERTAIN, 100)

    metrics = client.get(
        "/projects/lean_energy/screening/conflict-metrics",
        params={"stage": "title_abstract"},
    )
    assert metrics.status_code == 200
    assert metrics.json() == {
        "incomplete": 0,
        "agreement": 1,
        "conflict": 1,
        "resolved": 1,
        "stale_resolution": 1,
        "agreement_rate": 0.5,
        "resolution_rate": pytest.approx(1 / 3),
    }
    report = client.get(
        "/projects/lean_energy/screening/report",
        params={"reviewer_id": "alice"},
    )
    assert report.status_code == 200
    assert report.json()["title_abstract_project_outcomes"] == {
        "stage": "title_abstract",
        "total": 4,
        "include": 1,
        "exclude": 1,
        "uncertain": 0,
        "pending": 2,
    }
