from pathlib import Path

from app.domain.duplicate_review import DuplicateDecision, DuplicateGroupReviewDecision
from app.repositories.duplicate_review_decision_repository import SqliteDuplicateReviewDecisionRepository


def test_sqlite_decision_repo_save_and_get_approve(tmp_path: Path) -> None:
    db_path = tmp_path / "test_decisions.db"
    repo = SqliteDuplicateReviewDecisionRepository(db_path)

    decision = DuplicateGroupReviewDecision(
        decision=DuplicateDecision.APPROVE,
        rationale="Verified match",
    )
    repo.save_decision("proj_1", "grp_100", decision)

    stored = repo.get_decision("proj_1", "grp_100")
    assert stored is not None
    assert stored.decision == DuplicateDecision.APPROVE
    assert stored.rationale == "Verified match"


def test_sqlite_decision_repo_save_and_get_reject(tmp_path: Path) -> None:
    db_path = tmp_path / "test_decisions.db"
    repo = SqliteDuplicateReviewDecisionRepository(db_path)

    decision = DuplicateGroupReviewDecision(
        decision=DuplicateDecision.REJECT,
        rationale=None,
    )
    repo.save_decision("proj_1", "grp_101", decision)

    stored = repo.get_decision("proj_1", "grp_101")
    assert stored is not None
    assert stored.decision == DuplicateDecision.REJECT
    assert stored.rationale is None


def test_sqlite_decision_repo_pending_for_undecided(tmp_path: Path) -> None:
    db_path = tmp_path / "test_decisions.db"
    repo = SqliteDuplicateReviewDecisionRepository(db_path)

    stored = repo.get_decision("proj_1", "unknown_grp")
    assert stored is None


def test_sqlite_decision_repo_overwrite_decision(tmp_path: Path) -> None:
    db_path = tmp_path / "test_decisions.db"
    repo = SqliteDuplicateReviewDecisionRepository(db_path)

    first_decision = DuplicateGroupReviewDecision(
        decision=DuplicateDecision.APPROVE,
        rationale="Initial approval",
    )
    repo.save_decision("proj_1", "grp_200", first_decision)

    second_decision = DuplicateGroupReviewDecision(
        decision=DuplicateDecision.REJECT,
        rationale="Updated to reject after review",
    )
    repo.save_decision("proj_1", "grp_200", second_decision)

    stored = repo.get_decision("proj_1", "grp_200")
    assert stored is not None
    assert stored.decision == DuplicateDecision.REJECT
    assert stored.rationale == "Updated to reject after review"


def test_sqlite_decision_repo_project_isolation(tmp_path: Path) -> None:
    db_path = tmp_path / "test_decisions.db"
    repo = SqliteDuplicateReviewDecisionRepository(db_path)

    decision1 = DuplicateGroupReviewDecision(
        decision=DuplicateDecision.APPROVE,
        rationale="Approved in Project 1",
    )
    decision2 = DuplicateGroupReviewDecision(
        decision=DuplicateDecision.REJECT,
        rationale="Rejected in Project 2",
    )

    repo.save_decision("proj_1", "shared_grp_id", decision1)
    repo.save_decision("proj_2", "shared_grp_id", decision2)

    stored1 = repo.get_decision("proj_1", "shared_grp_id")
    stored2 = repo.get_decision("proj_2", "shared_grp_id")

    assert stored1 is not None and stored1.decision == DuplicateDecision.APPROVE
    assert stored1.rationale == "Approved in Project 1"
    assert stored2 is not None and stored2.decision == DuplicateDecision.REJECT
    assert stored2.rationale == "Rejected in Project 2"


def test_sqlite_decision_repo_persistence_across_repository_instances(tmp_path: Path) -> None:
    db_path = tmp_path / "test_decisions.db"

    repo1 = SqliteDuplicateReviewDecisionRepository(db_path)
    decision = DuplicateGroupReviewDecision(
        decision=DuplicateDecision.APPROVE,
        rationale="Persistent rationale across instances",
    )
    repo1.save_decision("proj_persist", "grp_persist", decision)

    # Re-instantiate repository pointing to same database
    repo2 = SqliteDuplicateReviewDecisionRepository(db_path)
    stored = repo2.get_decision("proj_persist", "grp_persist")

    assert stored is not None
    assert stored.decision == DuplicateDecision.APPROVE
    assert stored.rationale == "Persistent rationale across instances"
