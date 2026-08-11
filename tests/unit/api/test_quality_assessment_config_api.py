from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.main import app
from app.domain.project import Project
from app.domain.quality_assessment import (
    QualityAssessmentTemplate,
    QualityAssessmentTool,
)
from app.repositories.project_repository import SqliteProjectRepository
from app.repositories.sqlite_quality_assessment_repository import (
    SqliteProjectQualityAssessmentConfigurationRepository,
    SqliteQualityAssessmentCatalogRepository,
)
from app.services.quality_assessment_configuration_service import (
    CASP_INSPIRED_TOOL_ID,
    DefaultQualityAssessmentConfigurationService,
)


@pytest.fixture
def api_client(tmp_path: Path):
    db_path = tmp_path / "api_test.db"
    catalog_repo = SqliteQualityAssessmentCatalogRepository(db_path)
    config_repo = SqliteProjectQualityAssessmentConfigurationRepository(db_path)
    project_repo = SqliteProjectRepository(db_path)

    service = DefaultQualityAssessmentConfigurationService(
        catalog_repo=catalog_repo,
        config_repo=config_repo,
        project_repo=project_repo,
    )
    service.seed_built_in_catalog()

    # Pre-create project
    project_repo.create(Project(project_id="lean_energy", title="Lean Energy"))

    # Seed test template under CASP tool
    tid = uuid4()
    tmpl = QualityAssessmentTemplate(
        template_id=tid,
        tool_id=CASP_INSPIRED_TOOL_ID,
        template_key="lean_energy_qa",
        name="Lean Energy QA v1",
        version=1,
    )
    catalog_repo.create_template_version(tmpl)

    from app.api.routers.quality_assessment import get_config_service

    app.dependency_overrides[get_config_service] = lambda: service

    with TestClient(app) as client:
        yield client, tid, db_path

    app.dependency_overrides.clear()


def test_list_tools_api(api_client):
    client, _, _ = api_client
    response = client.get("/quality-assessment/tools")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    tool_ids = [t["tool_id"] for t in data]
    assert CASP_INSPIRED_TOOL_ID in tool_ids


def test_list_templates_for_tool_api(api_client):
    client, tid, _ = api_client
    response = client.get(f"/quality-assessment/tools/{CASP_INSPIRED_TOOL_ID}/templates")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    template_ids = [t["template_id"] for t in data]
    assert str(tid) in template_ids

    # Missing tool -> 404
    resp_missing = client.get("/quality-assessment/tools/missing_tool/templates")
    assert resp_missing.status_code == 404


def test_get_and_put_project_configuration_api(api_client):
    client, tid, _ = api_client

    # 1. Initially no config -> 404
    get_resp = client.get("/projects/lean_energy/quality-assessment/configuration")
    assert get_resp.status_code == 404

    # 2. PUT valid configuration -> 200 OK
    put_payload = {
        "tool_id": CASP_INSPIRED_TOOL_ID,
        "template_id": str(tid),
    }
    put_resp = client.put(
        "/projects/lean_energy/quality-assessment/configuration", json=put_payload
    )
    assert put_resp.status_code == 200
    put_data = put_resp.json()
    assert put_data["project_id"] == "lean_energy"
    assert put_data["tool_id"] == CASP_INSPIRED_TOOL_ID
    assert put_data["template_id"] == str(tid)

    # 3. GET configuration -> 200 OK
    get_resp2 = client.get("/projects/lean_energy/quality-assessment/configuration")
    assert get_resp2.status_code == 200
    assert get_resp2.json()["template_id"] == str(tid)


def test_put_project_configuration_validation_errors(api_client):
    client, tid, db_path = api_client
    catalog_repo = SqliteQualityAssessmentCatalogRepository(db_path)

    # Seed Tool B
    tool_b = QualityAssessmentTool(tool_id="jbi_tool", name="JBI Tool")
    catalog_repo.create_tool(tool_b)

    # 1. Missing project -> 404
    put_resp_missing_proj = client.put(
        "/projects/missing_project/quality-assessment/configuration",
        json={"tool_id": CASP_INSPIRED_TOOL_ID, "template_id": str(tid)},
    )
    assert put_resp_missing_proj.status_code == 404

    # 2. Cross-tool template mismatch -> 422 Unprocessable Content
    put_resp_mismatch = client.put(
        "/projects/lean_energy/quality-assessment/configuration",
        json={"tool_id": "jbi_tool", "template_id": str(tid)}, # Template tid belongs to CASP, NOT JBI
    )
    assert put_resp_mismatch.status_code == 422
