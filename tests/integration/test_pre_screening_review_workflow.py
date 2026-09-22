from pathlib import Path
from uuid import UUID, uuid4

import pytest

from app.domain.duplicate_review import DuplicateDecision, DuplicateGroupReviewDecision
from app.domain.pre_screening import (
    PreScreeningRemovalReason,
    PreScreeningStatus,
)
from app.domain.project import Project
from app.domain.screening import ScreeningDecision, ScreeningOutcome, ScreeningStage
from app.repositories.conflict_resolution_repository import (
    SqliteConflictResolutionRepository,
)
from app.repositories.duplicate_review_decision_repository import (
    SqliteDuplicateReviewDecisionRepository,
)
from app.repositories.import_history_repository import SqliteImportHistoryRepository
from app.repositories.pre_screening_decision_repository import (
    SqlitePreScreeningDecisionRepository,
)
from app.repositories.project_publication_repository import (
    SqliteProjectPublicationRepository,
)
from app.repositories.project_repository import SqliteProjectRepository
from app.repositories.screening_decision_repository import (
    SqliteScreeningDecisionRepository,
)
from app.repositories.screening_reporting_repository import (
    ScreeningReportingRepository,
)
from app.repositories.screening_reviewer_assignment_repository import (
    SqliteScreeningReviewerAssignmentRepository,
)
from app.services.duplicate_group_builder import DuplicateGroupBuilder
from app.services.multi_reviewer_screening_service import MultiReviewerScreeningService
from app.services.pre_screening_review_service import PreScreeningReviewService
from app.services.prisma_metrics_service import PrismaMetricsService
from app.services.project_workflow_status_service import ProjectWorkflowStatusService
from app.services.screening_eligibility_adapter import ScreeningEligibilityAdapter
from app.services.screening_input_service import ScreeningInputService
from tests.fixtures.factories import make_import_history, make_publication


@pytest.fixture
def workflow_context(tmp_path: Path):
    db_path = tmp_path / "integration_test.db"
    project_repo = SqliteProjectRepository(db_path)
    pub_repo = SqliteProjectPublicationRepository(db_path)
    history_repo = SqliteImportHistoryRepository(db_path)
    pre_screen_decisions = SqlitePreScreeningDecisionRepository(db_path)
    duplicate_decisions = SqliteDuplicateReviewDecisionRepository(db_path)
    screening_decisions = SqliteScreeningDecisionRepository(db_path)
    assignments = SqliteScreeningReviewerAssignmentRepository(db_path)
    resolutions = SqliteConflictResolutionRepository(db_path)
    reporting = ScreeningReportingRepository(db_path)

    project_id = "integration_project"
    project_repo.create(Project(project_id=project_id, title="Integration Test Project"))

    pre_screening_service = PreScreeningReviewService(pub_repo, pre_screen_decisions)
    input_service = ScreeningInputService(pub_repo, duplicate_decisions)
    multi_service = MultiReviewerScreeningService(
        assignments=assignments,
        reporting=reporting,
        input_service=input_service,
        resolutions=resolutions,
    )
    adapter = ScreeningEligibilityAdapter(
        input_service=input_service,
        assignments_repo=assignments,
        decisions_repo=screening_decisions,
        multi_reviewer_service=multi_service,
    )
    workflow_status = ProjectWorkflowStatusService(
        publication_repository=pub_repo,
        decision_repository=screening_decisions,
        assignment_repository=assignments,
        resolution_repository=resolutions,
        reporting_repository=reporting,
        input_service=input_service,
        multi_reviewer_service=multi_service,
        eligibility_adapter=adapter,
    )
    prisma_service = PrismaMetricsService(
        publication_repository=pub_repo,
        import_history_repository=history_repo,
        decision_repository=duplicate_decisions,
        workflow_status_service=workflow_status,
        builder=DuplicateGroupBuilder(),
    )

    return {
        "project_id": project_id,
        "pub_repo": pub_repo,
        "history_repo": history_repo,
        "pre_screen_decisions": pre_screen_decisions,
        "pre_screening_service": pre_screening_service,
        "input_service": input_service,
        "screening_decisions": screening_decisions,
        "prisma_service": prisma_service,
    }


