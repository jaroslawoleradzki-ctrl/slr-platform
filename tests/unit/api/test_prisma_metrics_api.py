from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.api.main import app
from app.api.routers.projects import get_prisma_metrics_service
from app.domain.duplicate_review import DuplicateDecision, DuplicateGroupReviewDecision
from app.domain.project import Project
from app.domain.screening import ScreeningDecision, ScreeningOutcome, ScreeningStage
from app.repositories.conflict_resolution_repository import SqliteConflictResolutionRepository
from app.repositories.duplicate_review_decision_repository import SqliteDuplicateReviewDecisionRepository
from app.repositories.import_history_repository import SqliteImportHistoryRepository
from app.repositories.project_publication_repository import SqliteProjectPublicationRepository
from app.repositories.project_repository import SqliteProjectRepository
from app.repositories.screening_decision_repository import SqliteScreeningDecisionRepository
from app.repositories.screening_reporting_repository import ScreeningReportingRepository
from app.repositories.screening_reviewer_assignment_repository import SqliteScreeningReviewerAssignmentRepository
from app.services.duplicate_group_builder import DuplicateGroupBuilder
from app.services.multi_reviewer_screening_service import MultiReviewerScreeningService
from app.services.prisma_metrics_service import PrismaMetricsService
from app.services.project_workflow_status_service import ProjectWorkflowStatusService
from app.services.screening_eligibility_adapter import ScreeningEligibilityAdapter
from app.services.screening_input_service import ScreeningInputService
from tests.fixtures.factories import make_import_history, make_publication

PROJECT_ID = "prisma_project"
REVIEWER_ID = "alice"


@pytest.fixture
def environment(tmp_path):
    database = tmp_path / "prisma.db"
    project_repo = SqliteProjectRepository(database)
    publications = SqliteProjectPublicationRepository(database)
    history = SqliteImportHistoryRepository(database)
    duplicate_decisions = SqliteDuplicateReviewDecisionRepository(database)
    screening_decisions = SqliteScreeningDecisionRepository(database)
    assignments = SqliteScreeningReviewerAssignmentRepository(database)
    resolutions = SqliteConflictResolutionRepository(database)
    reporting = ScreeningReportingRepository(database)
    project_repo.create(Project(project_id=PROJECT_ID, title="PRISMA Project"))

    input_service = ScreeningInputService(publications, duplicate_decisions)
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
        publication_repository=publications,
        decision_repository=screening_decisions,
        assignment_repository=assignments,
        resolution_repository=resolutions,
        reporting_repository=reporting,
        input_service=input_service,
        multi_reviewer_service=multi_service,
        eligibility_adapter=adapter,
    )
    service = PrismaMetricsService(
        publication_repository=publications,
        import_history_repository=history,
        decision_repository=duplicate_decisions,
        workflow_status_service=workflow_status,
        builder=DuplicateGroupBuilder(),
    )
    app.dependency_overrides[get_prisma_metrics_service] = lambda: service
    yield TestClient(app), publications, history, duplicate_decisions, screening_decisions
    app.dependency_overrides.clear()


def _decision(publication_id: UUID, stage: ScreeningStage, outcome: ScreeningOutcome) -> ScreeningDecision:
    return ScreeningDecision(
        project_id=PROJECT_ID,
        publication_id=publication_id,
        stage=stage,
        outcome=outcome,
        reviewer_id=REVIEWER_ID,
    )


def test_prisma_metrics_unknown_project_returns_404(environment) -> None:
    client, *_ = environment
    response = client.get("/api/v1/projects/does-not-exist/prisma/metrics")
    assert response.status_code == 404


def test_prisma_metrics_empty_project_returns_zeros(environment) -> None:
    client, *_ = environment
    response = client.get(f"/api/v1/projects/{PROJECT_ID}/prisma/metrics")
    assert response.status_code == 200
    assert response.json() == {
        "project_id": PROJECT_ID,
        "records_identified_providers": 0,
        "records_identified_imports": 0,
        "total_identified": 0,
        "records_after_normalization": 0,
        "records_before_dedup": 0,
        "records_after_technical_merger": 0,
        "duplicate_groups_pending_review": 0,
        "records_screened_title_abstract": 0,
        "records_screened_full_text": 0,
        "studies_included_synthesis": 0,
    }


def test_prisma_metrics_identified_counts_from_import_history(environment) -> None:
    client, _, history, *_ = environment
    history.create(make_import_history(PROJECT_ID, records_count=10, source_type="provider", status="success"))
    history.create(make_import_history(PROJECT_ID, records_count=5, source_type="provider", status="warning"))
    history.create(make_import_history(PROJECT_ID, records_count=7, source_type="file", status="success"))
    history.create(make_import_history(PROJECT_ID, records_count=3, source_type="file", status="failed"))

    body = client.get(f"/api/v1/projects/{PROJECT_ID}/prisma/metrics").json()
    assert body["records_identified_providers"] == 15
    assert body["records_identified_imports"] == 7
    assert body["total_identified"] == 22


