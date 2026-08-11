from datetime import datetime, timedelta, timezone
from uuid import UUID

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


def test_report_drops_lost_full_text_eligibility_but_audit_keeps_history(tmp_path) -> None:
    database_path = tmp_path / "reporting-service.db"
    publications = SqliteProjectPublicationRepository(database_path)
    decisions = SqliteScreeningDecisionRepository(database_path)
    service = ScreeningReportingService(
        ScreeningInputService(publications, InMemoryDuplicateReviewDecisionRepository()),
        ScreeningReportingRepository(database_path),
        publications,
    )
    paper = Publication(record_id=UUID("00000000-0000-0000-0000-000000000001"), title="Paper")
    publications.add_publications("lean_energy", [paper])
    timestamp = datetime(2026, 8, 11, tzinfo=timezone.utc)
    decisions.save(
        ScreeningDecision(
            project_id="lean_energy",
            publication_id=paper.record_id,
            stage=ScreeningStage.TITLE_ABSTRACT,
            outcome=ScreeningOutcome.INCLUDE,
            reviewer_id="alice",
            decided_at=timestamp,
        )
    )
    decisions.save(
        ScreeningDecision(
            project_id="lean_energy",
            publication_id=paper.record_id,
            stage=ScreeningStage.FULL_TEXT,
            outcome=ScreeningOutcome.EXCLUDE,
            reviewer_id="alice",
            decided_at=timestamp + timedelta(minutes=1),
        )
    )
    _, _, full_text, _, _ = service.report("lean_energy", "alice")
    assert full_text is not None and full_text.total_eligible == 1

    decisions.save(
        ScreeningDecision(
            project_id="lean_energy",
            publication_id=paper.record_id,
            stage=ScreeningStage.TITLE_ABSTRACT,
            outcome=ScreeningOutcome.EXCLUDE,
            reviewer_id="alice",
            decided_at=timestamp + timedelta(minutes=2),
        )
    )
    _, _, full_text, _, _ = service.report("lean_energy", "alice")
    audit, total = service.audit("lean_energy", reviewer_id="alice", stage=ScreeningStage.FULL_TEXT)

    assert full_text is not None and full_text.total_eligible == 0
    assert total == 1
    assert audit[0].decision.stage is ScreeningStage.FULL_TEXT
