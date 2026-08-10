from datetime import datetime, timedelta, timezone
from typing import cast
from uuid import UUID

import pytest

from app.domain.duplicate_review import DuplicateDecision, DuplicateGroupReviewDecision
from app.domain.identifiers import Identifier, IdentifierType
from app.domain.provenance import ProvenanceEntry
from app.domain.publication import Publication
from app.domain.screening import (
    CriterionAssessmentValue,
    ScreeningCriterion,
    ScreeningCriterionStage,
    ScreeningCriterionType,
    ScreeningDecision,
    ScreeningOutcome,
    ScreeningStage,
)
from app.repositories.duplicate_review_decision_repository import InMemoryDuplicateReviewDecisionRepository
from app.repositories.project_publication_repository import SqliteProjectPublicationRepository
from app.repositories.screening_criterion_repository import SqliteScreeningCriterionRepository
from app.repositories.screening_decision_repository import (
    ScreeningDecisionRepository,
    SqliteScreeningDecisionRepository,
)
from app.services.duplicate_group_builder import DuplicateGroupBuilder
from app.services.screening_decision_service import CriterionAssessmentInput, ScreeningDecisionService
from app.services.screening_input_service import ScreeningInputReadinessStatus, ScreeningInputService
from app.services.title_abstract_screening_service import (
    ScreeningPublicationNotEligibleError,
    ScreeningWorkflowNotReadyError,
    TitleAbstractScreeningService,
    TitleAbstractScreeningStatus,
)


def _publication(number: int, doi: str | None = None) -> Publication:
    identifiers = [] if doi is None else [Identifier(type=IdentifierType.DOI, value=doi)]
    return Publication(
        record_id=UUID(f"00000000-0000-0000-0000-{number:012d}"),
        title=f"Publication {number}",
        identifiers=identifiers,
        provenance=[ProvenanceEntry(source="test", source_record_id=str(number))],
    )


def _environment(tmp_path, publications):
    database = tmp_path / "workflow.db"
    pubs = SqliteProjectPublicationRepository(database)
    pubs.add_publications("lean_energy", publications)
    criteria = SqliteScreeningCriterionRepository(database)
    decisions = SqliteScreeningDecisionRepository(database)
    reviews = InMemoryDuplicateReviewDecisionRepository()
    input_service = ScreeningInputService(pubs, reviews)
    decision_service = ScreeningDecisionService(decisions, criteria, pubs)
    service = TitleAbstractScreeningService(input_service, criteria, decisions, decision_service)
    return service, pubs, criteria, decisions, reviews, database


def test_ready_empty_and_deterministic_paginated_records(tmp_path) -> None:
    service, *_ = _environment(tmp_path, [])
    assert service.get_overview("lean_energy", " reviewer ").progress.total == 0
    service, *_ = _environment(tmp_path / "second", [_publication(3), _publication(1), _publication(2)])
    first = service.list_records("lean_energy", "reviewer", offset=1, limit=2)
    second = service.list_records("lean_energy", "reviewer", offset=1, limit=2)
    assert first == second
    assert [item.publication.record_id for item in first.items] == [
        _publication(2).record_id,
        _publication(3).record_id,
    ]


def test_pending_blocks_records_and_write_with_typed_reason(tmp_path) -> None:
    publications = [_publication(1, "10.1/x"), _publication(2, "10.1/x")]
    service, *_ = _environment(tmp_path, publications)
    overview = service.get_overview("lean_energy", "reviewer")
    assert overview.progress is None
    assert overview.screening_input.readiness_status is ScreeningInputReadinessStatus.UNRESOLVED_DUPLICATES
    with pytest.raises(ScreeningWorkflowNotReadyError):
        service.list_records("lean_energy", "reviewer")
    with pytest.raises(ScreeningWorkflowNotReadyError):
        service.record_decision(
            "lean_energy", publications[0].record_id, "reviewer", ScreeningOutcome.INCLUDE, None, []
        )


def test_batch_latest_status_filter_progress_and_reviewer_specificity(tmp_path) -> None:
    publications = [_publication(1), _publication(2), _publication(3), _publication(4)]
    service, _, _, decisions, *_ = _environment(tmp_path, publications)
    base = datetime(2026, 8, 10, tzinfo=timezone.utc)
    decisions.save(
        ScreeningDecision(
            publication_id=publications[0].record_id,
            project_id="lean_energy",
            stage="title_abstract",
            outcome=ScreeningOutcome.INCLUDE,
            reviewer_id="alice",
            decided_at=base,
        )
    )
    decisions.save(
        ScreeningDecision(
            publication_id=publications[0].record_id,
            project_id="lean_energy",
            stage="title_abstract",
            outcome=ScreeningOutcome.EXCLUDE,
            reviewer_id="alice",
            decided_at=base + timedelta(seconds=1),
        )
    )
    decisions.save(
        ScreeningDecision(
            publication_id=publications[1].record_id,
            project_id="lean_energy",
            stage="title_abstract",
            outcome=ScreeningOutcome.UNCERTAIN,
            reviewer_id="alice",
            decided_at=base,
        )
    )
    decisions.save(
        ScreeningDecision(
            publication_id=publications[2].record_id,
            project_id="lean_energy",
            stage="title_abstract",
            outcome=ScreeningOutcome.INCLUDE,
            reviewer_id="bob",
            decided_at=base,
        )
    )

    alice = service.get_overview("lean_energy", "alice").progress
    bob = service.get_overview("lean_energy", "bob").progress
    assert (alice.total, alice.unscreened, alice.excluded, alice.uncertain, alice.completed) == (4, 2, 1, 1, 2)
    assert (bob.unscreened, bob.included) == (3, 1)
    excluded = service.list_records("lean_energy", "alice", status_filter=TitleAbstractScreeningStatus.EXCLUDED)
    assert [item.publication.record_id for item in excluded.items] == [publications[0].record_id]
    assert excluded.items[0].latest_decision.outcome is ScreeningOutcome.EXCLUDE
    assert (
        len(decisions.list_history("lean_energy", publications[0].record_id, ScreeningStage.TITLE_ABSTRACT, "alice"))
        == 2
    )


