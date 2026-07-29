from copy import deepcopy
from datetime import datetime, timezone
from uuid import UUID
import pytest

from fastapi.testclient import TestClient

from app.api.dto.deduplication import DuplicateDecisionStatus
from app.api.main import app
from app.domain.author import Author
from app.domain.duplicate_review import DuplicateDecision, DuplicateGroupReviewDecision
from app.domain.identifiers import Identifier, IdentifierType
from app.domain.provenance import ProvenanceEntry
from app.domain.publication import Publication
from app.domain.venue import Venue, VenueType
from app.repositories.duplicate_review_decision_repository import (
    InMemoryDuplicateReviewDecisionRepository,
    in_memory_duplicate_review_decision_repository,
)
from app.services.project_duplicate_service import ProjectDuplicateService

client = TestClient(app)
_TIME = datetime(2026, 7, 1, 10, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def reset_in_memory_decisions() -> None:
    in_memory_duplicate_review_decision_repository.clear()


class DummyProjectRepository:
    """Test repository verifying DI without hardcoded project_id checks."""

    def __init__(self, projects: dict[str, list[Publication]]) -> None:
        self._projects = projects

    def get_publications(self, project_id: str) -> list[Publication]:
        from app.repositories.project_publication_repository import ProjectNotFoundError

        if project_id not in self._projects:
            raise ProjectNotFoundError(project_id)
        return list(self._projects[project_id])


def test_service_does_not_depend_on_hardcoded_project_ids() -> None:
    custom_project_id = "custom_test_project_999"
    pub1 = Publication(
        record_id=UUID("00000000-0000-0000-0000-000000000001"),
        title="Custom Study Paper A",
        authors=[Author(display_name="Author A")],
        identifiers=[Identifier(type=IdentifierType.DOI, value="10.1000/custom.doi")],
        provenance=[ProvenanceEntry(source="CustomSource", source_record_id="REC-A")],
        created_at=_TIME,
    )
    pub2 = Publication(
        record_id=UUID("00000000-0000-0000-0000-000000000002"),
        title="Custom Study Paper B",
        authors=[Author(display_name="Author B")],
        identifiers=[Identifier(type=IdentifierType.DOI, value="10.1000/custom.doi")],
        provenance=[ProvenanceEntry(source="CustomSource", source_record_id="REC-B")],
        created_at=_TIME,
    )

    repo = DummyProjectRepository({custom_project_id: [pub1, pub2]})
    service = ProjectDuplicateService(repository=repo)

    result = service.get_candidate_duplicate_groups(custom_project_id)
    assert result.project_id == custom_project_id
    assert result.total_groups_count == 1
    assert len(result.groups) == 1
    assert result.groups[0].shared_identifiers[0].identifier_type == "doi"
    assert result.groups[0].shared_identifiers[0].value == "10.1000/custom.doi"


def test_publications_are_not_mutated_during_building_or_mapping() -> None:
    pub1 = Publication(
        record_id=UUID("00000000-0000-0000-0000-000000000011"),
        title="Immutable Study Title A",
        authors=[Author(display_name="Author A")],
        identifiers=[Identifier(type=IdentifierType.DOI, value="10.1000/immutable")],
        provenance=[ProvenanceEntry(source="SourceA", source_record_id="R11")],
        created_at=_TIME,
    )
    pub2 = Publication(
        record_id=UUID("00000000-0000-0000-0000-000000000012"),
        title="Immutable Study Title B",
        authors=[Author(display_name="Author B")],
        identifiers=[Identifier(type=IdentifierType.DOI, value="10.1000/immutable")],
        provenance=[ProvenanceEntry(source="SourceB", source_record_id="R12")],
        created_at=_TIME,
    )

    pub1_copy = deepcopy(pub1)
    pub2_copy = deepcopy(pub2)

    repo = DummyProjectRepository({"immutability_test": [pub1, pub2]})
    service = ProjectDuplicateService(repository=repo)
    service.get_candidate_duplicate_groups("immutability_test")

    assert pub1 == pub1_copy
    assert pub2 == pub2_copy


def test_doi_matching_as_separate_case() -> None:
    pub1 = Publication(
        record_id=UUID("00000000-0000-0000-0000-000000000021"),
        title="DOI Paper First",
        identifiers=[Identifier(type=IdentifierType.DOI, value="https://doi.org/10.1000/shared.doi")],
        provenance=[ProvenanceEntry(source="OpenAlex", source_record_id="W1")],
        created_at=_TIME,
    )
    pub2 = Publication(
        record_id=UUID("00000000-0000-0000-0000-000000000022"),
        title="DOI Paper Second",
        identifiers=[Identifier(type=IdentifierType.DOI, value="10.1000/shared.doi")],
        provenance=[ProvenanceEntry(source="Crossref", source_record_id="W2")],
        created_at=_TIME,
    )

    repo = DummyProjectRepository({"doi_proj": [pub1, pub2]})
    service = ProjectDuplicateService(repository=repo)
    result = service.get_candidate_duplicate_groups("doi_proj")

    assert result.total_groups_count == 1
    assert result.groups[0].shared_identifiers[0].identifier_type == "doi"
    assert result.groups[0].shared_identifiers[0].value == "10.1000/shared.doi"


def test_pmid_matching_as_separate_case() -> None:
    pub1 = Publication(
        record_id=UUID("00000000-0000-0000-0000-000000000031"),
        title="PMID Paper A",
        identifiers=[Identifier(type=IdentifierType.PMID, value="99887766")],
        provenance=[ProvenanceEntry(source="PubMed", source_record_id="PMID1")],
        created_at=_TIME,
    )
    pub2 = Publication(
        record_id=UUID("00000000-0000-0000-0000-000000000032"),
        title="PMID Paper B",
        identifiers=[Identifier(type=IdentifierType.PMID, value="99887766")],
        provenance=[ProvenanceEntry(source="Semantic Scholar", source_record_id="PMID2")],
        created_at=_TIME,
    )

    repo = DummyProjectRepository({"pmid_proj": [pub1, pub2]})
    service = ProjectDuplicateService(repository=repo)
    result = service.get_candidate_duplicate_groups("pmid_proj")

    assert result.total_groups_count == 1
    assert result.groups[0].shared_identifiers[0].identifier_type == "pmid"
    assert result.groups[0].shared_identifiers[0].value == "99887766"


def test_openalex_id_matching_as_separate_case() -> None:
    pub1 = Publication(
        record_id=UUID("00000000-0000-0000-0000-000000000041"),
        title="OpenAlex Paper Alpha",
        identifiers=[Identifier(type=IdentifierType.OPENALEX, value="W5544332211")],
        provenance=[ProvenanceEntry(source="OpenAlex", source_record_id="OA1")],
        created_at=_TIME,
    )
    pub2 = Publication(
        record_id=UUID("00000000-0000-0000-0000-000000000042"),
        title="OpenAlex Paper Beta",
        identifiers=[Identifier(type=IdentifierType.OPENALEX, value="W5544332211")],
        provenance=[ProvenanceEntry(source="OpenAlex", source_record_id="OA2")],
        created_at=_TIME,
    )

    repo = DummyProjectRepository({"openalex_proj": [pub1, pub2]})
    service = ProjectDuplicateService(repository=repo)
    result = service.get_candidate_duplicate_groups("openalex_proj")

    assert result.total_groups_count == 1
    assert result.groups[0].shared_identifiers[0].identifier_type == "openalex"
    assert result.groups[0].shared_identifiers[0].value == "W5544332211"


def test_get_duplicate_groups_returns_venue_and_provenance() -> None:
    pub1 = Publication(
        record_id=UUID("00000000-0000-0000-0000-000000000051"),
        title="Journal Article A",
        venue=Venue(name="Journal of Cleaner Production", type=VenueType.JOURNAL),
        identifiers=[Identifier(type=IdentifierType.DOI, value="10.1000/venue.doi")],
        provenance=[ProvenanceEntry(source="OpenAlex", source_record_id="W51", retrieved_at=_TIME)],
        created_at=_TIME,
    )
    pub2 = Publication(
        record_id=UUID("00000000-0000-0000-0000-000000000052"),
        title="Journal Article B",
        venue=Venue(name="Journal of Cleaner Production", type=VenueType.JOURNAL),
        identifiers=[Identifier(type=IdentifierType.DOI, value="10.1000/venue.doi")],
        provenance=[ProvenanceEntry(source="Crossref", source_record_id="CR52", retrieved_at=_TIME)],
        created_at=_TIME,
    )

    repo = DummyProjectRepository({"venue_proj": [pub1, pub2]})
    service = ProjectDuplicateService(repository=repo)
    result = service.get_candidate_duplicate_groups("venue_proj")

    rec1 = result.groups[0].records[0]
    rec2 = result.groups[0].records[1]

    assert rec1.venue == "Journal of Cleaner Production"
    assert len(rec1.provenance) == 1
    assert rec1.provenance[0].source == "OpenAlex"
    assert rec1.provenance[0].source_record_id == "W51"

    assert rec2.venue == "Journal of Cleaner Production"
    assert len(rec2.provenance) == 1
    assert rec2.provenance[0].source == "Crossref"
    assert rec2.provenance[0].source_record_id == "CR52"


def test_get_duplicate_groups_lean_energy_endpoint_returns_200() -> None:
    response = client.get("/projects/lean_energy/duplicate-groups")
    assert response.status_code == 200

    data = response.json()
    assert data["project_id"] == "lean_energy"
    assert data["total_groups_count"] == 2
    assert "similarity_score" not in data["groups"][0]
    assert data["groups"][0]["status"] == "PENDING"
    assert len(data["groups"][0]["records"][0]["provenance"]) >= 1


def test_get_duplicate_groups_ai_architecture_endpoint_returns_200_with_empty_groups() -> None:
    response = client.get("/projects/ai_architecture/duplicate-groups")
    assert response.status_code == 200

    data = response.json()
    assert data["project_id"] == "ai_architecture"
    assert data["total_groups_count"] == 0
    assert data["groups"] == []


def test_get_duplicate_groups_unknown_project_returns_404() -> None:
    response = client.get("/projects/unknown_project_123/duplicate-groups")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


# --- PHASE 6.5 DECISION & RATIONALE TESTS ---


def test_post_decision_approve_with_rationale() -> None:
    res = client.get("/projects/lean_energy/duplicate-groups")
    group_id = res.json()["groups"][0]["group_id"]

    response = client.post(
        f"/projects/lean_energy/duplicate-groups/{group_id}/decision",
        json={
            "decision": "APPROVE",
            "rationale": "  Verified full text agreement between sources.  ",
        },
    )
    assert response.status_code == 200
    assert response.json() == {
        "project_id": "lean_energy",
        "group_id": group_id,
        "decision": "APPROVE",
        "rationale": "Verified full text agreement between sources.",
    }

    # Verify GET decision returns APPROVE and rationale
    get_res = client.get(f"/projects/lean_energy/duplicate-groups/{group_id}/decision")
    assert get_res.status_code == 200
    assert get_res.json() == {
        "project_id": "lean_energy",
        "group_id": group_id,
        "decision": "APPROVE",
        "rationale": "Verified full text agreement between sources.",
    }


def test_post_decision_without_rationale() -> None:
    res = client.get("/projects/lean_energy/duplicate-groups")
    group_id = res.json()["groups"][0]["group_id"]

    response = client.post(
        f"/projects/lean_energy/duplicate-groups/{group_id}/decision",
        json={"decision": "REJECT"},
    )
    assert response.status_code == 200
    assert response.json() == {
        "project_id": "lean_energy",
        "group_id": group_id,
        "decision": "REJECT",
        "rationale": None,
    }


def test_empty_and_whitespace_rationale_becomes_none() -> None:
    res = client.get("/projects/lean_energy/duplicate-groups")
    group_id = res.json()["groups"][0]["group_id"]

    response = client.post(
        f"/projects/lean_energy/duplicate-groups/{group_id}/decision",
        json={"decision": "APPROVE", "rationale": "   \n\t  "},
    )
    assert response.status_code == 200
    assert response.json()["rationale"] is None


def test_rationale_exceeding_max_length_returns_422() -> None:
    res = client.get("/projects/lean_energy/duplicate-groups")
    group_id = res.json()["groups"][0]["group_id"]

    overlong_rationale = "A" * 1001

    response = client.post(
        f"/projects/lean_energy/duplicate-groups/{group_id}/decision",
        json={"decision": "APPROVE", "rationale": overlong_rationale},
    )
    assert response.status_code == 422
    assert "exceeds maximum length" in response.json()["detail"]


def test_overwrite_decision_and_rationale() -> None:
    res = client.get("/projects/lean_energy/duplicate-groups")
    group_id = res.json()["groups"][0]["group_id"]

    # 1. First Approve with rationale
    client.post(
        f"/projects/lean_energy/duplicate-groups/{group_id}/decision",
        json={"decision": "APPROVE", "rationale": "First decision rationale"},
    )
    assert client.get(f"/projects/lean_energy/duplicate-groups/{group_id}/decision").json()["rationale"] == "First decision rationale"

    # 2. Overwrite with Reject and new rationale
    response = client.post(
        f"/projects/lean_energy/duplicate-groups/{group_id}/decision",
        json={"decision": "REJECT", "rationale": "Updated decision rationale"},
    )
    assert response.status_code == 200
    assert response.json()["decision"] == "REJECT"
    assert response.json()["rationale"] == "Updated decision rationale"

    # 3. Read again
    get_res = client.get(f"/projects/lean_energy/duplicate-groups/{group_id}/decision")
    assert get_res.json()["decision"] == "REJECT"
    assert get_res.json()["rationale"] == "Updated decision rationale"


def test_post_decision_invalid_group_returns_404() -> None:
    response = client.post(
        "/projects/lean_energy/duplicate-groups/non_existent_group_uuid/decision",
        json={"decision": "APPROVE"},
    )
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_get_decision_invalid_group_returns_404() -> None:
    response = client.get("/projects/lean_energy/duplicate-groups/non_existent_group_uuid/decision")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_post_decision_invalid_enum_returns_422() -> None:
    res = client.get("/projects/lean_energy/duplicate-groups")
    group_id = res.json()["groups"][0]["group_id"]

    response = client.post(
        f"/projects/lean_energy/duplicate-groups/{group_id}/decision",
        json={"decision": "INVALID_DECISION_TYPE"},
    )
    assert response.status_code == 422


def test_read_decision_defaults_to_pending() -> None:
    res = client.get("/projects/lean_energy/duplicate-groups")
    group_id = res.json()["groups"][0]["group_id"]

    get_res = client.get(f"/projects/lean_energy/duplicate-groups/{group_id}/decision")
    assert get_res.status_code == 200
    assert get_res.json() == {
        "project_id": "lean_energy",
        "group_id": group_id,
        "decision": "PENDING",
        "rationale": None,
    }


def test_repository_isolation_between_instances() -> None:
    repo1 = InMemoryDuplicateReviewDecisionRepository()
    repo2 = InMemoryDuplicateReviewDecisionRepository()

    rec = DuplicateGroupReviewDecision(decision=DuplicateDecision.APPROVE, rationale="Test rationale")

    repo1.save_decision("proj_1", "g1", rec)
    assert repo1.get_decision("proj_1", "g1") == rec
    assert repo2.get_decision("proj_1", "g1") is None


def test_decision_isolation_between_projects_sharing_same_group_id() -> None:
    """Verify that projects A and B sharing the same group_id maintain isolated decisions and rationales."""
    pub_a1 = Publication(
        record_id=UUID("00000000-0000-0000-0000-000000000081"),
        title="Shared DOI Paper 1",
        identifiers=[Identifier(type=IdentifierType.DOI, value="10.1000/shared.doi")],
        provenance=[ProvenanceEntry(source="SourceA", source_record_id="SA1")],
        created_at=_TIME,
    )
    pub_a2 = Publication(
        record_id=UUID("00000000-0000-0000-0000-000000000082"),
        title="Shared DOI Paper 2",
        identifiers=[Identifier(type=IdentifierType.DOI, value="10.1000/shared.doi")],
        provenance=[ProvenanceEntry(source="SourceA", source_record_id="SA2")],
        created_at=_TIME,
    )

    proj_repo = DummyProjectRepository({
        "proj_a": [pub_a1, pub_a2],
        "proj_b": [pub_a1, pub_a2],
    })
    decision_repo = InMemoryDuplicateReviewDecisionRepository()
    service = ProjectDuplicateService(repository=proj_repo, decision_repository=decision_repo)

    groups_a = service.get_candidate_duplicate_groups("proj_a")
    groups_b = service.get_candidate_duplicate_groups("proj_b")
    group_id = groups_a.groups[0].group_id
    assert groups_b.groups[0].group_id == group_id

    # Record APPROVE for proj_a with rationale
    res_a = service.record_decision("proj_a", group_id, "APPROVE", "Rationale for Proj A")
    assert res_a.project_id == "proj_a"
    assert res_a.decision == DuplicateDecisionStatus.APPROVE
    assert res_a.rationale == "Rationale for Proj A"

    # Verify proj_a returns APPROVE while proj_b returns PENDING
    assert service.get_decision("proj_a", group_id).decision == DuplicateDecisionStatus.APPROVE
    assert service.get_decision("proj_b", group_id).decision == DuplicateDecisionStatus.PENDING

    # Record REJECT for proj_b with different rationale
    res_b = service.record_decision("proj_b", group_id, "REJECT", "Rationale for Proj B")
    assert res_b.project_id == "proj_b"
    assert res_b.decision == DuplicateDecisionStatus.REJECT
    assert res_b.rationale == "Rationale for Proj B"

    # Verify independence
    assert service.get_decision("proj_a", group_id).rationale == "Rationale for Proj A"
    assert service.get_decision("proj_b", group_id).rationale == "Rationale for Proj B"
