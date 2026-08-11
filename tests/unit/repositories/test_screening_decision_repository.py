import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest

from app.domain.screening import (
    CriterionAssessment,
    CriterionAssessmentValue,
    ScreeningCriterionStage,
    ScreeningCriterionType,
    ScreeningDecision,
    ScreeningOutcome,
    ScreeningStage,
)
from app.repositories.screening_decision_repository import (
    DecisionNotFoundError,
    SqliteScreeningDecisionRepository,
)


@pytest.fixture
def repository(tmp_path) -> SqliteScreeningDecisionRepository:
    db_path = tmp_path / "test_screening_decisions.db"
    return SqliteScreeningDecisionRepository(db_path)


def test_save_and_get_decision(repository: SqliteScreeningDecisionRepository) -> None:
    pub_id = uuid4()
    cid = uuid4()
    assessment = CriterionAssessment(
        criterion_id=cid,
        criterion_name="Criterion 1",
        criterion_type=ScreeningCriterionType.INCLUSION,
        criterion_stage=ScreeningCriterionStage.TITLE_ABSTRACT,
        criterion_is_required=True,
        assessment_value=CriterionAssessmentValue.MET,
        notes="All good",
    )
    decision = ScreeningDecision(
        project_id="proj-1",
        publication_id=pub_id,
        stage=ScreeningStage.TITLE_ABSTRACT,
        outcome=ScreeningOutcome.INCLUDE,
        reviewer_id="reviewer-1",
        rationale="Clear inclusion",
        criterion_assessments=[assessment],
    )

    saved = repository.save(decision)
    assert saved == decision

    fetched = repository.get("proj-1", decision.decision_id)
    assert fetched.decision_id == decision.decision_id
    assert fetched.project_id == "proj-1"
    assert fetched.publication_id == pub_id
    assert fetched.stage is ScreeningStage.TITLE_ABSTRACT
    assert fetched.outcome is ScreeningOutcome.INCLUDE
    assert fetched.reviewer_id == "reviewer-1"
    assert fetched.rationale == "Clear inclusion"
    assert len(fetched.criterion_assessments) == 1
    assert fetched.criterion_assessments[0].criterion_id == cid
    assert fetched.criterion_assessments[0].criterion_is_required is True


def test_new_decision_persists_v2_description_snapshot(
    repository: SqliteScreeningDecisionRepository,
) -> None:
    assessment = CriterionAssessment(
        criterion_id=uuid4(),
        criterion_name="Criterion with description",
        criterion_description="A historical explanation.",
        criterion_type=ScreeningCriterionType.INCLUSION,
        criterion_stage=ScreeningCriterionStage.TITLE_ABSTRACT,
        criterion_is_required=True,
        assessment_value=CriterionAssessmentValue.MET,
    )
    decision = ScreeningDecision(
        project_id="project-v2",
        publication_id=uuid4(),
        stage=ScreeningStage.TITLE_ABSTRACT,
        outcome=ScreeningOutcome.INCLUDE,
        reviewer_id="reviewer",
        criterion_assessments=[assessment],
    )

    repository.save(decision)

    restored = repository.get("project-v2", decision.decision_id)
    assert restored.criterion_snapshot_schema_version == 2
    assert restored.criterion_assessments[0].criterion_description == ("A historical explanation.")


def test_legacy_v1_decision_migrates_without_backfilling_description(tmp_path) -> None:
    database_path = tmp_path / "legacy-screening.db"
    decision_id = uuid4()
    criterion_id = uuid4()
    publication_id = uuid4()
    migrations = Path(__file__).parents[3] / "migrations"
    with sqlite3.connect(database_path) as connection:
        connection.execute("CREATE TABLE schema_migrations (version TEXT PRIMARY KEY, applied_at TEXT)")
        for migration in sorted(migrations.glob("*.sql")):
            if migration.name == "0015_screening_audit_reporting.sql":
                continue
            connection.executescript(migration.read_text(encoding="utf-8"))
            connection.execute(
                "INSERT INTO schema_migrations (version, applied_at) VALUES (?, CURRENT_TIMESTAMP)",
                (migration.name,),
            )
        connection.execute(
            """INSERT INTO screening_decisions (
                decision_id, project_id, publication_id, stage, outcome, reviewer_id,
                rationale, decided_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                str(decision_id),
                "legacy-project",
                str(publication_id),
                "title_abstract",
                "exclude",
                "reviewer",
                None,
                "2026-01-01T00:00:00+00:00",
            ),
        )
        connection.execute(
            """INSERT INTO screening_criterion_assessments (
                decision_id, criterion_id, criterion_name, criterion_type,
                criterion_stage, criterion_is_required, assessment_value, notes,
                evaluation_mode, metadata_rule, evaluated_metadata_value
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                str(decision_id),
                str(criterion_id),
                "Old criterion",
                "inclusion",
                "title_abstract",
                1,
                "not_met",
                None,
                "manual",
                None,
                None,
            ),
        )

    restored = SqliteScreeningDecisionRepository(database_path).get("legacy-project", decision_id)
    assert restored.criterion_snapshot_schema_version == 1
    assert restored.criterion_assessments[0].criterion_description is None


