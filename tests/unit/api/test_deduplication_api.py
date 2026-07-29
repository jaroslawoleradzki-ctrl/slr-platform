from copy import deepcopy
from datetime import datetime, timezone
from uuid import UUID

from fastapi.testclient import TestClient

from app.api.main import app
from app.domain.author import Author
from app.domain.identifiers import Identifier, IdentifierType
from app.domain.provenance import ProvenanceEntry
from app.domain.publication import Publication
from app.services.project_duplicate_service import ProjectDuplicateService

client = TestClient(app)
_TIME = datetime(2026, 7, 1, 10, 0, tzinfo=timezone.utc)


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


def test_get_duplicate_groups_lean_energy_endpoint_returns_200() -> None:
    response = client.get("/projects/lean_energy/duplicate-groups")
    assert response.status_code == 200

    data = response.json()
    assert data["project_id"] == "lean_energy"
    assert data["total_groups_count"] == 2
    assert "similarity_score" not in data["groups"][0]

    shared_idents = data["groups"][0]["shared_identifiers"]
    assert isinstance(shared_idents, list)
    assert "identifier_type" in shared_idents[0]
    assert "value" in shared_idents[0]


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
