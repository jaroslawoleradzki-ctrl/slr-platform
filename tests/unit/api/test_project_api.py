import pytest
from fastapi.testclient import TestClient

from app.api.main import app
from app.api.routers.projects import generate_project_id, get_project_repository
from app.repositories.project_repository import SqliteProjectRepository

client = TestClient(app)


@pytest.fixture
def repo(tmp_path) -> SqliteProjectRepository:
    db_path = tmp_path / "test_api_projects.db"
    r = SqliteProjectRepository(db_path)

    def _override():
        return r

    app.dependency_overrides[get_project_repository] = _override
    yield r
    app.dependency_overrides.clear()


def test_generate_project_id_rule() -> None:
    pid1 = generate_project_id("Lean Management Review")
    assert pid1.startswith("lean-management-review-")
    assert len(pid1) == len("lean-management-review-") + 6

    # Non-ASCII or symbols fallback
    pid2 = generate_project_id("!!!")
    assert pid2.startswith("project-")


def test_api_create_list_get_update_archive(repo: SqliteProjectRepository) -> None:
    # 1. Create project via POST
    payload = {
        "title": "Systematic Review of AI",
        "description": "Scope description",
        "protocol_version": "1.1",
    }
    create_resp = client.post("/projects", json=payload)
    assert create_resp.status_code == 201
    created_data = create_resp.json()
    project_id = created_data["project_id"]
    assert project_id.startswith("systematic-review-of-ai-")
    assert created_data["title"] == "Systematic Review of AI"
    assert created_data["status"] == "active"

    # 2. Create duplicate title generates DIFFERENT project_id
    create_resp_dup = client.post("/projects", json=payload)
    assert create_resp_dup.status_code == 201
    dup_id = create_resp_dup.json()["project_id"]
    assert dup_id != project_id

    # 3. Get project by ID
    get_resp = client.get(f"/projects/{project_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["project_id"] == project_id

    # 4. List projects
    list_resp = client.get("/projects")
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] == 2

    # 5. Update project (Rename) preserves project_id
    update_payload = {
        "title": "Updated Title of AI Review",
        "description": "New scope",
        "protocol_version": "1.2",
    }
    put_resp = client.put(f"/projects/{project_id}", json=update_payload)
    assert put_resp.status_code == 200
    put_data = put_resp.json()
    assert put_data["project_id"] == project_id  # Preserved!
    assert put_data["title"] == "Updated Title of AI Review"

    # 6. Archive project
    archive_resp = client.patch(f"/projects/{project_id}/archive")
    assert archive_resp.status_code == 200
    assert archive_resp.json()["status"] == "archived"

    # 7. List excluding archived returns only 1 active project
    list_active = client.get("/projects")
    assert list_active.json()["total"] == 1

    # 8. List including archived returns 2 projects
    list_all = client.get("/projects", params={"include_archived": True})
    assert list_all.json()["total"] == 2

    # 9. Restore project
    restore_resp = client.patch(f"/projects/{project_id}/restore")
    assert restore_resp.status_code == 200
    assert restore_resp.json()["status"] == "active"
