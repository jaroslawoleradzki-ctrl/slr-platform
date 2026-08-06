from fastapi.testclient import TestClient

from app.api.main import app
from app.domain.author import Author
from app.domain.identifiers import Identifier, IdentifierType
from app.domain.provenance import ProvenanceEntry
from app.domain.publication import Publication
from app.repositories.duplicate_review_decision_repository import InMemoryDuplicateReviewDecisionRepository
from app.repositories.project_publication_repository import DemoProjectPublicationRepository
from app.services.project_duplicate_service import ProjectDuplicateService

client = TestClient(app)


def test_full_duplicate_review_lifecycle_workflow() -> None:
    """Verify complete API integration workflow: GET list -> GET initial PENDING -> POST APPROVE -> GET APPROVE -> POST REJECT -> GET REJECT -> no publication loss."""
    # Step 1: GET list of candidate duplicate groups
    res_list = client.get("/projects/lean_energy/duplicate-groups")
    assert res_list.status_code == 200
    groups_data = res_list.json()
    assert groups_data["total_groups_count"] > 0
    group = groups_data["groups"][0]
    group_id = group["group_id"]
    initial_records_count = group["records_count"]
    initial_record_ids = [r["id"] for r in group["records"]]

    # Step 2 & 3: GET initial decision (PENDING, rationale: null)
    res_get_1 = client.get(f"/projects/lean_energy/duplicate-groups/{group_id}/decision")
    assert res_get_1.status_code == 200
    assert res_get_1.json()["decision"] == "PENDING"
    assert res_get_1.json()["rationale"] is None

    # Step 4: POST APPROVE with rationale
    res_post_1 = client.post(
        f"/projects/lean_energy/duplicate-groups/{group_id}/decision",
        json={"decision": "APPROVE", "rationale": "Verified abstract and author overlap"},
    )
    assert res_post_1.status_code == 200
    assert res_post_1.json()["decision"] == "APPROVE"
    assert res_post_1.json()["rationale"] == "Verified abstract and author overlap"

    # Step 5: GET decision returns APPROVE and saved rationale
    res_get_2 = client.get(f"/projects/lean_energy/duplicate-groups/{group_id}/decision")
    assert res_get_2.status_code == 200
    assert res_get_2.json()["decision"] == "APPROVE"
    assert res_get_2.json()["rationale"] == "Verified abstract and author overlap"

    # Step 6: POST REJECT with new rationale
    res_post_2 = client.post(
        f"/projects/lean_energy/duplicate-groups/{group_id}/decision",
        json={"decision": "REJECT", "rationale": "Different publication year upon full text inspection"},
    )
    assert res_post_2.status_code == 200
    assert res_post_2.json()["decision"] == "REJECT"
    assert res_post_2.json()["rationale"] == "Different publication year upon full text inspection"

    # Step 7 & 8: GET decision returns REJECT and updated rationale (overwritten)
    res_get_3 = client.get(f"/projects/lean_energy/duplicate-groups/{group_id}/decision")
    assert res_get_3.status_code == 200
    assert res_get_3.json()["decision"] == "REJECT"
    assert res_get_3.json()["rationale"] == "Different publication year upon full text inspection"

    # Step 9 & 10: Candidate group list remains available; no record deletion or physical merge executed
    res_list_after = client.get("/projects/lean_energy/duplicate-groups")
    assert res_list_after.status_code == 200
    after_groups = res_list_after.json()["groups"]
    matching_group = next(g for g in after_groups if g["group_id"] == group_id)
    after_record_ids = [r["id"] for r in matching_group["records"]]

    assert matching_group["status"] == "REJECT"
    assert matching_group["records_count"] == initial_records_count
    assert after_record_ids == initial_record_ids


