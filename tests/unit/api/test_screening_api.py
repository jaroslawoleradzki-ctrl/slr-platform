from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.main import app
from app.api.routers.screening import get_screening_repository
from app.repositories.screening_criterion_repository import (
    SqliteScreeningCriterionRepository,
)


@pytest.fixture
def test_repo(tmp_path: Path) -> SqliteScreeningCriterionRepository:
    db_path = tmp_path / "test_screening_api.db"
    return SqliteScreeningCriterionRepository(db_path)


@pytest.fixture
def client(test_repo: SqliteScreeningCriterionRepository) -> TestClient:
    app.dependency_overrides[get_screening_repository] = lambda: test_repo
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_create_screening_criterion_api(client: TestClient) -> None:
    payload = {
        "name": "Methodology Check",
        "description": "Must be randomized controlled trial.",
        "criterion_type": "inclusion",
        "screening_stage": "full_text",
        "display_order": 1,
        "is_active": True,
        "is_required": True,
    }
    response = client.post("/projects/proj-100/screening/criteria", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert "criterion_id" in data
    assert data["project_id"] == "proj-100"
    assert data["name"] == "Methodology Check"
    assert data["description"] == "Must be randomized controlled trial."
    assert data["criterion_type"] == "inclusion"
    assert data["screening_stage"] == "full_text"
    assert data["display_order"] == 1
    assert data["is_active"] is True
    assert data["is_required"] is True


def test_get_screening_criterion_api(client: TestClient) -> None:
    create_res = client.post(
        "/projects/proj-100/screening/criteria",
        json={
            "name": "Sample Criterion",
            "criterion_type": "exclusion",
            "screening_stage": "title_abstract",
        },
    )
    criterion_id = create_res.json()["criterion_id"]

    get_res = client.get(f"/projects/proj-100/screening/criteria/{criterion_id}")
    assert get_res.status_code == 200
    data = get_res.json()
    assert data["criterion_id"] == criterion_id
    assert data["name"] == "Sample Criterion"
    assert data["criterion_type"] == "exclusion"


def test_list_screening_criteria_api(client: TestClient) -> None:
    client.post(
        "/projects/proj-list/screening/criteria",
        json={
            "name": "Second Order",
            "criterion_type": "inclusion",
            "screening_stage": "both",
            "display_order": 2,
        },
    )
    client.post(
        "/projects/proj-list/screening/criteria",
        json={
            "name": "First Order",
            "criterion_type": "exclusion",
            "screening_stage": "title_abstract",
            "display_order": 1,
        },
    )

    list_res = client.get("/projects/proj-list/screening/criteria")
    assert list_res.status_code == 200
    data = list_res.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2
    # Verify deterministic ordering by display_order
    assert data["items"][0]["name"] == "First Order"
    assert data["items"][1]["name"] == "Second Order"


def test_update_screening_criterion_api(client: TestClient) -> None:
    create_res = client.post(
        "/projects/proj-100/screening/criteria",
        json={
            "name": "Initial Name",
            "description": "Initial Desc",
            "criterion_type": "inclusion",
            "screening_stage": "title_abstract",
            "display_order": 0,
        },
    )
    criterion_id = create_res.json()["criterion_id"]

    update_payload = {
        "name": "Updated Name",
        "description": "Updated Desc",
        "criterion_type": "exclusion",
        "screening_stage": "full_text",
        "display_order": 5,
        "is_active": False,
        "is_required": False,
    }
    update_res = client.put(
        f"/projects/proj-100/screening/criteria/{criterion_id}",
        json=update_payload,
    )
    assert update_res.status_code == 200
    data = update_res.json()
    assert data["criterion_id"] == criterion_id
    assert data["project_id"] == "proj-100"
    assert data["name"] == "Updated Name"
    assert data["description"] == "Updated Desc"
    assert data["criterion_type"] == "exclusion"
    assert data["screening_stage"] == "full_text"
    assert data["display_order"] == 5
    assert data["is_active"] is False
    assert data["is_required"] is False


def test_deactivate_screening_criterion_api(client: TestClient) -> None:
    create_res = client.post(
        "/projects/proj-100/screening/criteria",
        json={
            "name": "To Deactivate",
            "criterion_type": "inclusion",
            "screening_stage": "both",
            "is_active": True,
        },
    )
    criterion_id = create_res.json()["criterion_id"]

    patch_res = client.patch(
        f"/projects/proj-100/screening/criteria/{criterion_id}/deactivate"
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["is_active"] is False

    # Confirm via GET that is_active is False
    get_res = client.get(f"/projects/proj-100/screening/criteria/{criterion_id}")
    assert get_res.json()["is_active"] is False


def test_list_active_only_query_param(client: TestClient) -> None:
    c1 = client.post(
        "/projects/proj-active/screening/criteria",
        json={
            "name": "Active One",
            "criterion_type": "inclusion",
            "screening_stage": "both",
            "is_active": True,
        },
    ).json()

    client.post(
        "/projects/proj-active/screening/criteria",
        json={
            "name": "Inactive One",
            "criterion_type": "exclusion",
            "screening_stage": "both",
            "is_active": False,
        },
    )

    # Default list includes both
    res_all = client.get("/projects/proj-active/screening/criteria")
    assert res_all.json()["total"] == 2

    # active_only=true returns only active one
    res_active = client.get("/projects/proj-active/screening/criteria?active_only=true")
    assert res_active.json()["total"] == 1
    assert res_active.json()["items"][0]["criterion_id"] == c1["criterion_id"]


def test_validation_errors(client: TestClient) -> None:
    # Blank name
    res1 = client.post(
        "/projects/proj-val/screening/criteria",
        json={
            "name": "   ",
            "criterion_type": "inclusion",
            "screening_stage": "both",
        },
    )
    assert res1.status_code == 422

    # Negative display_order
    res2 = client.post(
        "/projects/proj-val/screening/criteria",
        json={
            "name": "Valid Name",
            "criterion_type": "inclusion",
            "screening_stage": "both",
            "display_order": -5,
        },
    )
    assert res2.status_code == 422

    # Invalid criterion_type enum
    res3 = client.post(
        "/projects/proj-val/screening/criteria",
        json={
            "name": "Valid Name",
            "criterion_type": "invalid_type",
            "screening_stage": "both",
        },
    )
    assert res3.status_code == 422

    # Invalid screening_stage enum
    res4 = client.post(
        "/projects/proj-val/screening/criteria",
        json={
            "name": "Valid Name",
            "criterion_type": "inclusion",
            "screening_stage": "invalid_stage",
        },
    )
    assert res4.status_code == 422


def test_404_nonexistent_criterion(client: TestClient) -> None:
    fake_id = uuid4()
    get_res = client.get(f"/projects/proj-100/screening/criteria/{fake_id}")
    assert get_res.status_code == 404

    put_res = client.put(
        f"/projects/proj-100/screening/criteria/{fake_id}",
        json={
            "name": "Name",
            "criterion_type": "inclusion",
            "screening_stage": "both",
        },
    )
    assert put_res.status_code == 404

    deactivate_res = client.patch(
        f"/projects/proj-100/screening/criteria/{fake_id}/deactivate"
    )
    assert deactivate_res.status_code == 404


def test_cross_project_isolation_api(client: TestClient) -> None:
    # Create criterion in project A
    create_res = client.post(
        "/projects/project-A/screening/criteria",
        json={
            "name": "Project A Criterion",
            "criterion_type": "inclusion",
            "screening_stage": "both",
        },
    )
    criterion_id = create_res.json()["criterion_id"]

    # GET via project-B URL returns 404
    get_res = client.get(f"/projects/project-B/screening/criteria/{criterion_id}")
    assert get_res.status_code == 404

    # PUT via project-B URL returns 404
    put_res = client.put(
        f"/projects/project-B/screening/criteria/{criterion_id}",
        json={
            "name": "Hacked Name",
            "criterion_type": "inclusion",
            "screening_stage": "both",
        },
    )
    assert put_res.status_code == 404

    # PATCH deactivate via project-B URL returns 404
    deactivate_res = client.patch(
        f"/projects/project-B/screening/criteria/{criterion_id}/deactivate"
    )
    assert deactivate_res.status_code == 404

    # Confirm original criterion in project-A remains unchanged
    orig_res = client.get(f"/projects/project-A/screening/criteria/{criterion_id}")
    assert orig_res.status_code == 200
    assert orig_res.json()["name"] == "Project A Criterion"
    assert orig_res.json()["is_active"] is True
