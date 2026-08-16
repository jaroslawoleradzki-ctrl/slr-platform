"""Integration tests for Synthesis Terminology Classification REST API endpoints."""

from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.main import app
from app.domain.extraction import (
    ExtractedGroupItemState,
    ExtractedValueState,
    ExtractionCompletenessStatus,
    ExtractionRecord,
    ExtractionRevision,
    ExtractionTemplate,
    ExtractionTemplateVersion,
    ValueOrigin,
    ValueStatus,
)
from app.domain.project import Project
from app.repositories.extraction_repository import SqliteExtractionRepository
from app.repositories.extraction_template_repository import SqliteExtractionTemplateRepository
from app.repositories.project_repository import SqliteProjectRepository


@pytest.fixture
def client(tmp_path: Path, monkeypatch):
    test_db = tmp_path / "synthesis_api_test.db"
    monkeypatch.setenv("SLR_DATABASE_PATH", str(test_db))

    proj_repo = SqliteProjectRepository(test_db)
    proj_repo.create(Project(project_id="proj-api-test", title="API Test Project"))

    template_repo = SqliteExtractionTemplateRepository(test_db)
    template_repo.register_template(ExtractionTemplate(template_id="lean_energy", name="Lean Energy"))
    template_repo.register_version(
        ExtractionTemplateVersion(template_id="lean_energy", version="1.0.0", name="v1", is_published=True)
    )

    extraction_repo = SqliteExtractionRepository(test_db)
    pub_id = uuid4()
    rec = extraction_repo.create_record(
        ExtractionRecord(
            project_id="proj-api-test", publication_id=pub_id, template_id="lean_energy", template_version="1.0.0"
        )
    )
    extraction_repo.append_revision(
        ExtractionRevision(
            record_id=rec.record_id,
            project_id="proj-api-test",
            publication_id=pub_id,
            revision_index=1,
            reviewer_id="reviewer-1",
            completeness_status=ExtractionCompletenessStatus.COMPLETE,
            group_items=[
                ExtractedGroupItemState(
                    group_item_id=uuid4(),
                    group_key="lean_ee_relationships",
                    item_index=1,
                    values=[
                        ExtractedValueState(
                            field_key="lean_practice",
                            status=ValueStatus.PRESENT,
                            origin=ValueOrigin.REPORTED,
                            text_value="5S Visuals",
                            source_locator="Table 1",
                        ),
                        ExtractedValueState(
                            field_key="energy_effect_indicator",
                            status=ValueStatus.PRESENT,
                            origin=ValueOrigin.REPORTED,
                            text_value="10% kWh reduction",
                            source_locator="Table 1",
                        ),
                    ],
                )
            ],
        )
    )

    return TestClient(app)


def test_get_workspace_classifications_empty_categories(client: TestClient):
    resp = client.get("/api/v1/projects/proj-api-test/synthesis/classifications")
    assert resp.status_code == 200
    data = resp.json()

    assert data["project_id"] == "proj-api-test"
    assert len(data["lean_categories"]) == 0
    assert len(data["energy_categories"]) == 0
    assert len(data["lean_terms"]) == 1
    assert data["lean_terms"][0]["source_value"] == "5S Visuals"
    assert data["lean_terms"][0]["occurrence_count"] == 1
    assert data["lean_terms"][0]["analytical_category_id"] is None
    assert len(data["energy_terms"]) == 1
    assert data["energy_terms"][0]["source_value"] == "10% kWh reduction"
    assert data["stats"]["total_terms"] == 2
    assert data["stats"]["mapped_count"] == 0


def test_category_crud_endpoints(client: TestClient):
    # 1. Create Lean category
    create_resp = client.post(
        "/api/v1/projects/proj-api-test/synthesis/categories/lean",
        json={"category_id": "custom_lean", "name": "Custom Lean", "description": "Desc", "display_order": 1},
    )
    assert create_resp.status_code == 201
    assert create_resp.json()["category_id"] == "custom_lean"

    # 2. Duplicate Lean category -> 400
    dup_resp = client.post(
        "/api/v1/projects/proj-api-test/synthesis/categories/lean",
        json={"category_id": "custom_lean", "name": "Duplicate Lean"},
    )
    assert dup_resp.status_code == 400

    # 3. Update Lean category
    update_resp = client.put(
        "/api/v1/projects/proj-api-test/synthesis/categories/lean/custom_lean",
        json={"name": "Custom Lean Updated", "description": "Updated", "display_order": 2},
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["name"] == "Custom Lean Updated"

    # 4. Create and delete Energy category
    create_e_resp = client.post(
        "/api/v1/projects/proj-api-test/synthesis/categories/energy",
        json={"category_id": "custom_energy", "name": "Custom Energy", "display_order": 1},
    )
    assert create_e_resp.status_code == 201

    del_resp = client.delete("/api/v1/projects/proj-api-test/synthesis/categories/energy/custom_energy")
    assert del_resp.status_code == 204


def test_mapping_and_approval_flow_endpoints(client: TestClient):
    # Create category first
    client.post(
        "/api/v1/projects/proj-api-test/synthesis/categories/lean",
        json={"category_id": "5s", "name": "5S & Visual Management"},
    )

    # 1. Set mapping -> PENDING
    map_resp = client.put(
        "/api/v1/projects/proj-api-test/synthesis/classifications",
        json={
            "term_type": "lean_practice",
            "source_value": "5S Visuals",
            "analytical_category_id": "5s",
        },
    )
    assert map_resp.status_code == 200
    map_data = map_resp.json()
    assert map_data["analytical_category_id"] == "5s"
    assert map_data["approval_state"] == "pending"

    # 2. Explicit approval -> APPROVED
    app_resp = client.post(
        "/api/v1/projects/proj-api-test/synthesis/classifications/approve",
        json={
            "term_type": "lean_practice",
            "source_value": "5S Visuals",
            "reviewer_id": "reviewer-test",
        },
    )
    assert app_resp.status_code == 200
    app_data = app_resp.json()
    assert app_data["approval_state"] == "approved"
    assert app_data["approved_by"] == "reviewer-test"
    assert app_data["approved_at"] is not None

    # 3. Verify in workspace query
    ws_resp = client.get("/api/v1/projects/proj-api-test/synthesis/classifications")
    assert ws_resp.status_code == 200
    ws_data = ws_resp.json()
    assert ws_data["stats"]["mapped_count"] == 1
    assert ws_data["stats"]["approved_count"] == 1
    assert ws_data["lean_terms"][0]["analytical_category_name"] == "5S & Visual Management"
    assert ws_data["lean_terms"][0]["approval_state"] == "approved"


def test_api_validation_errors(client: TestClient):
    # Unknown project -> 404
    resp = client.get("/api/v1/projects/unknown-proj/synthesis/classifications")
    assert resp.status_code == 404

    # Mapping to unknown category -> 404
    resp2 = client.put(
        "/api/v1/projects/proj-api-test/synthesis/classifications",
        json={
            "term_type": "lean_practice",
            "source_value": "5S Visuals",
            "analytical_category_id": "unknown_cat",
        },
    )
    assert resp2.status_code == 404
