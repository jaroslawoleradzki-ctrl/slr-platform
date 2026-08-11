from datetime import datetime, timedelta, timezone
from uuid import UUID

import pytest

from app.domain.conflict_resolution import PublicationScreeningStatus, ResolvedOutcome, compute_decision_set_key
from app.domain.publication import Publication
from app.domain.screening import ScreeningDecision, ScreeningOutcome, ScreeningStage
from app.repositories.conflict_resolution_repository import SqliteConflictResolutionRepository
from app.repositories.duplicate_review_decision_repository import InMemoryDuplicateReviewDecisionRepository
from app.repositories.project_publication_repository import SqliteProjectPublicationRepository
from app.repositories.screening_decision_repository import SqliteScreeningDecisionRepository
from app.repositories.screening_reporting_repository import ScreeningReportingRepository
from app.repositories.screening_reviewer_assignment_repository import SqliteScreeningReviewerAssignmentRepository
from app.services.conflict_resolution_service import ConflictResolutionService, ConflictResolutionStaleError
from app.services.multi_reviewer_screening_service import MultiReviewerScreeningService, ScreeningConflictStatus
from app.services.screening_input_service import ScreeningInputService


def test_resolution_is_append_only_and_becomes_stale_when_a_decision_changes(tmp_path):
    db = tmp_path / "resolution.db"
    publication = Publication(record_id=UUID("00000000-0000-0000-0000-000000000001"), title="Paper")
    pubs = SqliteProjectPublicationRepository(db)
    pubs.add_publications("lean_energy", [publication])
    decisions = SqliteScreeningDecisionRepository(db)
    assignments = SqliteScreeningReviewerAssignmentRepository(db)
    repo = SqliteConflictResolutionRepository(db)
    multi = MultiReviewerScreeningService(
        assignments,
        ScreeningReportingRepository(db),
        ScreeningInputService(pubs, InMemoryDuplicateReviewDecisionRepository()),
        repo,
    )
    multi.roster("lean_energy", ScreeningStage.TITLE_ABSTRACT, ["a", "b"])
    now = datetime(2026, 8, 11, tzinfo=timezone.utc)
    decisions.save(
        ScreeningDecision(
            project_id="lean_energy",
            publication_id=publication.record_id,
            stage=ScreeningStage.TITLE_ABSTRACT,
            outcome=ScreeningOutcome.INCLUDE,
            reviewer_id="a",
            decided_at=now,
        )
    )
    decisions.save(
        ScreeningDecision(
            project_id="lean_energy",
            publication_id=publication.record_id,
            stage=ScreeningStage.TITLE_ABSTRACT,
            outcome=ScreeningOutcome.EXCLUDE,
            reviewer_id="b",
            decided_at=now + timedelta(seconds=1),
        )
    )
    state = multi.publication_state(
        "lean_energy", publication.record_id, ScreeningStage.TITLE_ABSTRACT, reveal_decisions=True
    )
    assert state and state.status is ScreeningConflictStatus.CONFLICT
    service = ConflictResolutionService(multi, repo)
    first = service.resolve(
        "lean_energy",
        publication.record_id,
        ScreeningStage.TITLE_ABSTRACT,
        ResolvedOutcome.INCLUDE,
        "adjudicator",
        "Reasoned decision",
        state.current_decision_set_key,
    )
    assert (
        multi.project_outcome("lean_energy", publication.record_id, ScreeningStage.TITLE_ABSTRACT).status
        is PublicationScreeningStatus.RESOLVED
    )
    decisions.save(
        ScreeningDecision(
            project_id="lean_energy",
            publication_id=publication.record_id,
            stage=ScreeningStage.TITLE_ABSTRACT,
            outcome=ScreeningOutcome.UNCERTAIN,
            reviewer_id="b",
            decided_at=now + timedelta(seconds=2),
        )
    )
    changed = multi.publication_state("lean_energy", publication.record_id, ScreeningStage.TITLE_ABSTRACT)
    assert changed and changed.status is ScreeningConflictStatus.STALE_RESOLUTION
    assert (
        service.history("lean_energy", publication.record_id, ScreeningStage.TITLE_ABSTRACT)[1][0].resolution_id
        == first.resolution_id
    )
    with pytest.raises(ConflictResolutionStaleError):
        service.resolve(
            "lean_energy",
            publication.record_id,
            ScreeningStage.TITLE_ABSTRACT,
            ResolvedOutcome.EXCLUDE,
            "adjudicator",
            "New reason",
            state.current_decision_set_key,
        )


