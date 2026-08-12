from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.domain.screening import ScreeningDecision, ScreeningOutcome, ScreeningStage
from app.repositories.screening_decision_repository import SqliteScreeningDecisionRepository
from app.repositories.screening_reporting_repository import ScreeningReportingRepository


def _decision(
    project_id: str,
    publication_id,
    outcome: ScreeningOutcome,
    when: datetime,
    reviewer_id: str = "reviewer-a",
) -> ScreeningDecision:
    return ScreeningDecision(
        project_id=project_id,
        publication_id=publication_id,
        stage=ScreeningStage.TITLE_ABSTRACT,
        outcome=outcome,
        reviewer_id=reviewer_id,
        decided_at=when,
    )


def test_audit_revision_metadata_uses_full_history_before_outcome_filter(tmp_path) -> None:
    database_path = tmp_path / "reporting.db"
    decisions = SqliteScreeningDecisionRepository(database_path)
    reporting = ScreeningReportingRepository(database_path)
    publication_id = uuid4()
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    decisions.save(_decision("project-a", publication_id, ScreeningOutcome.UNCERTAIN, start))
    latest = _decision(
        "project-a",
        publication_id,
        ScreeningOutcome.EXCLUDE,
        start + timedelta(minutes=1),
    )
    decisions.save(latest)
    decisions.save(
        _decision(
            "project-b",
            uuid4(),
            ScreeningOutcome.EXCLUDE,
            start,
        )
    )

    rows, total = reporting.audit_page("project-a", outcome=ScreeningOutcome.EXCLUDE)

    assert total == 1
    assert rows[0].decision.decision_id == latest.decision_id
    assert rows[0].revision_index == 2
    assert rows[0].previous_outcome is ScreeningOutcome.UNCERTAIN
    assert rows[0].is_latest_for_reviewer is True


def test_latest_decisions_is_reviewer_scoped_and_batch_hydrated(tmp_path) -> None:
    database_path = tmp_path / "reporting-latest.db"
    decisions = SqliteScreeningDecisionRepository(database_path)
    reporting = ScreeningReportingRepository(database_path)
    moment = datetime(2026, 1, 1, tzinfo=timezone.utc)
    publication_id = uuid4()
    decisions.save(_decision("project-a", publication_id, ScreeningOutcome.INCLUDE, moment))
    decisions.save(
        _decision(
            "project-a",
            publication_id,
            ScreeningOutcome.EXCLUDE,
            moment + timedelta(minutes=1),
            reviewer_id="reviewer-b",
        )
    )

    latest = reporting.latest_decisions("project-a", "reviewer-a")

    assert [(item.publication_id, item.outcome) for item in latest] == [(publication_id, ScreeningOutcome.INCLUDE)]


def test_latest_decision_read_uses_constant_query_count(tmp_path) -> None:
    database_path = tmp_path / "reporting-query-count.db"
    decisions = SqliteScreeningDecisionRepository(database_path)
    moment = datetime(2026, 1, 1, tzinfo=timezone.utc)
    for _ in range(20):
        decisions.save(_decision("project-a", uuid4(), ScreeningOutcome.INCLUDE, moment))

    class CountingRepository(ScreeningReportingRepository):
        def __init__(self, path) -> None:
            super().__init__(path)
            self.queries: list[str] = []

        def _connect(self):
            connection = super()._connect()
            connection.set_trace_callback(self.queries.append)
            return connection

    reporting = CountingRepository(database_path)
    latest = reporting.latest_decisions("project-a", "reviewer-a")

    assert len(latest) == 20
    assert len(reporting.queries) == 3
