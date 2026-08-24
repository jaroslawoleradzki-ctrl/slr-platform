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


def test_merge_api_has_no_client_canonical_selection_and_reports_lifecycle(tmp_path: Path) -> None:
    database = tmp_path / "api-merge.db"
    publications = SqliteProjectPublicationRepository(database)
    first = Publication(record_id=UUID("00000000-0000-0000-0000-000000000001"), title="Study", identifiers=[Identifier(type=IdentifierType.DOI, value="10.1000/api")], provenance=[ProvenanceEntry(source="a", source_record_id="1")])
    second = Publication(record_id=UUID("00000000-0000-0000-0000-000000000002"), title="Study duplicate", identifiers=[Identifier(type=IdentifierType.DOI, value="10.1000/api")], provenance=[ProvenanceEntry(source="b", source_record_id="2")])
    publications.add_publications("lean_energy", [first, second])
    service = ProjectDuplicateService(publications, SqliteDuplicateReviewDecisionRepository(database), merge_repository=SqliteDuplicateMergeRepository(database), transaction_manager=SqliteTransactionManager(database))
    previous = app.dependency_overrides.get(get_duplicate_service)
    app.dependency_overrides[get_duplicate_service] = lambda: service
    try:
        client = TestClient(app)
        group_id = client.get("/api/v1/projects/lean_energy/duplicate-groups").json()["groups"][0]["group_id"]
        assert client.post(f"/api/v1/projects/lean_energy/duplicate-groups/{group_id}/merge", json={}).status_code == 422
        assert client.post(f"/api/v1/projects/lean_energy/duplicate-groups/{group_id}/decision", json={"decision": "APPROVE"}).json()["decision"] == "APPROVE"
        response = client.post(f"/api/v1/projects/lean_energy/duplicate-groups/{group_id}/merge", json={})
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "MERGED" and body["canonical_record_id"] == str(first.record_id)
        assert set(body["merged_publication_ids"]) == {str(first.record_id), str(second.record_id)} and body["merged_at"]
        assert client.get(f"/api/v1/projects/lean_energy/duplicate-groups/{group_id}/decision").json()["decision"] == "APPROVE"
        assert client.get("/api/v1/projects/lean_energy/duplicate-groups").json()["groups"][0]["status"] == "MERGED"
        assert client.post(f"/api/v1/projects/lean_energy/duplicate-groups/{group_id}/merge", json={}).status_code == 422
    finally:
        if previous is None:
            app.dependency_overrides.pop(get_duplicate_service, None)
        else:
            app.dependency_overrides[get_duplicate_service] = previous
