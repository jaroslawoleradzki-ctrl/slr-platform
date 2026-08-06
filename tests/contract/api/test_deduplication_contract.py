import re
from pathlib import Path

from fastapi.testclient import TestClient

from app.api.dto.deduplication import (
    DuplicateGroupDecisionResponse,
    DuplicateGroupListResponse,
    DuplicateRecordPreviewResponse,
    ProvenanceEntryResponse,
)
from app.api.main import app

client = TestClient(app)


def test_duplicate_groups_endpoint_full_contract_schema() -> None:
    """Verify GET /projects/{project_id}/duplicate-groups matches full DTO contract."""
    response = client.get("/projects/lean_energy/duplicate-groups")
    assert response.status_code == 200

    data = response.json()

    # Validate high-level list response structure
    parsed_list = DuplicateGroupListResponse.model_validate(data)
    assert parsed_list.project_id == "lean_energy"
    assert parsed_list.total_groups_count == len(parsed_list.groups)
    assert len(parsed_list.groups) > 0

    # Validate individual group response contracts
    for group in parsed_list.groups:
        assert isinstance(group.group_id, str) and len(group.group_id) > 0
        assert isinstance(group.reason, str) and len(group.reason) > 0
        assert group.records_count == len(group.records)
        assert group.records_count >= 2
        assert group.status.value in {"PENDING", "APPROVE", "REJECT"}

        # Shared identifiers contract
        for ident in group.shared_identifiers:
            assert isinstance(ident.identifier_type, str)
            assert isinstance(ident.value, str)

        # Publication record preview contract
        for record in group.records:
            assert isinstance(record.id, str)
            assert isinstance(record.title, str)
            assert isinstance(record.authors, str)
            assert record.year is None or isinstance(record.year, int)
            assert isinstance(record.source, str)
            assert record.venue is None or isinstance(record.venue, str)
            assert record.doi is None or isinstance(record.doi, str)
            assert record.pmid is None or isinstance(record.pmid, str)
            assert record.openalex_id is None or isinstance(record.openalex_id, str)

            # Provenance contract
            for prov in record.provenance:
                assert isinstance(prov.source, str)
                assert isinstance(prov.source_record_id, str)
                assert prov.retrieved_at is None or isinstance(prov.retrieved_at, str)


def test_decision_endpoints_full_contract_schema() -> None:
    """Verify POST & GET /projects/{project_id}/duplicate-groups/{group_id}/decision contract."""
    res_list = client.get("/projects/lean_energy/duplicate-groups")
    group_id = res_list.json()["groups"][0]["group_id"]

    # 1. GET initial decision (PENDING)
    res_get_initial = client.get(f"/projects/lean_energy/duplicate-groups/{group_id}/decision")
    assert res_get_initial.status_code == 200
    initial_dto = DuplicateGroupDecisionResponse.model_validate(res_get_initial.json())
    assert initial_dto.project_id == "lean_energy"
    assert initial_dto.group_id == group_id
    assert initial_dto.decision.value == "PENDING"
    assert initial_dto.rationale is None

    # 2. POST APPROVE with rationale
    res_post = client.post(
        f"/projects/lean_energy/duplicate-groups/{group_id}/decision",
        json={"decision": "APPROVE", "rationale": "Verified matching abstracts"},
    )
    assert res_post.status_code == 200
    post_dto = DuplicateGroupDecisionResponse.model_validate(res_post.json())
    assert post_dto.project_id == "lean_energy"
    assert post_dto.group_id == group_id
    assert post_dto.decision.value == "APPROVE"
    assert post_dto.rationale == "Verified matching abstracts"

    # 3. GET recorded decision
    res_get_after = client.get(f"/projects/lean_energy/duplicate-groups/{group_id}/decision")
    assert res_get_after.status_code == 200
    after_dto = DuplicateGroupDecisionResponse.model_validate(res_get_after.json())
    assert after_dto == post_dto


