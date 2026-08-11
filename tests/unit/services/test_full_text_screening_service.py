from datetime import datetime, timedelta, timezone
from uuid import UUID

import pytest

from app.domain.full_text_screening import FullTextAvailabilityStatus
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
from app.repositories.full_text_availability_repository import SqliteFullTextAvailabilityRepository
from app.repositories.project_publication_repository import SqliteProjectPublicationRepository
from app.repositories.screening_criterion_repository import SqliteScreeningCriterionRepository
from app.repositories.screening_decision_repository import SqliteScreeningDecisionRepository
from app.services.full_text_screening_service import (
    FullTextPublicationNotEligibleError,
    FullTextScreeningService,
    FullTextScreeningStatus,
    FullTextWorkflowNotReadyError,
)
from app.services.screening_decision_service import CriterionAssessmentInput, ScreeningDecisionService
from app.services.screening_input_service import ScreeningInputService


def _publication(number: int) -> Publication:
    return Publication(
        record_id=UUID(f"00000000-0000-0000-0000-{number:012d}"),
        title=f"Paper {number}", publication_year=2024,
    )


def _environment(tmp_path):
    database = tmp_path / "full-text.db"
    publications = SqliteProjectPublicationRepository(database)
    criteria = SqliteScreeningCriterionRepository(database)
    decisions = SqliteScreeningDecisionRepository(database)
    availability = SqliteFullTextAvailabilityRepository(database)
    input_service = ScreeningInputService(publications, InMemoryDuplicateReviewDecisionRepository())
    decision_service = ScreeningDecisionService(decisions, criteria, publications)
    service = FullTextScreeningService(input_service, criteria, decisions, decision_service, availability)
    return service, publications, criteria, decisions, availability


def _include_title_abstract(decisions, publication, reviewer="alice", outcome=ScreeningOutcome.INCLUDE, at=None):
    decisions.save(ScreeningDecision(
        project_id="lean_energy", publication_id=publication.record_id,
        stage=ScreeningStage.TITLE_ABSTRACT, outcome=outcome, reviewer_id=reviewer,
        decided_at=at or datetime.now(timezone.utc),
    ))


def test_eligibility_is_reviewer_specific_and_latest_decision_wins(tmp_path) -> None:
    service, publications, _, decisions, _ = _environment(tmp_path)
    paper = _publication(1)
    publications.add_publications("lean_energy", [paper])
    now = datetime(2026, 8, 11, tzinfo=timezone.utc)
    _include_title_abstract(decisions, paper, "bob", at=now)
    assert service.get_overview("lean_energy", "alice").readiness.ready is False
    _include_title_abstract(decisions, paper, "alice", at=now)
    assert service.get_overview("lean_energy", "alice").readiness.ready is True
    _include_title_abstract(decisions, paper, "alice", ScreeningOutcome.EXCLUDE, now + timedelta(seconds=1))
    assert service.get_overview("lean_energy", "alice").readiness.ready is False


def test_loss_and_restoration_of_eligibility_keeps_full_text_history_and_availability(tmp_path) -> None:
    service, publications, _, decisions, availability = _environment(tmp_path)
    paper = _publication(1)
    publications.add_publications("lean_energy", [paper])
    now = datetime(2026, 8, 11, tzinfo=timezone.utc)
    _include_title_abstract(decisions, paper, at=now)
    full_text = service.record_decision("lean_energy", paper.record_id, "alice", ScreeningOutcome.INCLUDE, None, [], [])
    service.save_availability("lean_energy", paper.record_id, "alice", FullTextAvailabilityStatus.AVAILABLE, "https://example.test/text", None)
    _include_title_abstract(decisions, paper, outcome=ScreeningOutcome.EXCLUDE, at=now + timedelta(seconds=1))
    assert service.get_overview("lean_energy", "alice").readiness.ready is False
    assert decisions.get("lean_energy", full_text.decision_id).outcome is ScreeningOutcome.INCLUDE
    assert availability.get("lean_energy", paper.record_id).status is FullTextAvailabilityStatus.AVAILABLE
    with pytest.raises((FullTextPublicationNotEligibleError, FullTextWorkflowNotReadyError)):
        service.record_decision("lean_energy", paper.record_id, "alice", ScreeningOutcome.INCLUDE, None, [], [])
    _include_title_abstract(decisions, paper, outcome=ScreeningOutcome.INCLUDE, at=now + timedelta(seconds=2))
    item = service.list_records("lean_energy", "alice").items[0]
    assert item.status is FullTextScreeningStatus.INCLUDED


def test_full_text_exclusion_requires_a_valid_same_decision_reason(tmp_path) -> None:
    service, publications, criteria, decisions, _ = _environment(tmp_path)
    paper = _publication(1)
    publications.add_publications("lean_energy", [paper])
    _include_title_abstract(decisions, paper)
    inclusion = criteria.create(ScreeningCriterion(project_id="lean_energy", name="Population", criterion_type=ScreeningCriterionType.INCLUSION, screening_stage=ScreeningCriterionStage.FULL_TEXT))
    exclusion = criteria.create(ScreeningCriterion(project_id="lean_energy", name="Wrong design", criterion_type=ScreeningCriterionType.EXCLUSION, screening_stage=ScreeningCriterionStage.FULL_TEXT, is_required=False))
    with pytest.raises(ValueError, match="requires at least one"):
        service.record_decision("lean_energy", paper.record_id, "alice", ScreeningOutcome.EXCLUDE, None, [CriterionAssessmentInput(criterion_id=inclusion.criterion_id, assessment_value=CriterionAssessmentValue.NOT_MET)], [])
    saved = service.record_decision("lean_energy", paper.record_id, "alice", ScreeningOutcome.EXCLUDE, None, [CriterionAssessmentInput(criterion_id=inclusion.criterion_id, assessment_value=CriterionAssessmentValue.NOT_MET), CriterionAssessmentInput(criterion_id=exclusion.criterion_id, assessment_value=CriterionAssessmentValue.NOT_MET)], [inclusion.criterion_id])
    assert saved.exclusion_reason_criterion_ids == [inclusion.criterion_id]
    reopened = decisions.get("lean_energy", saved.decision_id)
    assert reopened.exclusion_reason_criterion_ids == [inclusion.criterion_id]


def test_unavailable_full_text_does_not_auto_exclude(tmp_path) -> None:
    service, publications, _, decisions, _ = _environment(tmp_path)
    paper = _publication(1)
    publications.add_publications("lean_energy", [paper])
    _include_title_abstract(decisions, paper)
    service.save_availability("lean_energy", paper.record_id, "alice", FullTextAvailabilityStatus.UNAVAILABLE, None, "No access")
    assert service.get_record("lean_energy", paper.record_id, "alice").status is FullTextScreeningStatus.UNSCREENED
