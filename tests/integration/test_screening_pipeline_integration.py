from __future__ import annotations

import os
import tempfile
from pathlib import Path
from uuid import uuid4

import pytest

from app.domain.conflict_resolution import PublicationScreeningStatus, ResolvedOutcome
from app.domain.project import Project
from app.domain.publication import Publication
from app.domain.screening import (
    ScreeningOutcome,
    ScreeningStage,
)
from app.repositories.conflict_resolution_repository import SqliteConflictResolutionRepository
from app.repositories.full_text_availability_repository import SqliteFullTextAvailabilityRepository
from app.repositories.project_publication_repository import SqliteProjectPublicationRepository
from app.repositories.project_repository import SqliteProjectRepository
from app.repositories.screening_criterion_repository import SqliteScreeningCriterionRepository
from app.repositories.screening_decision_repository import SqliteScreeningDecisionRepository
from app.repositories.screening_reporting_repository import ScreeningReportingRepository
from app.repositories.screening_reviewer_assignment_repository import SqliteScreeningReviewerAssignmentRepository
from app.services.conflict_resolution_service import ConflictResolutionService
from app.services.full_text_screening_service import (
    FullTextReadinessStatus,
    FullTextScreeningService,
    FullTextWorkflowNotReadyError,
)
from app.services.multi_reviewer_screening_service import MultiReviewerScreeningService
from app.services.screening_decision_service import ScreeningDecisionService
from app.services.screening_eligibility_adapter import ScreeningEligibilityAdapter
from app.services.screening_input_service import ScreeningInputService
from app.services.title_abstract_screening_service import TitleAbstractScreeningService


@pytest.fixture
def temp_db_path():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)
    yield db_path
    if db_path.exists():
        os.unlink(db_path)


@pytest.fixture
def pipeline_fixture(temp_db_path):
    project_repo = SqliteProjectRepository(temp_db_path)
    pub_repo = SqliteProjectPublicationRepository(temp_db_path)
    criterion_repo = SqliteScreeningCriterionRepository(temp_db_path)
    decision_repo = SqliteScreeningDecisionRepository(temp_db_path)
    assignment_repo = SqliteScreeningReviewerAssignmentRepository(temp_db_path)
    resolution_repo = SqliteConflictResolutionRepository(temp_db_path)
    availability_repo = SqliteFullTextAvailabilityRepository(temp_db_path)

    project_id = "test_project"
    project_repo.create(Project(project_id=project_id, title="Test Project", description="Test", protocol_version="1.0"))

    # Seed 2 publications directly
    pub1_id = uuid4()
    pub2_id = uuid4()
    pub1 = Publication(
        record_id=pub1_id,
        title="Publication One",
        abstract="Abstract One",
        publication_year=2024,
    )
    pub2 = Publication(
        record_id=pub2_id,
        title="Publication Two",
        abstract="Abstract Two",
        publication_year=2024,
    )
    pub_repo.add_publications(project_id, [pub1, pub2])

    reporting_repo = ScreeningReportingRepository(temp_db_path)

    input_service = ScreeningInputService(publication_repository=pub_repo)
    decision_service = ScreeningDecisionService(
        publication_repository=pub_repo,
        criterion_repository=criterion_repo,
        decision_repository=decision_repo,
    )
    multi_service = MultiReviewerScreeningService(
        assignments=assignment_repo,
        reporting=reporting_repo,
        resolutions=resolution_repo,
        input_service=input_service,
    )
    resolution_service = ConflictResolutionService(
        multi_reviewer=multi_service,
        repository=resolution_repo,
    )
    adapter = ScreeningEligibilityAdapter(
        input_service=input_service,
        assignments_repo=assignment_repo,
        decisions_repo=decision_repo,
        multi_reviewer_service=multi_service,
    )
    ta_service = TitleAbstractScreeningService(
        input_service=input_service,
        criterion_repository=criterion_repo,
        decision_repository=decision_repo,
        decision_service=decision_service,
    )
    ft_service = FullTextScreeningService(
        input_service=input_service,
        criterion_repository=criterion_repo,
        decision_repository=decision_repo,
        decision_service=decision_service,
        availability_repository=availability_repo,
        eligibility_adapter=adapter,
    )

    return {
        "project_id": project_id,
        "pub1_id": pub1_id,
        "pub2_id": pub2_id,
        "criterion_repo": criterion_repo,
        "decision_repo": decision_repo,
        "assignment_repo": assignment_repo,
        "resolution_service": resolution_service,
        "multi_service": multi_service,
        "adapter": adapter,
        "ta_service": ta_service,
        "ft_service": ft_service,
    }


