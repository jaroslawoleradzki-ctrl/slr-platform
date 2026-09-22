from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.main import app
from app.api.routers.pre_screening import get_pre_screening_review_service
from app.domain.project import Project
from app.repositories.import_history_repository import SqliteImportHistoryRepository
from app.repositories.pre_screening_decision_repository import (
    SqlitePreScreeningDecisionRepository,
)
from app.repositories.project_publication_repository import (
    SqliteProjectPublicationRepository,
)
from app.repositories.project_repository import SqliteProjectRepository
from app.services.pre_screening_review_service import PreScreeningReviewService
from tests.fixtures.factories import make_import_history, make_publication

PROJECT_ID = "pre_screen_proj"


@pytest.fixture
def client_fixture(tmp_path: Path):
    db_path = tmp_path / "api_test.db"
    project_repo = SqliteProjectRepository(db_path)
    pub_repo = SqliteProjectPublicationRepository(db_path)
    history_repo = SqliteImportHistoryRepository(db_path)
    decision_repo = SqlitePreScreeningDecisionRepository(db_path)

    project_repo.create(Project(project_id=PROJECT_ID, title="Pre Screening Project"))
    service = PreScreeningReviewService(pub_repo, decision_repo)
    app.dependency_overrides[get_pre_screening_review_service] = lambda: service

    client = TestClient(app)
    yield client, pub_repo, history_repo, decision_repo
    app.dependency_overrides.clear()


def test_get_imported_records_empty_import(client_fixture):
    client, pub_repo, history_repo, _ = client_fixture
    import_id = uuid4()
    history = make_import_history(project_id=PROJECT_ID, import_id=import_id, records_count=0)
    history_repo.create(history)

    response = client.get(f"/api/v1/projects/{PROJECT_ID}/imports/{import_id}/records")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert data["items"] == []
    assert data["total_imported"] == 0
    assert data["retained_count"] == 0
    assert data["removed_count"] == 0


def test_remove_and_restore_record_api(client_fixture):
    client, pub_repo, history_repo, decision_repo = client_fixture
    import_id = uuid4()
    history = make_import_history(project_id=PROJECT_ID, import_id=import_id, records_count=1)
    history_repo.create(history)

    pub = make_publication(index=1, title="Retrieved Article")
    pub_repo.import_source_publications(PROJECT_ID, [pub], import_id=import_id)

    # 1. Fetch records
    res = client.get(f"/api/v1/projects/{PROJECT_ID}/imports/{import_id}/records")
    assert res.status_code == 200
    assert res.json()["total"] == 1
    assert res.json()["items"][0]["pre_screening_status"] == "retained"

    # 2. Remove record
    remove_res = client.post(
        f"/api/v1/projects/{PROJECT_ID}/imports/{import_id}/records/{pub.record_id}/remove",
        json={
            "reason": "clearly_outside_scope",
            "notes": "Irrelevant field",
            "reviewer_id": "dr_smith",
        },
    )
    assert remove_res.status_code == 200
    rem_data = remove_res.json()
    assert rem_data["pre_screening_status"] == "removed"
    assert rem_data["removal_reason"] == "clearly_outside_scope"
    assert rem_data["removal_notes"] == "Irrelevant field"
    assert rem_data["reviewer_id"] == "dr_smith"

    # 3. Check records list reflection
    res_after = client.get(f"/api/v1/projects/{PROJECT_ID}/imports/{import_id}/records")
    data_after = res_after.json()
    assert data_after["total_imported"] == 1
    assert data_after["retained_count"] == 0
    assert data_after["removed_count"] == 1
    assert data_after["items"][0]["pre_screening_status"] == "removed"

    # 4. Restore record (Undo)
    restore_res = client.post(
        f"/api/v1/projects/{PROJECT_ID}/imports/{import_id}/records/{pub.record_id}/restore",
        json={"reviewer_id": "dr_smith"},
    )
    assert restore_res.status_code == 200
    rest_data = restore_res.json()
    assert rest_data["pre_screening_status"] == "retained"
    assert rest_data["removal_reason"] is None

    # 5. Check records list reflection after restore
    res_restored = client.get(f"/api/v1/projects/{PROJECT_ID}/imports/{import_id}/records")
    data_restored = res_restored.json()
    assert data_restored["retained_count"] == 1
    assert data_restored["removed_count"] == 0


def test_remove_record_validation_error(client_fixture):
    client, pub_repo, history_repo, _ = client_fixture
    import_id = uuid4()
    pub = make_publication(index=1, title="Test Record")
    pub_repo.import_source_publications(PROJECT_ID, [pub], import_id=import_id)

    # Missing reason
    res = client.post(
        f"/api/v1/projects/{PROJECT_ID}/imports/{import_id}/records/{pub.record_id}/remove",
        json={},
    )
    assert res.status_code == 422

    # Reason 'other' with no notes
    res2 = client.post(
        f"/api/v1/projects/{PROJECT_ID}/imports/{import_id}/records/{pub.record_id}/remove",
        json={"reason": "other", "notes": ""},
    )
    assert res2.status_code == 422


def test_record_not_found(client_fixture):
    client, *_ = client_fixture
    import_id = uuid4()
    random_rec = uuid4()

    res = client.post(
        f"/api/v1/projects/{PROJECT_ID}/imports/{import_id}/records/{random_rec}/remove",
        json={"reason": "clearly_outside_scope"},
    )
    assert res.status_code == 404