def test_screening_boundary_and_prisma_invariants(workflow_context):
    ctx = workflow_context
    project_id = ctx["project_id"]
    pub_repo = ctx["pub_repo"]
    history_repo = ctx["history_repo"]
    pre_screening_service = ctx["pre_screening_service"]
    input_service = ctx["input_service"]
    screening_decisions = ctx["screening_decisions"]
    prisma_service = ctx["prisma_service"]

    import_id = uuid4()
    history = make_import_history(
        project_id=project_id,
        import_id=import_id,
        records_count=3,
        source_type="provider",
        status="success",
    )
    history_repo.create(history)

    # 3 publications retrieved from Crossref
    p1 = make_publication(index=1, title="Relevant Paper A", source="crossref")
    p2 = make_publication(index=2, title="Retrieved Error Artefact B", source="crossref")
    p3 = make_publication(index=3, title="Relevant Paper C", source="crossref")
    pub_repo.import_source_publications(project_id, [p1, p2, p3], import_id=import_id)

    # Before pre-screening removal:
    # Active publications = 3
    assert len(pub_repo.get_active_publications(project_id)) == 3
    input_set_before = input_service.get_input_set(project_id)
    assert len(input_set_before.publications) == 3

    # PRISMA metrics before removal
    metrics_before = prisma_service.get_metrics(project_id)
    assert metrics_before.total_identified == 3
    assert metrics_before.records_removed_prescreening == 0
    assert metrics_before.records_screened_title_abstract == 0

    # Execute Pre-Screening Removal on p2
    pre_screening_service.remove_record(
        project_id=project_id,
        import_id=import_id,
        record_id=p2.record_id,
        reason=PreScreeningRemovalReason.RETRIEVAL_ARTEFACT,
        notes="Non-scholarly erratum",
        reviewer_id="reviewer_lead",
    )

    # CRITICAL INVARIANT 1: Removed record does NOT enter active publications
    active_after = pub_repo.get_active_publications(project_id)
    active_ids = {p.record_id for p in active_after}
    assert len(active_ids) == 2
    assert p1.record_id in active_ids
    assert p3.record_id in active_ids
    assert p2.record_id not in active_ids

    # CRITICAL INVARIANT 2: ScreeningInputService excludes pre-screening removed records
    input_set_after = input_service.get_input_set(project_id)
    screening_input_ids = {p.record_id for p in input_set_after.publications}
    assert len(screening_input_ids) == 2
    assert p2.record_id not in screening_input_ids

    # CRITICAL INVARIANT 3: PRISMA accounting distinguishes pre-screening removal
    # and does NOT count it as screened or screening-excluded
    metrics_after_removal = prisma_service.get_metrics(project_id)
    assert metrics_after_removal.total_identified == 3
    assert metrics_after_removal.records_removed_prescreening == 1
    assert metrics_after_removal.records_screened_title_abstract == 0
    assert metrics_after_removal.records_excluded_title_abstract == 0

    # Now, formally screen one of the retained records (p1 -> include) and one (p3 -> exclude)
    screening_decisions.save(
        ScreeningDecision(
            project_id=project_id,
            publication_id=p1.record_id,
            stage=ScreeningStage.TITLE_ABSTRACT,
            outcome=ScreeningOutcome.INCLUDE,
            reviewer_id="reviewer_lead",
        )
    )
    screening_decisions.save(
        ScreeningDecision(
            project_id=project_id,
            publication_id=p3.record_id,
            stage=ScreeningStage.TITLE_ABSTRACT,
            outcome=ScreeningOutcome.EXCLUDE,
            reviewer_id="reviewer_lead",
        )
    )

    # CRITICAL INVARIANT 4: PRISMA "records screened" is exactly 2, NOT 3 (not inflated by pre-screening removal)
    metrics_after_screening = prisma_service.get_metrics(project_id, reviewer_id="reviewer_lead")
    assert metrics_after_screening.records_screened_title_abstract == 2
    assert metrics_after_screening.records_excluded_title_abstract == 1
    assert metrics_after_screening.records_removed_prescreening == 1

    # CRITICAL INVARIANT 5: Undo / Restore puts record back into screening corpus
    pre_screening_service.restore_record(
        project_id=project_id,
        import_id=import_id,
        record_id=p2.record_id,
        reviewer_id="reviewer_lead",
    )

    active_restored = pub_repo.get_active_publications(project_id)
    assert len(active_restored) == 3
    assert p2.record_id in {p.record_id for p in active_restored}

    metrics_after_restore = prisma_service.get_metrics(project_id, reviewer_id="reviewer_lead")
    assert metrics_after_restore.records_removed_prescreening == 0


def test_legacy_import_compatibility(workflow_context):
    """Test compatibility with historical imports where import_id was initially NULL."""
    ctx = workflow_context
    project_id = ctx["project_id"]
    pub_repo = ctx["pub_repo"]
    history_repo = ctx["history_repo"]
    pre_screening_service = ctx["pre_screening_service"]

    import_id = uuid4()
    # Create history entry with provider 'crossref'
    history = make_import_history(
        project_id=project_id,
        import_id=import_id,
        records_count=2,
        source_type="provider",
        provider="crossref",
        status="success",
    )
    history_repo.create(history)

    # Directly insert publications without import_id (simulating legacy data)
    p1 = make_publication(index=1, title="Legacy Paper 1", source="crossref")
    p2 = make_publication(index=2, title="Legacy Paper 2", source="crossref")
    # Add directly via add_publications where import_id is not passed
    pub_repo.add_publications(project_id, [p1, p2])

    # The pre-screening listing will dynamically auto-link publications based on provider
    page = pre_screening_service.list_imported_records(project_id, import_id)
    assert page.total == 2
    assert page.total_imported == 2
    assert page.retained_count == 2
    assert page.removed_count == 0

    # Pre-screening removal works on legacy record
    rec = pre_screening_service.remove_record(
        project_id=project_id,
        import_id=import_id,
        record_id=p2.record_id,
        reason=PreScreeningRemovalReason.CLEARLY_OUTSIDE_SCOPE,
        reviewer_id="reviewer_1",
    )
    assert rec.pre_screening_status == PreScreeningStatus.REMOVED
    assert pub_repo.count_pre_screening_removed(project_id) == 1