def test_decision_set_key_is_deterministic():
    publication = UUID("00000000-0000-0000-0000-000000000001")
    first = compute_decision_set_key("p", publication, ScreeningStage.TITLE_ABSTRACT, ("b", "a"), {})
    second = compute_decision_set_key("p", publication, ScreeningStage.TITLE_ABSTRACT, ("a", "b"), {})
    assert first == second


def test_roster_add_and_remove_stale_resolutions_and_reresolution_is_append_only(tmp_path):
    db = tmp_path / "roster-stale.db"
    paper = Publication(record_id=UUID("00000000-0000-0000-0000-000000000010"), title="Roster paper")
    publications = SqliteProjectPublicationRepository(db)
    publications.add_publications("lean_energy", [paper])
    decisions = SqliteScreeningDecisionRepository(db)
    assignments = SqliteScreeningReviewerAssignmentRepository(db)
    resolutions = SqliteConflictResolutionRepository(db)
    multi = MultiReviewerScreeningService(
        assignments,
        ScreeningReportingRepository(db),
        ScreeningInputService(publications, InMemoryDuplicateReviewDecisionRepository()),
        resolutions,
    )
    service = ConflictResolutionService(multi, resolutions)
    now = datetime(2026, 8, 11, tzinfo=timezone.utc)
    multi.roster("lean_energy", ScreeningStage.TITLE_ABSTRACT, ["a", "b"])
    for index, (reviewer, outcome) in enumerate(
        (("a", ScreeningOutcome.INCLUDE), ("b", ScreeningOutcome.EXCLUDE))
    ):
        decisions.save(
            ScreeningDecision(
                project_id="lean_energy",
                publication_id=paper.record_id,
                stage=ScreeningStage.TITLE_ABSTRACT,
                outcome=outcome,
                reviewer_id=reviewer,
                decided_at=now + timedelta(seconds=index),
            )
        )
    original = multi.publication_state("lean_energy", paper.record_id, ScreeningStage.TITLE_ABSTRACT)
    assert original is not None
    first = service.resolve(
        "lean_energy", paper.record_id, ScreeningStage.TITLE_ABSTRACT,
        ResolvedOutcome.INCLUDE, "resolver", "First resolution", original.current_decision_set_key,
    )

    multi.roster("lean_energy", ScreeningStage.TITLE_ABSTRACT, ["a", "b", "c"])
    after_add = multi.publication_state("lean_energy", paper.record_id, ScreeningStage.TITLE_ABSTRACT)
    assert after_add is not None
    assert after_add.status is ScreeningConflictStatus.INCOMPLETE
    assert after_add.current_decision_set_key != first.decision_set_key
    decisions.save(
        ScreeningDecision(
            project_id="lean_energy", publication_id=paper.record_id,
            stage=ScreeningStage.TITLE_ABSTRACT, outcome=ScreeningOutcome.UNCERTAIN,
            reviewer_id="c", decided_at=now + timedelta(seconds=3),
        )
    )
    three_reviewer = multi.publication_state("lean_energy", paper.record_id, ScreeningStage.TITLE_ABSTRACT)
    assert three_reviewer is not None and three_reviewer.status is ScreeningConflictStatus.STALE_RESOLUTION
    second = service.resolve(
        "lean_energy", paper.record_id, ScreeningStage.TITLE_ABSTRACT,
        ResolvedOutcome.UNCERTAIN, "resolver-2", "Three reviewer resolution",
        three_reviewer.current_decision_set_key,
    )

    multi.roster("lean_energy", ScreeningStage.TITLE_ABSTRACT, ["a", "b"])
    after_remove = multi.publication_state("lean_energy", paper.record_id, ScreeningStage.TITLE_ABSTRACT)
    assert after_remove is not None and after_remove.status is ScreeningConflictStatus.STALE_RESOLUTION
    assert after_remove.current_decision_set_key != second.decision_set_key
    third = service.resolve(
        "lean_energy", paper.record_id, ScreeningStage.TITLE_ABSTRACT,
        ResolvedOutcome.EXCLUDE, "resolver-3", "Resolution after roster removal",
        after_remove.current_decision_set_key,
    )
    history = resolutions.history("lean_energy", paper.record_id, ScreeningStage.TITLE_ABSTRACT)
    assert [item.resolution_id for item in history] == [third.resolution_id, second.resolution_id, first.resolution_id]
    assert len({item.resolution_id for item in history}) == 3