def test_openapi_schema_contract() -> None:
    """Verify OpenAPI v3 schema contains required endpoints, methods, parameters and maxLength constraints."""
    openapi = app.openapi()
    assert openapi["info"]["title"] == "SLR Platform"
    paths = openapi["paths"]

    # 1. Verify endpoint registration
    assert "/projects/{project_id}/duplicate-groups" in paths
    assert "/projects/{project_id}/duplicate-groups/{group_id}/decision" in paths

    # 2. Verify methods
    list_op = paths["/projects/{project_id}/duplicate-groups"]["get"]
    decision_post_op = paths["/projects/{project_id}/duplicate-groups/{group_id}/decision"]["post"]
    decision_get_op = paths["/projects/{project_id}/duplicate-groups/{group_id}/decision"]["get"]

    assert list_op["summary"] == "Get candidate duplicate groups for human review"
    assert decision_post_op["summary"] == "Record reviewer decision for a candidate duplicate group"
    assert decision_get_op["summary"] == "Get recorded decision for a candidate duplicate group"

    # 3. Verify request body schema for POST decision
    schemas = openapi["components"]["schemas"]
    req_schema = schemas["DuplicateGroupDecisionRequest"]
    assert "decision" in req_schema["properties"]
    assert "rationale" in req_schema["properties"]

    rationale_prop = req_schema["properties"]["rationale"]
    # Handle anyOf / nullable schema structure in OpenAPI
    if "anyOf" in rationale_prop:
        str_branch = next(b for b in rationale_prop["anyOf"] if b.get("type") == "string")
        assert str_branch.get("maxLength") == 1000
    else:
        assert rationale_prop.get("maxLength") == 1000

    decision_type_schema = schemas["DuplicateDecisionType"]
    assert set(decision_type_schema["enum"]) == {"APPROVE", "REJECT"}


def test_python_dto_to_typescript_types_parity_contract() -> None:
    """Verify 1-to-1 field parity between Python backend DTOs and TypeScript interfaces."""
    ts_types_file = Path(__file__).parents[3] / "frontend" / "src" / "types" / "index.ts"
    assert ts_types_file.exists(), f"TypeScript types file not found at {ts_types_file}"
    ts_content = ts_types_file.read_text(encoding="utf-8")

    # Check key frontend TypeScript interfaces exist
    assert "export interface ApiDuplicateGroupListResponse" in ts_content
    assert "export interface ApiDuplicateGroup" in ts_content
    assert "export interface ApiDuplicateRecordPreview" in ts_content
    assert "export interface ApiProvenanceEntry" in ts_content
    assert "export interface ApiDuplicateGroupDecisionResponse" in ts_content

    # Check DuplicateRecordPreviewResponse Python fields exist in TypeScript ApiDuplicateRecordPreview
    py_record_fields = set(DuplicateRecordPreviewResponse.model_fields.keys())
    for field in py_record_fields:
        # Match field name in TypeScript interface
        pattern = rf"\b{field}\??\s*:"
        assert re.search(pattern, ts_content), f"Python DTO field '{field}' missing in TypeScript types"

    # Check ProvenanceEntryResponse Python fields exist in TypeScript ApiProvenanceEntry
    py_prov_fields = set(ProvenanceEntryResponse.model_fields.keys())
    for field in py_prov_fields:
        pattern = rf"\b{field}\??\s*:"
        assert re.search(pattern, ts_content), f"Python DTO field '{field}' missing in TypeScript types"

    # Check DuplicateGroupResponse Python fields exist in TypeScript ApiDuplicateGroup
    from app.api.dto.deduplication import DuplicateGroupResponse
    py_group_fields = set(DuplicateGroupResponse.model_fields.keys())
    for field in py_group_fields:
        pattern = rf"\b{field}\??\s*:"
        assert re.search(pattern, ts_content), f"Python DTO field '{field}' missing in TypeScript ApiDuplicateGroup"