def test_many_records_use_one_batch_decision_read(tmp_path) -> None:
    publications = [_publication(number) for number in range(1, 101)]
    service, _, criteria, decisions, *_ = _environment(tmp_path, publications)

    class CountingRepository:
        def __init__(self):
            self.calls = 0

        def list_by_project(self, project_id, stage=None):
            self.calls += 1
            return decisions.list_by_project(project_id, stage)

    counting = CountingRepository()
    batch_service = TitleAbstractScreeningService(
        service._input,
        criteria,
        cast(ScreeningDecisionRepository, counting),
        service._decision_service,
    )

    result = batch_service.list_records("lean_energy", "alice", limit=100)

    assert len(result.items) == 100
    assert counting.calls == 1


def test_criteria_scope_and_required_validation_delegation(tmp_path) -> None:
    publication = _publication(1)
    service, _, criteria, *_ = _environment(tmp_path, [publication])
    eligible = []
    for stage, active in (
        (ScreeningCriterionStage.TITLE_ABSTRACT, True),
        (ScreeningCriterionStage.BOTH, True),
        (ScreeningCriterionStage.FULL_TEXT, True),
        (ScreeningCriterionStage.TITLE_ABSTRACT, False),
    ):
        eligible.append(
            criteria.create(
                ScreeningCriterion(
                    project_id="lean_energy",
                    name=f"Criterion {len(eligible)}",
                    criterion_type=ScreeningCriterionType.INCLUSION,
                    screening_stage=stage,
                    display_order=len(eligible),
                    is_active=active,
                    is_required=active and stage is ScreeningCriterionStage.TITLE_ABSTRACT,
                )
            )
        )
    assert [item.criterion_id for item in service.get_overview("lean_energy", "alice").criteria] == [
        eligible[0].criterion_id,
        eligible[1].criterion_id,
    ]
    with pytest.raises(ValueError, match="Missing required assessment"):
        service.record_decision("lean_energy", publication.record_id, "alice", ScreeningOutcome.INCLUDE, None, [])
    saved = service.record_decision(
        "lean_energy",
        publication.record_id,
        "alice",
        ScreeningOutcome.INCLUDE,
        None,
        [
            CriterionAssessmentInput(
                criterion_id=eligible[0].criterion_id, assessment_value=CriterionAssessmentValue.MET
            )
        ],
    )
    assert saved.stage.value == "title_abstract"


def test_approved_duplicate_accepts_only_canonical_and_does_not_mutate_collection(tmp_path) -> None:
    publications = [_publication(2, "10.1/x"), _publication(1, "10.1/x")]
    service, pubs, _, _, reviews, _ = _environment(tmp_path, publications)
    group = DuplicateGroupBuilder().build(publications)[0]
    reviews.save_decision(
        "lean_energy", str(group.group_id), DuplicateGroupReviewDecision(decision=DuplicateDecision.APPROVE)
    )
    before = pubs.get_publications("lean_energy")
    with pytest.raises(ScreeningPublicationNotEligibleError):
        service.record_decision("lean_energy", publications[0].record_id, "alice", ScreeningOutcome.INCLUDE, None, [])
    decision = service.record_decision(
        "lean_energy", publications[1].record_id, "alice", ScreeningOutcome.INCLUDE, None, []
    )
    assert decision.publication_id == min(item.record_id for item in publications)
    assert pubs.get_publications("lean_energy") == before


def test_reopen_persistence_restores_progress_and_project_isolation(tmp_path) -> None:
    publication = _publication(1)
    service, pubs, criteria, decisions, reviews, database = _environment(tmp_path, [publication])
    service.record_decision("lean_energy", publication.record_id, "alice", ScreeningOutcome.UNCERTAIN, None, [])
    reopened = TitleAbstractScreeningService(
        ScreeningInputService(SqliteProjectPublicationRepository(database), reviews),
        SqliteScreeningCriterionRepository(database),
        SqliteScreeningDecisionRepository(database),
        ScreeningDecisionService(
            SqliteScreeningDecisionRepository(database),
            SqliteScreeningCriterionRepository(database),
            SqliteProjectPublicationRepository(database),
        ),
    )
    assert reopened.get_overview("lean_energy", "alice").progress.uncertain == 1
    with pytest.raises(ScreeningPublicationNotEligibleError):
        reopened.get_record("ai_architecture", publication.record_id, "alice")


def test_blank_reviewer_is_rejected(tmp_path) -> None:
    service, *_ = _environment(tmp_path, [])
    with pytest.raises(ValueError, match="reviewer_id"):
        service.get_overview("lean_energy", "   ")
