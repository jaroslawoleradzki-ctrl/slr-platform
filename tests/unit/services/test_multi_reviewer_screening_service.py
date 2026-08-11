from datetime import datetime, timedelta, timezone
from uuid import UUID

from app.domain.project import Project
from app.domain.publication import Publication
from app.domain.screening import ScreeningDecision, ScreeningOutcome, ScreeningStage
from app.repositories.duplicate_review_decision_repository import InMemoryDuplicateReviewDecisionRepository
from app.repositories.project_publication_repository import SqliteProjectPublicationRepository
from app.repositories.project_repository import SqliteProjectRepository
from app.repositories.screening_decision_repository import SqliteScreeningDecisionRepository
from app.repositories.screening_reporting_repository import ScreeningReportingRepository
from app.repositories.screening_reviewer_assignment_repository import (
    SqliteScreeningReviewerAssignmentRepository,
)
from app.services.multi_reviewer_screening_service import (
    MultiReviewerScreeningService,
    ScreeningConflictStatus,
)
from app.services.screening_input_service import ScreeningInputService


def _publication(number: int) -> Publication:
    return Publication(
        record_id=UUID(f"00000000-0000-0000-0000-{number:012d}"),
        title=f"Publication {number}",
    )


def _service(tmp_path):
    database = tmp_path / "multi-reviewer.db"
    publications = SqliteProjectPublicationRepository(database)
    publications.add_publications("lean_energy", [_publication(1), _publication(2), _publication(3)])
    decisions = SqliteScreeningDecisionRepository(database)
    assignments = SqliteScreeningReviewerAssignmentRepository(database)
    input_service = ScreeningInputService(publications, InMemoryDuplicateReviewDecisionRepository())
    service = MultiReviewerScreeningService(assignments, ScreeningReportingRepository(database), input_service)
    return service, assignments, decisions, publications, database


def _decision(publication_id: UUID, reviewer: str, outcome: ScreeningOutcome, seconds: int) -> ScreeningDecision:
    return ScreeningDecision(
        project_id="lean_energy",
        publication_id=publication_id,
        stage=ScreeningStage.TITLE_ABSTRACT,
        outcome=outcome,
        reviewer_id=reviewer,
        decided_at=datetime(2026, 8, 11, tzinfo=timezone.utc) + timedelta(seconds=seconds),
    )


def test_roster_is_lifecycle_based_and_conflicts_are_derived(tmp_path) -> None:
    service, assignments, decisions, _, _ = _service(tmp_path)
    service.roster("lean_energy", ScreeningStage.TITLE_ABSTRACT, ["alice", "bob"])
    decisions.save(_decision(_publication(1).record_id, "alice", ScreeningOutcome.INCLUDE, 1))
    decisions.save(_decision(_publication(1).record_id, "bob", ScreeningOutcome.INCLUDE, 2))
    decisions.save(_decision(_publication(2).record_id, "alice", ScreeningOutcome.INCLUDE, 1))
    decisions.save(_decision(_publication(2).record_id, "bob", ScreeningOutcome.EXCLUDE, 2))
    decisions.save(_decision(_publication(3).record_id, "alice", ScreeningOutcome.UNCERTAIN, 1))

    records, total = service.conflicts("lean_energy", ScreeningStage.TITLE_ABSTRACT, limit=10)
    assert total == 3
    assert [item.status for item in records] == [
        ScreeningConflictStatus.AGREEMENT,
        ScreeningConflictStatus.CONFLICT,
        ScreeningConflictStatus.INCOMPLETE,
    ]
    metrics = service.metrics("lean_energy", ScreeningStage.TITLE_ABSTRACT)
    assert (metrics.agreement, metrics.conflict, metrics.incomplete, metrics.agreement_rate) == (1, 1, 1, 0.5)

    service.roster("lean_energy", ScreeningStage.TITLE_ABSTRACT, ["bob", "carol"])
    roster = assignments.list("lean_energy", ScreeningStage.TITLE_ABSTRACT)
    assert [(item.reviewer_id, item.is_active) for item in roster] == [
        ("alice", False),
        ("bob", True),
        ("carol", True),
    ]


def test_latest_wins_three_reviewer_and_blind_presentation(tmp_path) -> None:
    service, _, decisions, _, _ = _service(tmp_path)
    service.roster("lean_energy", ScreeningStage.TITLE_ABSTRACT, ["alice", "bob", "carol"])
    paper = _publication(1).record_id
    decisions.save(_decision(paper, "alice", ScreeningOutcome.INCLUDE, 1))
    decisions.save(_decision(paper, "alice", ScreeningOutcome.EXCLUDE, 4))
    decisions.save(_decision(paper, "bob", ScreeningOutcome.EXCLUDE, 2))
    decisions.save(_decision(paper, "carol", ScreeningOutcome.EXCLUDE, 3))

    records, _ = service.conflicts("lean_energy", ScreeningStage.TITLE_ABSTRACT, viewer_reviewer_id="alice")
    first = next(item for item in records if item.publication_id == paper)
    assert first.status is ScreeningConflictStatus.AGREEMENT
    assert [item.outcome for item in first.latest_decisions] == [
        ScreeningOutcome.EXCLUDE,
        ScreeningOutcome.EXCLUDE,
        ScreeningOutcome.EXCLUDE,
    ]

    blind_records, _ = service.conflicts("lean_energy", ScreeningStage.TITLE_ABSTRACT, viewer_reviewer_id="dana")
    blind = next(item for item in blind_records if item.publication_id == paper)
    assert blind.latest_decisions == ()


