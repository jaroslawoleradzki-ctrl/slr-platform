from pathlib import Path
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.api.main import app
from app.api.routers.projects import get_project_workflow_status_service
from app.domain.duplicate_review import DuplicateDecision, DuplicateGroupReviewDecision
from app.domain.identifiers import Identifier, IdentifierType
from app.domain.project import Project
from app.domain.provenance import ProvenanceEntry
from app.domain.publication import Publication
from app.repositories.duplicate_merge_repository import SqliteDuplicateMergeRepository
from app.repositories.duplicate_review_decision_repository import SqliteDuplicateReviewDecisionRepository
from app.repositories.project_publication_repository import SqliteProjectPublicationRepository
from app.repositories.project_repository import SqliteProjectRepository
from app.repositories.transaction_manager import SqliteTransactionManager
from app.services.project_duplicate_service import ProjectDuplicateService
from app.services.project_workflow_status_service import ProjectWorkflowStatusService
from app.services.screening_input_service import ScreeningInputService

PROJECT_ID = "workflow-dedup-project"


def _publication(number: int) -> Publication:
    return Publication(
        record_id=UUID(f"00000000-0000-0000-0000-{number:012d}"),
        title=f"Publication {number}",
        identifiers=[Identifier(type=IdentifierType.DOI, value="10.1000/workflow")],
        provenance=[ProvenanceEntry(source="ris", source_record_id=str(number))],
    )


@pytest.fixture
def environment(tmp_path: Path):
    database = tmp_path / "workflow-dedup.db"
    SqliteProjectRepository(database).create(Project(project_id=PROJECT_ID, title="Workflow"))
    publications = SqliteProjectPublicationRepository(database)
    decisions = SqliteDuplicateReviewDecisionRepository(database)
    merges = SqliteDuplicateMergeRepository(database)
    publications.add_publications(PROJECT_ID, [_publication(1), _publication(2)])
    duplicate_service = ProjectDuplicateService(
        publications,
        decisions,
        merge_repository=merges,
        transaction_manager=SqliteTransactionManager(database),
    )
    group_id = duplicate_service.get_candidate_duplicate_groups(PROJECT_ID).groups[0].group_id
    decisions.save_decision(
        PROJECT_ID,
        group_id,
        DuplicateGroupReviewDecision(decision=DuplicateDecision.APPROVE),
    )
    workflow_service = ProjectWorkflowStatusService(
        publication_repository=publications,
        input_service=ScreeningInputService(publications, decisions, merge_repository=merges),
    )
    app.dependency_overrides[get_project_workflow_status_service] = lambda: workflow_service
    yield TestClient(app), group_id
    app.dependency_overrides.clear()


def test_workflow_status_exposes_approved_unmerged_duplicate_blocker(environment) -> None:
    client, group_id = environment

    response = client.get(
        f"/api/v1/projects/{PROJECT_ID}/workflow-status",
        params={"reviewer_id": "alice"},
    )

    assert response.status_code == 200
    dedup = response.json()["deduplication"]
    assert dedup["status"] == "approved_unmerged"
    assert dedup["screening_ready"] is False
    assert dedup["approved_unmerged_groups"] == 1
    assert dedup["pending_review_groups"] == 0
    assert dedup["blocking_groups"] == 1
    assert dedup["blocking_group_ids"] == [group_id]
    assert response.json()["title_abstract_screening"]["evaluated_count"] == 0