def test_single_reviewer_pipeline(pipeline_fixture):
    project_id = pipeline_fixture["project_id"]
    pub1_id = pipeline_fixture["pub1_id"]
    pub2_id = pipeline_fixture["pub2_id"]
    ta_service = pipeline_fixture["ta_service"]
    ft_service = pipeline_fixture["ft_service"]
    adapter = pipeline_fixture["adapter"]

    # In single reviewer mode (no active roster configured), Reviewer 1 includes pub1 and excludes pub2
    ta_service.record_decision(
        project_id=project_id,
        publication_id=pub1_id,
        reviewer_id="reviewer_1",
        outcome=ScreeningOutcome.INCLUDE,
        rationale="Looks relevant",
        assessment_inputs=[],
    )
    ta_service.record_decision(
        project_id=project_id,
        publication_id=pub2_id,
        reviewer_id="reviewer_1",
        outcome=ScreeningOutcome.EXCLUDE,
        rationale="Not relevant",
        assessment_inputs=[],
    )

    # Check FT eligibility for reviewer_1: only pub1 is eligible
    eligible_ft = adapter.eligible_publications(project_id, ScreeningStage.TITLE_ABSTRACT, ScreeningStage.FULL_TEXT, "reviewer_1")
    assert eligible_ft == (pub1_id,)

    overview = ft_service.get_overview(project_id, "reviewer_1")
    assert overview.readiness.ready is True
    assert overview.readiness.eligible_count == 1

    # Record FT decision for reviewer_1 on pub1
    ft_service.record_decision(
        project_id=project_id,
        publication_id=pub1_id,
        reviewer_id="reviewer_1",
        outcome=ScreeningOutcome.INCLUDE,
        rationale="Full text confirmed",
        assessment_inputs=[],
        exclusion_reason_criterion_ids=[],
    )

    # Check QA eligibility for reviewer_1: pub1 is eligible
    eligible_qa = adapter.eligible_publications(project_id, ScreeningStage.FULL_TEXT, "quality_assessment", "reviewer_1")
    assert eligible_qa == (pub1_id,)


def test_multi_reviewer_agreement_hydrates_all_active_ft_reviewers(pipeline_fixture):
    project_id = pipeline_fixture["project_id"]
    pub1_id = pipeline_fixture["pub1_id"]
    assignment_repo = pipeline_fixture["assignment_repo"]
    ta_service = pipeline_fixture["ta_service"]
    adapter = pipeline_fixture["adapter"]
    ft_service = pipeline_fixture["ft_service"]

    # Set up active rosters for T&A and FT
    assignment_repo.replace_active(project_id, ScreeningStage.TITLE_ABSTRACT, ["reviewer_1", "reviewer_2"])
    assignment_repo.replace_active(project_id, ScreeningStage.FULL_TEXT, ["reviewer_1", "reviewer_2", "reviewer_3"])

    # Reviewer 1 and Reviewer 2 both vote INCLUDE on pub1 at T&A
    ta_service.record_decision(project_id, pub1_id, "reviewer_1", ScreeningOutcome.INCLUDE, "Yes", [])
    ta_service.record_decision(project_id, pub1_id, "reviewer_2", ScreeningOutcome.INCLUDE, "Yes", [])

    # Project outcome is AGREEMENT INCLUDE
    outcome = adapter.get_outcome(project_id, pub1_id, ScreeningStage.TITLE_ABSTRACT, "reviewer_1")
    assert outcome.status is PublicationScreeningStatus.AGREEMENT
    assert outcome.outcome is ResolvedOutcome.INCLUDE

    # ALL active FT reviewers (reviewer_1, reviewer_2, AND reviewer_3 who was not in T&A) see pub1 in FT queue
    for r in ["reviewer_1", "reviewer_2", "reviewer_3"]:
        eligible = adapter.eligible_publications(project_id, ScreeningStage.TITLE_ABSTRACT, ScreeningStage.FULL_TEXT, r)
        assert eligible == (pub1_id,)
        overview = ft_service.get_overview(project_id, r)
        assert overview.readiness.ready is True
        assert overview.readiness.eligible_count >= 1


