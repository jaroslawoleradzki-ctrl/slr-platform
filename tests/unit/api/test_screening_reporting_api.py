from datetime import datetime, timedelta, timezone
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.api.main import app
from app.api.routers.screening import get_screening_reporting_service
from app.domain.publication import Publication
from app.domain.screening import ScreeningDecision, ScreeningOutcome, ScreeningStage
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
from app.services.screening_input_service import ScreeningInputService
from app.services.screening_reporting_service import ScreeningReportingService


@pytest.fixture
def environment(tmp_path):
    database = tmp_path / "reporting-api.db"
    publications = SqliteProjectPublicationRepository(database)
    decisions = SqliteScreeningDecisionRepository(database)
    service = ScreeningReportingService(
        ScreeningInputService(publications, InMemoryDuplicateReviewDecisionRepository()),
        ScreeningReportingRepository(database),
        publications,
    )
    app.dependency_overrides[get_screening_reporting_service] = lambda: service
    yield TestClient(app), publications, decisions
    app.dependency_overrides.clear()


def test_report_and_audit_are_reviewer_and_project_scoped(environment) -> None:
    client, publications, decisions = environment
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
