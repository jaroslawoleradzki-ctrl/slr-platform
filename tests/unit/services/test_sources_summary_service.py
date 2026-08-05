from datetime import datetime, timezone
from uuid import UUID, uuid4
import pytest

from app.api.dto.search_strategy import SearchResultRecordResponse
from app.domain.provenance import ProvenanceEntry
from app.domain.publication import Publication
from app.repositories.import_history_repository import (
    ImportHistoryRecord,
    SqliteImportHistoryRepository,
)
from app.repositories.normalization_execution_repository import (
    SqliteNormalizationExecutionRepository,
)
from app.repositories.project_publication_repository import (
    ProjectNotFoundError,
    SqliteProjectPublicationRepository,
)
from app.repositories.transaction_manager import SqliteTransactionManager
from app.services.integrity_audit_service import ProjectIntegrityAuditService
from app.services.project_import_service import ProjectImportService
from app.services.sources_summary_service import SourcesSummaryService

_TIME = datetime(2026, 8, 5, 10, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def temp_db_path(tmp_path):
    return tmp_path / "test_sources_summary.db"


@pytest.fixture
def pub_repo(temp_db_path):
    return SqliteProjectPublicationRepository(temp_db_path)


@pytest.fixture
def history_repo(temp_db_path):
    return SqliteImportHistoryRepository(temp_db_path)


@pytest.fixture
def norm_repo(temp_db_path):
    return SqliteNormalizationExecutionRepository(temp_db_path)


@pytest.fixture
def tx_manager(temp_db_path):
    return SqliteTransactionManager(temp_db_path)


@pytest.fixture
def import_service(pub_repo, history_repo, norm_repo, tx_manager):
    return ProjectImportService(
        publication_repository=pub_repo,
        import_history_repository=history_repo,
        normalization_repository=norm_repo,
        transaction_manager=tx_manager,
    )


@pytest.fixture
def summary_service(pub_repo, history_repo):
    return SourcesSummaryService(
        publication_repository=pub_repo,
        import_history_repository=history_repo,
    )


@pytest.fixture
def audit_service(pub_repo, history_repo, norm_repo):
    return ProjectIntegrityAuditService(
        publication_repository=pub_repo,
        import_history_repository=history_repo,
        normalization_execution_repository=norm_repo,
    )


def test_sources_summary_empty_project(pub_repo, summary_service):
    # Verify raises ProjectNotFoundError for non-existent project
    with pytest.raises(ProjectNotFoundError):
        summary_service.get_sources_summary("non_existent")

    # Add 0 publications but ensure project registered
    pub_repo.add_publications("lean_energy", [])
    res = summary_service.get_sources_summary("lean_energy")
    assert res.project_id == "lean_energy"
    assert res.working_collection.total_records == 0
    assert res.source_summaries == []
    assert res.import_history == []


def test_sources_summary_single_successful_import(import_service, summary_service):
    project_id = "lean_energy"
    rec = SearchResultRecordResponse(
        id=str(uuid4()),
        title="Pub 1",
        authors=["Author"],
        year=2021,
        provider="openalex",
        source_id="W1",
        doi="10.1000/1",
    )
    import_service.import_provider_results_group(
        project_id=project_id,
        provider_name="openalex",
        records_group=[rec],
        query="energy",
        group_total_available=10,
    )

    res = summary_service.get_sources_summary(project_id)
    assert res.working_collection.total_records == 1
    assert len(res.source_summaries) == 1
    s = res.source_summaries[0]
    assert s.source == "openalex"
    assert s.source_kind == "provider"
    assert s.successful_imports_count == 1
    assert s.warning_imports_count == 0
    assert s.failed_imports_count == 0
    assert s.records_added_count == 1
    assert s.last_import_status == "success"
    assert len(res.import_history) == 1


def test_sources_summary_multiple_imports_same_source(import_service, summary_service):
    project_id = "lean_energy"
    rec1 = SearchResultRecordResponse(
        id=str(uuid4()), title="Pub 1", authors=[], year=2021, provider="openalex", source_id="W1"
    )
    import_service.import_provider_results_group(
        project_id=project_id, provider_name="openalex", records_group=[rec1], query="q1", group_total_available=1
    )

    rec2 = SearchResultRecordResponse(
        id=str(uuid4()), title="Pub 2", authors=[], year=2022, provider="openalex", source_id="W2"
    )
    import_service.import_provider_results_group(
        project_id=project_id, provider_name="openalex", records_group=[rec2], query="q2", group_total_available=1
    )

    res = summary_service.get_sources_summary(project_id)
    assert res.working_collection.total_records == 2
    assert len(res.source_summaries) == 1
    s = res.source_summaries[0]
    assert s.source == "openalex"
    assert s.successful_imports_count == 2
    assert s.records_added_count == 2
    assert len(res.import_history) == 2


def test_sources_summary_mixed_import_and_duplicate_reimport(import_service, summary_service):
    project_id = "lean_energy"
    rec1 = SearchResultRecordResponse(
        id=str(uuid4()), title="Pub 1", authors=[], year=2021, provider="openalex", source_id="W1"
    )
    rec2 = SearchResultRecordResponse(
        id=str(uuid4()), title="Pub 2", authors=[], year=2022, provider="openalex", source_id="W2"
    )

    # 1. Initial import of Pub 1
    import_service.import_provider_results_group(
        project_id=project_id, provider_name="openalex", records_group=[rec1], query="q", group_total_available=2
    )

    # 2. Mixed import of Pub 1 (duplicate) + Pub 2 (new)
    import_service.import_provider_results_group(
        project_id=project_id, provider_name="openalex", records_group=[rec1, rec2], query="q", group_total_available=2
    )

    # 3. Duplicate-only re-import of Pub 1 & Pub 2
    import_service.import_provider_results_group(
        project_id=project_id, provider_name="openalex", records_group=[rec1, rec2], query="q", group_total_available=2
    )

    res = summary_service.get_sources_summary(project_id)
    assert res.working_collection.total_records == 2
    assert len(res.source_summaries) == 1
    s = res.source_summaries[0]
    assert s.successful_imports_count == 3  # All completed imports have status="success" in import_service
    assert s.records_added_count == 2  # 1 from first + 1 from second + 0 from third
    assert s.last_import_status == "success"
    assert len(res.import_history) == 3


def test_sources_summary_openalex_crossref_ris_bibtex(import_service, summary_service):
    project_id = "lean_energy"

    # OpenAlex
    import_service.import_provider_results_group(
        project_id=project_id,
        provider_name="openalex",
        records_group=[SearchResultRecordResponse(id=str(uuid4()), title="OA", authors=[], year=2021, provider="openalex", source_id="W1")],
        query="q",
        group_total_available=1,
    )
    # Crossref
    import_service.import_provider_results_group(
        project_id=project_id,
        provider_name="crossref",
        records_group=[SearchResultRecordResponse(id=str(uuid4()), title="CR", authors=[], year=2021, provider="crossref", source_id="10.1000/cr")],
        query="q",
        group_total_available=1,
    )
    # RIS
    import_service.import_bibliographic_publications(
        project_id=project_id,
        filename="ref.ris",
        file_format="RIS",
        publications=[Publication(record_id=uuid4(), title="RIS", provenance=[ProvenanceEntry(source="ris", source_record_id="R1")], created_at=_TIME)],
    )
    # BibTeX
    import_service.import_bibliographic_publications(
        project_id=project_id,
        filename="ref.bib",
        file_format="BibTeX",
        publications=[Publication(record_id=uuid4(), title="BIB", provenance=[ProvenanceEntry(source="bibtex", source_record_id="B1")], created_at=_TIME)],
    )

    res = summary_service.get_sources_summary(project_id)
    assert res.working_collection.total_records == 4
    # Check deterministic sorting: file sources first ('bibtex', 'ris'), then provider sources ('crossref', 'openalex')
    expected_sources = [("file", "bibtex"), ("file", "ris"), ("provider", "crossref"), ("provider", "openalex")]
    actual_sources = [(s.source_kind, s.source) for s in res.source_summaries]
    assert actual_sources == expected_sources


def test_sources_summary_deterministic_tie_breaker(history_repo, pub_repo, summary_service):
    project_id = "lean_energy"
    pub_repo.add_publications(project_id, [])

    # Two records with exact same created_at timestamp but different UUIDs
    uuid_a = UUID("00000000-0000-0000-0000-000000000001")
    uuid_b = UUID("00000000-0000-0000-0000-000000000002")

    rec_a = ImportHistoryRecord(
        import_id=uuid_a, project_id=project_id, source_type="file", filename="a.ris", format="RIS", provider=None,
        query=None, records_count=1, total_available=1, status="success", warnings=(), created_at=_TIME
    )
    rec_b = ImportHistoryRecord(
        import_id=uuid_b, project_id=project_id, source_type="file", filename="b.ris", format="RIS", provider=None,
        query=None, records_count=1, total_available=1, status="success", warnings=(), created_at=_TIME
    )
    history_repo.create(rec_a)
    history_repo.create(rec_b)

    res = summary_service.get_sources_summary(project_id)
    history_ids = [item.import_id for item in res.import_history]
    # Tie-breaker (created_at DESC, import_id DESC) places uuid_b before uuid_a
    assert history_ids == [uuid_b, uuid_a]


def test_sources_summary_http_endpoint(pub_repo, history_repo):
    from fastapi.testclient import TestClient
    from app.api.main import app
    from app.api.routers.search_strategy import get_project_publication_repository, get_import_history_repository

    project_id = "lean_energy"
    pub_repo.add_publications(project_id, [
        Publication(record_id=UUID("00000000-0000-0000-0000-000000000001"), title="HTTP Pub", provenance=[ProvenanceEntry(source="openalex", source_record_id="W1")], created_at=_TIME)
    ])
    history_repo.create(
        ImportHistoryRecord(
            import_id=UUID("00000000-0000-0000-0000-000000000001"),
            project_id=project_id,
            source_type="provider",
            filename=None,
            format=None,
            provider="openalex",
            query="energy",
            records_count=1,
            total_available=10,
            status="success",
            warnings=("Warn 1",),
            created_at=_TIME,
        )
    )

    app.dependency_overrides[get_project_publication_repository] = lambda: pub_repo
    app.dependency_overrides[get_import_history_repository] = lambda: history_repo
    client = TestClient(app)

    try:
        response = client.get(f"/projects/{project_id}/sources-summary")
        assert response.status_code == 200
        data = response.json()

        assert data["project_id"] == project_id
        assert data["working_collection"]["total_records"] == 1

        # Check source_summaries serialization
        assert len(data["source_summaries"]) == 1
        s = data["source_summaries"][0]
        assert s["source"] == "openalex"
        assert s["source_kind"] == "provider"
        assert s["successful_imports_count"] == 1
        assert s["records_added_count"] == 1

        # Check import_history serialization
        assert len(data["import_history"]) == 1
        h = data["import_history"][0]
        assert h["import_id"] == "00000000-0000-0000-0000-000000000001"
        assert h["source_type"] == "provider"
        assert h["provider"] == "openalex"
        assert h["records_count"] == 1
        assert h["status"] == "success"
        assert h["warnings"] == ["Warn 1"]
        assert "2026-08-05T10:00:00" in h["created_at"]

        # Test empty/not found project HTTP 404
        response_404 = client.get("/projects/non_existent/sources-summary")
        assert response_404.status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_sources_summary_http_endpoint_empty_project(pub_repo, history_repo):
    from fastapi.testclient import TestClient
    from app.api.main import app
    from app.api.routers.search_strategy import get_project_publication_repository, get_import_history_repository

    project_id = "lean_energy"
    # Ensure project exists in repository with 0 publications
    pub_repo.add_publications(project_id, [])

    app.dependency_overrides[get_project_publication_repository] = lambda: pub_repo
    app.dependency_overrides[get_import_history_repository] = lambda: history_repo
    client = TestClient(app)

    try:
        response = client.get(f"/projects/{project_id}/sources-summary")
        assert response.status_code == 200
        data = response.json()

        assert data["project_id"] == project_id
        assert data["working_collection"]["total_records"] == 0
        assert data["source_summaries"] == []
        assert data["import_history"] == []
    finally:
        app.dependency_overrides.clear()


def test_sources_summary_status_breakdown(history_repo, pub_repo, summary_service):
    project_id = "lean_energy"
    pub_repo.add_publications(project_id, [])

    # Manually insert history records with different statuses
    rec1 = ImportHistoryRecord(
        import_id=uuid4(), project_id=project_id, source_type="provider", filename=None, format=None, provider="openalex",
        query="q", records_count=5, total_available=10, status="success", warnings=(), created_at=_TIME
    )
    rec2 = ImportHistoryRecord(
        import_id=uuid4(), project_id=project_id, source_type="provider", filename=None, format=None, provider="openalex",
        query="q", records_count=2, total_available=10, status="warning", warnings=("Dup skipped",), created_at=_TIME
    )
    rec3 = ImportHistoryRecord(
        import_id=uuid4(), project_id=project_id, source_type="provider", filename=None, format=None, provider="openalex",
        query="q", records_count=0, total_available=10, status="failed", warnings=("Connection error",), created_at=_TIME
    )
    history_repo.create(rec1)
    history_repo.create(rec2)
    history_repo.create(rec3)

    res = summary_service.get_sources_summary(project_id)
    s = res.source_summaries[0]
    assert s.successful_imports_count == 1
    assert s.warning_imports_count == 1
    assert s.failed_imports_count == 1
    assert s.records_added_count == 7  # 5 + 2


def test_sources_summary_independent_working_collection_truth(pub_repo, history_repo, summary_service):
    project_id = "lean_energy"
    # Working Collection has 10 publications
    pubs = [
        Publication(record_id=uuid4(), title=f"P{i}", provenance=[ProvenanceEntry(source="test", source_record_id=str(i))], created_at=_TIME)
        for i in range(10)
    ]
    pub_repo.add_publications(project_id, pubs)

    # History only records 3 records added
    history_repo.create(
        ImportHistoryRecord(
            import_id=uuid4(), project_id=project_id, source_type="file", filename="a.ris", format="RIS", provider=None, query=None,
            records_count=3, total_available=3, status="success", warnings=(), created_at=_TIME
        )
    )

    res = summary_service.get_sources_summary(project_id)
    # Verify working collection total_records is truth from publication repo (10), not history sum (3)
    assert res.working_collection.total_records == 10
    assert res.source_summaries[0].records_added_count == 3