def test_prisma_metrics_counts_semantic_scholar_provider_imports(environment) -> None:
    client, _, history, *_ = environment
    history.create(
        make_import_history(
            PROJECT_ID,
            records_count=6,
            source_type="provider",
            provider="semantic_scholar",
            status="success",
        )
    )
    history.create(
        make_import_history(
            PROJECT_ID,
            records_count=2,
            source_type="provider",
            provider="semantic_scholar",
            status="warning",
        )
    )

    body = client.get(f"/api/v1/projects/{PROJECT_ID}/prisma/metrics").json()
    assert body["records_identified_providers"] == 8
    assert body["total_identified"] == 8


def test_prisma_metrics_normalization_and_dedup_without_duplicates(environment) -> None:
    client, publications, *_ = environment
    publications.add_publications(PROJECT_ID, [make_publication(1), make_publication(2), make_publication(3)])

    body = client.get(f"/api/v1/projects/{PROJECT_ID}/prisma/metrics").json()
    assert body["records_after_normalization"] == 3
    assert body["records_before_dedup"] == 3
    assert body["records_after_technical_merger"] == 3
    assert body["duplicate_groups_pending_review"] == 0


def test_prisma_metrics_technical_merger_and_pending_group(environment) -> None:
    client, publications, *_ = environment
    publications.add_publications(
        PROJECT_ID,
        [make_publication(1, doi="10.1/x"), make_publication(2, doi="10.1/x"), make_publication(3, doi="10.2/y")],
    )

    body = client.get(f"/api/v1/projects/{PROJECT_ID}/prisma/metrics").json()
    assert body["records_after_normalization"] == 3
    assert body["records_before_dedup"] == 3
    assert body["records_after_technical_merger"] == 2
    assert body["duplicate_groups_pending_review"] == 1


def test_prisma_metrics_resolved_group_no_longer_pending(environment) -> None:
    client, publications, _, duplicate_decisions, *_ = environment
    pubs = [make_publication(1, doi="10.1/x"), make_publication(2, doi="10.1/x")]
    publications.add_publications(PROJECT_ID, pubs)
    group = DuplicateGroupBuilder().build(pubs)[0]
    duplicate_decisions.save_decision(
        PROJECT_ID, str(group.group_id), DuplicateGroupReviewDecision(decision=DuplicateDecision.APPROVE)
    )

    body = client.get(f"/api/v1/projects/{PROJECT_ID}/prisma/metrics").json()
    assert body["duplicate_groups_pending_review"] == 0
    assert body["records_after_technical_merger"] == 1


def test_prisma_metrics_partial_and_full_screening(environment) -> None:
    client, publications, _, _, screening_decisions = environment
    pub1 = make_publication(1)
    pub2 = make_publication(2)
    pub3 = make_publication(3)
    publications.add_publications(PROJECT_ID, [pub1, pub2, pub3])

    body = client.get(f"/api/v1/projects/{PROJECT_ID}/prisma/metrics", params={"reviewer_id": REVIEWER_ID}).json()
    assert body["records_screened_title_abstract"] == 0
    assert body["records_screened_full_text"] == 0
    assert body["studies_included_synthesis"] == 0

    screening_decisions.save(_decision(pub1.record_id, ScreeningStage.TITLE_ABSTRACT, ScreeningOutcome.INCLUDE))
    body = client.get(f"/api/v1/projects/{PROJECT_ID}/prisma/metrics", params={"reviewer_id": REVIEWER_ID}).json()
    assert body["records_screened_title_abstract"] == 1
    assert body["records_screened_full_text"] == 0
    assert body["studies_included_synthesis"] == 0

    screening_decisions.save(_decision(pub2.record_id, ScreeningStage.TITLE_ABSTRACT, ScreeningOutcome.INCLUDE))
    screening_decisions.save(_decision(pub3.record_id, ScreeningStage.TITLE_ABSTRACT, ScreeningOutcome.EXCLUDE))
    body = client.get(f"/api/v1/projects/{PROJECT_ID}/prisma/metrics", params={"reviewer_id": REVIEWER_ID}).json()
    assert body["records_screened_title_abstract"] == 3

    screening_decisions.save(_decision(pub1.record_id, ScreeningStage.FULL_TEXT, ScreeningOutcome.INCLUDE))
    screening_decisions.save(_decision(pub2.record_id, ScreeningStage.FULL_TEXT, ScreeningOutcome.EXCLUDE))
    body = client.get(f"/api/v1/projects/{PROJECT_ID}/prisma/metrics", params={"reviewer_id": REVIEWER_ID}).json()
    assert body["records_screened_full_text"] == 2
    assert body["studies_included_synthesis"] == 1


def test_prisma_metrics_latest_decision_wins(environment) -> None:
    client, publications, _, _, screening_decisions = environment
    pub1 = make_publication(1)
    publications.add_publications(PROJECT_ID, [pub1])

    screening_decisions.save(_decision(pub1.record_id, ScreeningStage.TITLE_ABSTRACT, ScreeningOutcome.INCLUDE))
    screening_decisions.save(_decision(pub1.record_id, ScreeningStage.TITLE_ABSTRACT, ScreeningOutcome.EXCLUDE))

    body = client.get(f"/api/v1/projects/{PROJECT_ID}/prisma/metrics", params={"reviewer_id": REVIEWER_ID}).json()
    assert body["records_screened_title_abstract"] == 1
    assert body["studies_included_synthesis"] == 0