def test_multi_reviewer_conflict_and_adjudication_flow(pipeline_fixture):
    project_id = pipeline_fixture["project_id"]
    pub1_id = pipeline_fixture["pub1_id"]
    assignment_repo = pipeline_fixture["assignment_repo"]
    ta_service = pipeline_fixture["ta_service"]
    ft_service = pipeline_fixture["ft_service"]
    multi_service = pipeline_fixture["multi_service"]
    resolution_service = pipeline_fixture["resolution_service"]

    assignment_repo.replace_active(project_id, ScreeningStage.TITLE_ABSTRACT, ["reviewer_1", "reviewer_2"])
    assignment_repo.replace_active(project_id, ScreeningStage.FULL_TEXT, ["reviewer_1", "reviewer_2"])

    # Disagreement: Reviewer 1 votes INCLUDE, Reviewer 2 votes EXCLUDE
    ta_service.record_decision(project_id, pub1_id, "reviewer_1", ScreeningOutcome.INCLUDE, "Yes", [])
    ta_service.record_decision(project_id, pub1_id, "reviewer_2", ScreeningOutcome.EXCLUDE, "No", [])

    # Full-Text screening workflow must be BLOCKED with UNRESOLVED_CONFLICT
    overview = ft_service.get_overview(project_id, "reviewer_1")
    assert overview.readiness.status is FullTextReadinessStatus.UNRESOLVED_CONFLICT

    with pytest.raises(FullTextWorkflowNotReadyError) as exc:
        ft_service.list_records(project_id, "reviewer_1")
    assert exc.value.readiness_status is FullTextReadinessStatus.UNRESOLVED_CONFLICT

    # Get conflict state to retrieve expected decision set key
    state = multi_service.publication_state(project_id, pub1_id, ScreeningStage.TITLE_ABSTRACT)
    assert state is not None
    assert state.status.value == "conflict"

    # Adjudicator resolves conflict as INCLUDE
    res = resolution_service.resolve(
        project_id=project_id,
        publication_id=pub1_id,
        stage=ScreeningStage.TITLE_ABSTRACT,
        outcome=ResolvedOutcome.INCLUDE,
        resolver_id="adjudicator_1",
        rationale="Overriding exclusion based on protocol",
        expected_key=state.current_decision_set_key,
    )
    assert res.resolved_outcome is ResolvedOutcome.INCLUDE

    # Now FT workflow is READY for both active FT reviewers
    overview_after = ft_service.get_overview(project_id, "reviewer_1")
    assert overview_after.readiness.ready is True
    assert overview_after.readiness.eligible_count >= 1


def test_staleness_revocation_on_decision_change(pipeline_fixture):
    project_id = pipeline_fixture["project_id"]
    pub1_id = pipeline_fixture["pub1_id"]
    assignment_repo = pipeline_fixture["assignment_repo"]
    ta_service = pipeline_fixture["ta_service"]
    ft_service = pipeline_fixture["ft_service"]
    multi_service = pipeline_fixture["multi_service"]
    resolution_service = pipeline_fixture["resolution_service"]

    assignment_repo.replace_active(project_id, ScreeningStage.TITLE_ABSTRACT, ["reviewer_1", "reviewer_2"])
    assignment_repo.replace_active(project_id, ScreeningStage.FULL_TEXT, ["reviewer_1", "reviewer_2"])

    ta_service.record_decision(project_id, pub1_id, "reviewer_1", ScreeningOutcome.INCLUDE, "Yes", [])
    ta_service.record_decision(project_id, pub1_id, "reviewer_2", ScreeningOutcome.EXCLUDE, "No", [])

    state = multi_service.publication_state(project_id, pub1_id, ScreeningStage.TITLE_ABSTRACT)
    resolution_service.resolve(
        project_id=project_id,
        publication_id=pub1_id,
        stage=ScreeningStage.TITLE_ABSTRACT,
        outcome=ResolvedOutcome.INCLUDE,
        resolver_id="adjudicator_1",
        rationale="Resolved",
        expected_key=state.current_decision_set_key,
    )

    assert ft_service.get_overview(project_id, "reviewer_1").readiness.ready is True

    # Reviewer 2 changes vote to UNCERTAIN -> decision_set_key changes, status becomes STALE_RESOLUTION
    ta_service.record_decision(project_id, pub1_id, "reviewer_2", ScreeningOutcome.UNCERTAIN, "Changed mind", [])

    state_after = multi_service.publication_state(project_id, pub1_id, ScreeningStage.TITLE_ABSTRACT)
    assert state_after.status.value == "stale_resolution"

    # FT access is immediately revoked
    overview_stale = ft_service.get_overview(project_id, "reviewer_1")
    assert overview_stale.readiness.status is FullTextReadinessStatus.STALE_RESOLUTION