def test_survive_db_reopen(tmp_path) -> None:
    db_path = tmp_path / "test_reopen.db"
    repo1 = SqliteScreeningDecisionRepository(db_path)

    decision = ScreeningDecision(
        project_id="proj-reopen",
        publication_id=uuid4(),
        stage=ScreeningStage.FULL_TEXT,
        outcome=ScreeningOutcome.EXCLUDE,
        reviewer_id="reviewer-reopen",
        rationale="Out of scope",
    )
    repo1.save(decision)

    # Open fresh repository instance on same database file
    repo2 = SqliteScreeningDecisionRepository(db_path)
    fetched = repo2.get("proj-reopen", decision.decision_id)
    assert fetched.decision_id == decision.decision_id
    assert fetched.outcome is ScreeningOutcome.EXCLUDE


def test_get_not_found(repository: SqliteScreeningDecisionRepository) -> None:
    with pytest.raises(DecisionNotFoundError):
        repository.get("proj-1", uuid4())


def test_project_isolation(repository: SqliteScreeningDecisionRepository) -> None:
    decision = ScreeningDecision(
        project_id="proj-1",
        publication_id=uuid4(),
        stage=ScreeningStage.TITLE_ABSTRACT,
        outcome=ScreeningOutcome.INCLUDE,
        reviewer_id="reviewer-1",
    )
    repository.save(decision)

    # Attempt fetching decision using a different project_id
    with pytest.raises(DecisionNotFoundError):
        repository.get("proj-2", decision.decision_id)


def test_append_only_history_and_latest_decision(
    repository: SqliteScreeningDecisionRepository,
) -> None:
    pub_id = uuid4()
    project_id = "proj-history"
    stage = ScreeningStage.TITLE_ABSTRACT
    reviewer_id = "reviewer-main"

    # First decision: UNCERTAIN
    d1 = ScreeningDecision(
        project_id=project_id,
        publication_id=pub_id,
        stage=stage,
        outcome=ScreeningOutcome.UNCERTAIN,
        reviewer_id=reviewer_id,
        rationale="Need full text check",
        decided_at=datetime(2026, 8, 10, 10, 0, 0, tzinfo=timezone.utc),
    )
    repository.save(d1)

    # Second decision (update/re-screening): INCLUDE
    d2 = ScreeningDecision(
        project_id=project_id,
        publication_id=pub_id,
        stage=stage,
        outcome=ScreeningOutcome.INCLUDE,
        reviewer_id=reviewer_id,
        rationale="Approved after review",
        decided_at=datetime(2026, 8, 10, 11, 0, 0, tzinfo=timezone.utc),
    )
    repository.save(d2)

    # History should contain both decisions ordered DESC by timestamp
    history = repository.list_history(project_id, pub_id, stage, reviewer_id)
    assert len(history) == 2
    assert history[0].decision_id == d2.decision_id
    assert history[1].decision_id == d1.decision_id

    # Latest decision should be d2
    latest = repository.get_latest_decision(project_id, pub_id, stage, reviewer_id)
    assert latest is not None
    assert latest.decision_id == d2.decision_id
    assert latest.outcome is ScreeningOutcome.INCLUDE


def test_stage_separated_histories(
    repository: SqliteScreeningDecisionRepository,
) -> None:
    pub_id = uuid4()
    project_id = "proj-stages"
    reviewer_id = "reviewer-1"

    d_title = ScreeningDecision(
        project_id=project_id,
        publication_id=pub_id,
        stage=ScreeningStage.TITLE_ABSTRACT,
        outcome=ScreeningOutcome.INCLUDE,
        reviewer_id=reviewer_id,
    )
    repository.save(d_title)

    d_fulltext = ScreeningDecision(
        project_id=project_id,
        publication_id=pub_id,
        stage=ScreeningStage.FULL_TEXT,
        outcome=ScreeningOutcome.EXCLUDE,
        reviewer_id=reviewer_id,
    )
    repository.save(d_fulltext)

    title_latest = repository.get_latest_decision(project_id, pub_id, ScreeningStage.TITLE_ABSTRACT, reviewer_id)
    full_latest = repository.get_latest_decision(project_id, pub_id, ScreeningStage.FULL_TEXT, reviewer_id)

    assert title_latest is not None and title_latest.decision_id == d_title.decision_id
    assert full_latest is not None and full_latest.decision_id == d_fulltext.decision_id