def test_decision_workflow_edge_cases_and_validations() -> None:
    """Verify rationale trimming, null handling, length boundary (1000 chars), enum validation, and project isolation."""
    res_list = client.get("/projects/lean_energy/duplicate-groups")
    group_id = res_list.json()["groups"][0]["group_id"]

    # 1. Decision without rationale -> rationale is null
    r1 = client.post(
        f"/projects/lean_energy/duplicate-groups/{group_id}/decision",
        json={"decision": "APPROVE"},
    )
    assert r1.status_code == 200
    assert r1.json()["rationale"] is None

    # 2. Whitespace rationale -> trimmed to null
    r2 = client.post(
        f"/projects/lean_energy/duplicate-groups/{group_id}/decision",
        json={"decision": "APPROVE", "rationale": "   \n\t  "},
    )
    assert r2.status_code == 200
    assert r2.json()["rationale"] is None

    # 3. Rationale exactly at 1000 characters -> accepted
    exact_1000 = "B" * 1000
    r3 = client.post(
        f"/projects/lean_energy/duplicate-groups/{group_id}/decision",
        json={"decision": "APPROVE", "rationale": exact_1000},
    )
    assert r3.status_code == 200
    assert r3.json()["rationale"] == exact_1000

    # 4. Rationale exceeding 1000 characters -> HTTP 422
    over_1000 = "B" * 1001
    r4 = client.post(
        f"/projects/lean_energy/duplicate-groups/{group_id}/decision",
        json={"decision": "APPROVE", "rationale": over_1000},
    )
    assert r4.status_code == 422

    # 5. Invalid decision enum -> HTTP 422
    r5 = client.post(
        f"/projects/lean_energy/duplicate-groups/{group_id}/decision",
        json={"decision": "INVALID_DECISION_ENUM"},
    )
    assert r5.status_code == 422

    # 6. Non-existent project -> HTTP 404
    r6 = client.get("/projects/non_existent_project_xyz/duplicate-groups")
    assert r6.status_code == 404

    # 7. Non-existent group -> HTTP 404
    r7 = client.get("/projects/lean_energy/duplicate-groups/non_existent_group_123/decision")
    assert r7.status_code == 404


def test_project_decision_isolation() -> None:
    """Verify same group_id in two distinct projects maintains isolated decisions and rationales."""
    pub1 = Publication(
        title="Isolated Paper A",
        authors=[Author(display_name="Author A")],
        publication_year=2021,
        identifiers=[Identifier(type=IdentifierType.DOI, value="10.1000/shared_doi")],
        provenance=[ProvenanceEntry(source="OpenAlex", source_record_id="W1")],
    )
    pub2 = Publication(
        title="Isolated Paper B",
        authors=[Author(display_name="Author B")],
        publication_year=2021,
        identifiers=[Identifier(type=IdentifierType.DOI, value="10.1000/shared_doi")],
        provenance=[ProvenanceEntry(source="Crossref", source_record_id="10.1000/shared_doi")],
    )

    proj_repo = DemoProjectPublicationRepository()
    proj_repo._projects_data = {
        "project_alpha": [pub1, pub2],
        "project_beta": [pub1, pub2],
    }
    decision_repo = InMemoryDuplicateReviewDecisionRepository()
    service = ProjectDuplicateService(repository=proj_repo, decision_repository=decision_repo)

    groups_alpha = service.get_candidate_duplicate_groups("project_alpha")
    groups_beta = service.get_candidate_duplicate_groups("project_beta")
    shared_group_id = groups_alpha.groups[0].group_id
    assert groups_beta.groups[0].group_id == shared_group_id

    # Record decision for project_alpha only
    service.record_decision("project_alpha", shared_group_id, "APPROVE", "Alpha rationale")

    # Verify project_alpha returns APPROVE while project_beta remains PENDING
    dec_alpha = service.get_decision("project_alpha", shared_group_id)
    dec_beta = service.get_decision("project_beta", shared_group_id)

    assert dec_alpha.decision.value == "APPROVE"
    assert dec_alpha.rationale == "Alpha rationale"
    assert dec_beta.decision.value == "PENDING"
    assert dec_beta.rationale is None

    # Record decision for project_beta
    service.record_decision("project_beta", shared_group_id, "REJECT", "Beta rationale")

    # Confirm project_beta returns REJECT and "Beta rationale"
    dec_beta_updated = service.get_decision("project_beta", shared_group_id)
    assert dec_beta_updated.decision.value == "REJECT"
    assert dec_beta_updated.rationale == "Beta rationale"

    # Re-confirm project_alpha still returns APPROVE and "Alpha rationale"
    dec_alpha_reconfirmed = service.get_decision("project_alpha", shared_group_id)
    assert dec_alpha_reconfirmed.decision.value == "APPROVE"
    assert dec_alpha_reconfirmed.rationale == "Alpha rationale"


def test_backend_response_determinism() -> None:
    """Verify backend API produces deterministic responses with stable group and record ordering across multiple invocations."""
    res1 = client.get("/projects/lean_energy/duplicate-groups").json()
    res2 = client.get("/projects/lean_energy/duplicate-groups").json()
    res3 = client.get("/projects/lean_energy/duplicate-groups").json()

    # 1. High level equivalence
    assert res1 == res2 == res3

    # 2. Group order stability
    group_ids_1 = [g["group_id"] for g in res1["groups"]]
    group_ids_2 = [g["group_id"] for g in res2["groups"]]
    assert group_ids_1 == group_ids_2

    # 3. Record order stability within groups
    for g1, g2 in zip(res1["groups"], res2["groups"]):
        record_ids_1 = [r["id"] for r in g1["records"]]
        record_ids_2 = [r["id"] for r in g2["records"]]
        assert record_ids_1 == record_ids_2
