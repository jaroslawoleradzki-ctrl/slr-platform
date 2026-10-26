from pathlib import Path
from uuid import UUID

from fastapi.testclient import TestClient

from app.api.main import app
from app.api.routers.deduplication import get_duplicate_service
from app.domain.identifiers import Identifier, IdentifierType
from app.domain.provenance import ProvenanceEntry
from app.domain.publication import Publication
from app.repositories.duplicate_merge_repository import SqliteDuplicateMergeRepository
from app.repositories.duplicate_review_decision_repository import SqliteDuplicateReviewDecisionRepository
from app.repositories.project_publication_repository import SqliteProjectPublicationRepository
from app.repositories.transaction_manager import SqliteTransactionManager
from app.services.project_duplicate_service import ProjectDuplicateService


def _service(tmp_path: Path) -> tuple[ProjectDuplicateService, TestClient, str]:
    database = tmp_path / "v072.db"
    publications = SqliteProjectPublicationRepository(database)
    first = Publication(
        record_id=UUID("00000000-0000-0000-0000-000000000001"),
        title="Study",
        identifiers=[Identifier(type=IdentifierType.DOI, value="10.1000/v072")],
        provenance=[ProvenanceEntry(source="a", source_record_id="1")],
    )
    second = Publication(
        record_id=UUID("00000000-0000-0000-0000-000000000002"),
        title="Study duplicate",
        identifiers=[Identifier(type=IdentifierType.DOI, value="10.1000/v072")],
        provenance=[ProvenanceEntry(source="b", source_record_id="2")],
    )
    publications.add_publications("lean_energy", [first, second])
    service = ProjectDuplicateService(
        publications,
        SqliteDuplicateReviewDecisionRepository(database),
        merge_repository=SqliteDuplicateMergeRepository(database),
        transaction_manager=SqliteTransactionManager(database),
    )
    app.dependency_overrides[get_duplicate_service] = lambda: service
    client = TestClient(app)
    group_id = client.get("/api/v1/projects/lean_energy/duplicate-groups").json()["groups"][0]["group_id"]
    return service, client, group_id


def test_v072_approve_triggers_merge_and_decision_history(tmp_path: Path) -> None:
    service, client, group_id = _service(tmp_path)
    try:
        response = client.post(f"/api/v1/projects/lean_energy/duplicate-groups/{group_id}/merge", json={})
        assert response.status_code == 200
        assert response.json()["status"] == "MERGED"

        groups = client.get("/api/v1/projects/lean_energy/duplicate-groups").json()["groups"]
        assert groups[0]["status"] == "MERGED"
        assert groups[0]["canonical_record_id"] is not None

        decision = client.get(f"/api/v1/projects/lean_energy/duplicate-groups/{group_id}/decision").json()
        assert decision["decision"] == "APPROVE"

        # Repeated merge request must not merge a second time.
        repeat = client.post(f"/api/v1/projects/lean_energy/duplicate-groups/{group_id}/merge", json={})
        assert repeat.status_code == 422
    finally:
        app.dependency_overrides.pop(get_duplicate_service, None)


def test_v072_failed_merge_rolls_back_atomically(tmp_path: Path) -> None:
    service, client, group_id = _service(tmp_path)
    try:
        original_update = service._repository.update_publication

        def failing_update(project_id, publication, *, connection=None):
            raise RuntimeError("simulated canonical update failure")

        service._repository.update_publication = failing_update
        response = client.post(f"/api/v1/projects/lean_energy/duplicate-groups/{group_id}/merge", json={})
        assert response.status_code == 500

        service._repository.update_publication = original_update
        reopened_merge_repo = SqliteDuplicateMergeRepository(service._merge_repository._database_path)
        reopened_decision_repo = SqliteDuplicateReviewDecisionRepository(service._decision_repository._database_path)
        assert reopened_merge_repo.get_merge("lean_energy", group_id) is None
        assert reopened_decision_repo.get_decision("lean_energy", group_id) is None
    finally:
        app.dependency_overrides.pop(get_duplicate_service, None)
