from pathlib import Path
from uuid import uuid4

from app.domain.pre_screening import (
    PreScreeningDecision,
    PreScreeningRemovalReason,
    PreScreeningStatus,
)
from app.repositories.pre_screening_decision_repository import (
    SqlitePreScreeningDecisionRepository,
)


def test_save_and_retrieve_latest_decision(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    repo = SqlitePreScreeningDecisionRepository(db_path)

    project_id = "proj_1"
    record_id = uuid4()
    import_id = uuid4()

    decision_1 = PreScreeningDecision(
        project_id=project_id,
        record_id=record_id,
        import_id=import_id,
        status=PreScreeningStatus.REMOVED,
        reason=PreScreeningRemovalReason.RETRIEVAL_ARTEFACT,
        notes="Non-academic content",
        reviewer_id="reviewer_1",
    )
    repo.save_decision(decision_1)

    latest = repo.get_latest_decision(project_id, record_id)
    assert latest is not None
    assert latest.decision_id == decision_1.decision_id
    assert latest.status == PreScreeningStatus.REMOVED
    assert latest.reason == PreScreeningRemovalReason.RETRIEVAL_ARTEFACT
    assert latest.notes == "Non-academic content"
    assert latest.reviewer_id == "reviewer_1"

    # Restore decision
    decision_2 = PreScreeningDecision(
        project_id=project_id,
        record_id=record_id,
        import_id=import_id,
        status=PreScreeningStatus.RETAINED,
        reviewer_id="reviewer_2",
    )
    repo.save_decision(decision_2)

    latest_after_restore = repo.get_latest_decision(project_id, record_id)
    assert latest_after_restore is not None
    assert latest_after_restore.decision_id == decision_2.decision_id
    assert latest_after_restore.status == PreScreeningStatus.RETAINED
    assert latest_after_restore.reason is None


def test_list_decisions_for_project_and_import(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    repo = SqlitePreScreeningDecisionRepository(db_path)

    project_id = "proj_test"
    import_1 = uuid4()
    import_2 = uuid4()

    rec1 = uuid4()
    rec2 = uuid4()

    d1 = PreScreeningDecision(
        project_id=project_id,
        record_id=rec1,
        import_id=import_1,
        status=PreScreeningStatus.REMOVED,
        reason=PreScreeningRemovalReason.CLEARLY_OUTSIDE_SCOPE,
    )
    d2 = PreScreeningDecision(
        project_id=project_id,
        record_id=rec2,
        import_id=import_2,
        status=PreScreeningStatus.REMOVED,
        reason=PreScreeningRemovalReason.INCOMPLETE_RECORD,
    )

    repo.save_decision(d1)
    repo.save_decision(d2)

    all_proj = repo.list_decisions_for_project(project_id)
    assert len(all_proj) == 2

    imp1_decisions = repo.list_decisions_for_import(project_id, import_1)
    assert len(imp1_decisions) == 1
    assert imp1_decisions[0].record_id == rec1

    imp2_decisions = repo.list_decisions_for_import(project_id, import_2)
    assert len(imp2_decisions) == 1
    assert imp2_decisions[0].record_id == rec2


def test_delete_for_project(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    repo = SqlitePreScreeningDecisionRepository(db_path)

    project_id = "proj_to_delete"
    d = PreScreeningDecision(
        project_id=project_id,
        record_id=uuid4(),
        import_id=uuid4(),
        status=PreScreeningStatus.REMOVED,
        reason=PreScreeningRemovalReason.CLEARLY_OUTSIDE_SCOPE,
    )
    repo.save_decision(d)
    assert len(repo.list_decisions_for_project(project_id)) == 1

    repo.delete_for_project(project_id)
    assert len(repo.list_decisions_for_project(project_id)) == 0