def test_no_completed_comparison_has_null_agreement_rate(tmp_path) -> None:
    service, _, decisions, _, _ = _service(tmp_path)
    service.roster("lean_energy", ScreeningStage.FULL_TEXT, ["alice", "bob"])
    decisions.save(_decision(_publication(1).record_id, "alice", ScreeningOutcome.INCLUDE, 1))
    decisions.save(_decision(_publication(1).record_id, "bob", ScreeningOutcome.INCLUDE, 2))
    decisions.save(
        ScreeningDecision(
            project_id="lean_energy",
            publication_id=_publication(1).record_id,
            stage=ScreeningStage.FULL_TEXT,
            outcome=ScreeningOutcome.INCLUDE,
            reviewer_id="alice",
        )
    )
    metrics = service.metrics("lean_energy", ScreeningStage.FULL_TEXT)
    assert metrics.incomplete == 1
    assert metrics.agreement_rate is None


def test_conflicts_are_project_scoped_and_use_one_batch_latest_query(tmp_path, monkeypatch) -> None:
    service, _, decisions, publications, database = _service(tmp_path)
    service.roster("lean_energy", ScreeningStage.TITLE_ABSTRACT, ["alice", "bob"])
    paper = _publication(1).record_id
    decisions.save(_decision(paper, "alice", ScreeningOutcome.INCLUDE, 1))
    decisions.save(_decision(paper, "bob", ScreeningOutcome.INCLUDE, 2))
    calls = 0
    original = service._reporting.latest_decisions_for_stage_all_reviewers

    def counted(project_id, stage):
        nonlocal calls
        calls += 1
        return original(project_id, stage)

    monkeypatch.setattr(service._reporting, "latest_decisions_for_stage_all_reviewers", counted)
    records, _ = service.conflicts("lean_energy", ScreeningStage.TITLE_ABSTRACT)

    SqliteProjectRepository(database).create(Project(project_id="other-project", title="Other"))
    publications.add_publications("other-project", [_publication(4)])
    assert calls == 1
    assert records[0].project_id == "lean_energy"
    assert service.conflicts("other-project", ScreeningStage.TITLE_ABSTRACT) == ([], 0)


def test_roster_reactivation_preserves_history_and_stage_project_isolation(tmp_path) -> None:
    service, assignments, decisions, publications, database = _service(tmp_path)
    paper = _publication(1).record_id
    service.roster("lean_energy", ScreeningStage.TITLE_ABSTRACT, ["alice", "bob"])
    decisions.save(_decision(paper, "bob", ScreeningOutcome.INCLUDE, 1))

    service.roster("lean_energy", ScreeningStage.TITLE_ABSTRACT, ["alice"])
    assert [(item.reviewer_id, item.is_active) for item in assignments.list("lean_energy", ScreeningStage.TITLE_ABSTRACT)] == [
        ("alice", True),
        ("bob", False),
    ]
    assert len(decisions.list_history("lean_energy", paper, ScreeningStage.TITLE_ABSTRACT, "bob")) == 1

    service.roster("lean_energy", ScreeningStage.TITLE_ABSTRACT, ["alice", "bob"])
    assert [(item.reviewer_id, item.is_active) for item in assignments.list("lean_energy", ScreeningStage.TITLE_ABSTRACT)] == [
        ("alice", True),
        ("bob", True),
    ]
    service.roster("lean_energy", ScreeningStage.FULL_TEXT, ["carol"])
    assert [item.reviewer_id for item in assignments.list("lean_energy", ScreeningStage.FULL_TEXT, active_only=True)] == [
        "carol"
    ]

    SqliteProjectRepository(database).create(Project(project_id="other-project", title="Other"))
    publications.add_publications("other-project", [_publication(4)])
    service.roster("other-project", ScreeningStage.TITLE_ABSTRACT, ["dana"])
    assert [item.reviewer_id for item in assignments.list("other-project", ScreeningStage.TITLE_ABSTRACT, active_only=True)] == [
        "dana"
    ]
    assert [item.reviewer_id for item in assignments.list("lean_energy", ScreeningStage.TITLE_ABSTRACT, active_only=True)] == [
        "alice",
        "bob",
    ]
