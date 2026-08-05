from datetime import datetime, timezone
import sqlite3
from uuid import UUID, uuid4
import pytest

from app.api.dto.search_strategy import SearchResultRecordResponse
from app.domain.integrity_audit import IntegrityAuditStatus
from app.domain.provenance import ProvenanceEntry
from app.domain.publication import Publication
from app.repositories.import_history_repository import (
    ImportHistoryRecord,
    SqliteImportHistoryRepository,
)
from app.repositories.normalization_execution_repository import (
    NormalizationExecution,
    SqliteNormalizationExecutionRepository,
)
from app.repositories.project_publication_repository import SqliteProjectPublicationRepository
from app.repositories.transaction_manager import SqliteTransactionManager
from app.services.integrity_audit_service import ProjectIntegrityAuditService
from app.services.project_import_service import ProjectImportService

_TIME = datetime(2026, 8, 1, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def temp_db_path(tmp_path):
    return tmp_path / "test_transactions.db"


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
def audit_service(pub_repo, history_repo, norm_repo):
    return ProjectIntegrityAuditService(
        publication_repository=pub_repo,
        import_history_repository=history_repo,
        normalization_repository=norm_repo,
    )


def test_transaction_import_new_records_success(import_service, pub_repo, history_repo, audit_service):
    project_id = "lean_energy"
    record1 = SearchResultRecordResponse(
        id=str(UUID("00000000-0000-0000-0000-000000000001")),
        title="Pub 1",
        authors=["Author 1"],
        year=2021,
        provider="openalex",
        source_id="W1",
        doi="10.1000/1",
    )

    res = import_service.import_provider_results_group(
        project_id=project_id,
        provider_name="openalex",
        records_group=[record1],
        query="energy",
        group_total_available=100,
    )

    assert res.imported_count == 1
    assert res.working_collection_count == 1

    pubs = pub_repo.get_publications(project_id)
    assert len(pubs) == 1
    history = history_repo.list_for_project(project_id)
    assert len(history) == 1
    assert history[0].records_count == 1

    report = audit_service.audit_project(project_id)
    assert report.status is IntegrityAuditStatus.OK


def test_transaction_import_mixed_records(import_service, pub_repo, history_repo, audit_service):
    project_id = "lean_energy"
    pub1 = Publication(
        record_id=UUID("00000000-0000-0000-0000-000000000001"),
        title="Existing Pub",
        provenance=[ProvenanceEntry(source="openalex", source_record_id="W1")],
        created_at=_TIME,
    )
    pub_repo.add_publications(project_id, [pub1])
    history_repo.create(
        ImportHistoryRecord(
            import_id=uuid4(),
            project_id=project_id,
            source_type="provider",
            filename=None,
            format=None,
            provider="openalex",
            query="initial",
            records_count=1,
            total_available=1,
            status="success",
            warnings=(),
            created_at=_TIME,
        )
    )

    record_dup = SearchResultRecordResponse(
        id=str(UUID("00000000-0000-0000-0000-000000000001")),
        title="Existing Pub",
        authors=["Author 1"],
        year=2021,
        provider="openalex",
        source_id="W1",
        doi="10.1000/1",
    )
    record_new = SearchResultRecordResponse(
        id=str(UUID("00000000-0000-0000-0000-000000000002")),
        title="New Pub",
        authors=["Author 2"],
        year=2022,
        provider="openalex",
        source_id="W2",
        doi="10.1000/2",
    )

    res = import_service.import_provider_results_group(
        project_id=project_id,
        provider_name="openalex",
        records_group=[record_dup, record_new],
        query="energy",
        group_total_available=100,
    )

    assert res.imported_count == 1
    assert res.skipped_count == 1
    assert res.working_collection_count == 2

    history = history_repo.list_for_project(project_id)
    assert len(history) == 2
    assert history[0].records_count == 1

    report = audit_service.audit_project(project_id)
    assert report.status is IntegrityAuditStatus.OK


def test_transaction_import_duplicate_only(import_service, pub_repo, history_repo, audit_service):
    project_id = "lean_energy"
    pub1 = Publication(
        record_id=UUID("00000000-0000-0000-0000-000000000001"),
        title="Existing Pub",
        provenance=[ProvenanceEntry(source="ris", source_record_id="Title 1")],
        created_at=_TIME,
    )
    pub_repo.add_publications(project_id, [pub1])
    history_repo.create(
        ImportHistoryRecord(
            import_id=uuid4(),
            project_id=project_id,
            source_type="file",
            filename="initial.ris",
            format="RIS",
            provider=None,
            query=None,
            records_count=1,
            total_available=None,
            status="success",
            warnings=(),
            created_at=_TIME,
        )
    )

    res, history_rec = import_service.import_bibliographic_publications(
        project_id=project_id,
        filename="dup.ris",
        file_format="RIS",
        publications=[pub1],
    )

    assert res.imported_count == 0
    assert res.skipped_count == 1
    assert history_rec.records_count == 0
    assert history_rec.status == "warning"

    history = history_repo.list_for_project(project_id)
    assert len(history) == 2
    assert history[0].records_count == 0

    report = audit_service.audit_project(project_id)
    assert report.status is IntegrityAuditStatus.OK


def test_transaction_rollback_error_before_first_write(pub_repo, history_repo, norm_repo, tx_manager, audit_service):
    project_id = "lean_energy"
    pub1 = Publication(
        record_id=UUID("00000000-0000-0000-0000-000000000001"),
        title="Initial Pub",
        provenance=[ProvenanceEntry(source="openalex", source_record_id="W1")],
        created_at=_TIME,
    )
    pub_repo.add_publications(project_id, [pub1])
    initial_pubs = pub_repo.get_publications(project_id)

    norm_execution = NormalizationExecution(
        run_id=uuid4(),
        project_id=project_id,
        status="completed",
        processed_records=1,
        clean_records=1,
        warnings_count=0,
        errors_count=0,
        rules_applied=(),
        audit_trail=(),
        started_at=_TIME,
        completed_at=_TIME,
    )
    norm_repo.save(norm_execution)
    initial_norm = norm_repo.get_for_project(project_id)

    # Class with invalid implementation raising before first write
    class FailingPubRepoBeforeWrite:
        def import_source_publications(self, project_id, publications, *, connection=None):
            raise ValueError("Validation error before first write")

    failing_service = ProjectImportService(
        publication_repository=FailingPubRepoBeforeWrite(),
        import_history_repository=history_repo,
        normalization_repository=norm_repo,
        transaction_manager=tx_manager,
    )

    record = SearchResultRecordResponse(
        id=str(UUID("00000000-0000-0000-0000-000000000002")),
        title="New Pub",
        authors=["Author"],
        year=2021,
        provider="openalex",
        source_id="W2",
        doi=None,
    )

    with pytest.raises(ValueError, match="Validation error before first write"):
        failing_service.import_provider_results_group(
            project_id=project_id,
            provider_name="openalex",
            records_group=[record],
            query="test",
            group_total_available=10,
        )

    # Verify state remains 100% unchanged
    assert pub_repo.get_publications(project_id) == initial_pubs
    assert history_repo.list_for_project(project_id) == []
    assert norm_repo.get_for_project(project_id) == initial_norm


def test_transaction_rollback_error_after_pub_write_before_history(pub_repo, history_repo, norm_repo, tx_manager):
    project_id = "lean_energy"
    pub1 = Publication(
        record_id=UUID("00000000-0000-0000-0000-000000000001"),
        title="Initial Pub",
        provenance=[ProvenanceEntry(source="openalex", source_record_id="W1")],
        created_at=_TIME,
    )
    pub_repo.add_publications(project_id, [pub1])

    norm_execution = NormalizationExecution(
        run_id=uuid4(),
        project_id=project_id,
        status="completed",
        processed_records=1,
        clean_records=1,
        warnings_count=0,
        errors_count=0,
        rules_applied=(),
        audit_trail=(),
        started_at=_TIME,
        completed_at=_TIME,
    )
    norm_repo.save(norm_execution)

def test_transaction_rollback_error_during_history_insert(pub_repo, history_repo, norm_repo, tx_manager):
    project_id = "lean_energy"
    pub1 = Publication(
        record_id=UUID("00000000-0000-0000-0000-000000000001"),
        title="Initial Pub",
        provenance=[ProvenanceEntry(source="openalex", source_record_id="W1")],
        created_at=_TIME,
    )
    pub_repo.add_publications(project_id, [pub1])
    initial_pubs = pub_repo.get_publications(project_id)

    norm_execution = NormalizationExecution(
        run_id=uuid4(),
        project_id=project_id,
        status="completed",
        processed_records=1,
        clean_records=1,
        warnings_count=0,
        errors_count=0,
        rules_applied=(),
        audit_trail=(),
        started_at=_TIME,
        completed_at=_TIME,
    )
    norm_repo.save(norm_execution)
    initial_norm = norm_repo.get_for_project(project_id)

    # Repository that executes Working Collection insert, then fails during INSERT in create()
    class SqliteFailingHistoryRepo(SqliteImportHistoryRepository):
        def create(self, record, *, connection=None):
            if connection is not None:
                # Attempt statement to trigger real SQLite syntax/execution error during INSERT
                connection.execute("INSERT INTO import_history (invalid_column) VALUES (1)")
            return super().create(record, connection=connection)

    failing_service = ProjectImportService(
        publication_repository=pub_repo,
        import_history_repository=SqliteFailingHistoryRepo(history_repo._database_path),
        normalization_repository=norm_repo,
        transaction_manager=tx_manager,
    )

    record = SearchResultRecordResponse(
        id=str(UUID("00000000-0000-0000-0000-000000000002")),
        title="New Pub",
        authors=["Author"],
        year=2021,
        provider="openalex",
        source_id="W2",
        doi=None,
    )

    with pytest.raises(sqlite3.OperationalError, match="table import_history has no column named invalid_column"):
        failing_service.import_provider_results_group(
            project_id=project_id,
            provider_name="openalex",
            records_group=[record],
            query="test",
            group_total_available=10,
        )

    # Confirm Working Collection rollback, Import History clean, Normalization preserved
    assert pub_repo.get_publications(project_id) == initial_pubs
    assert history_repo.list_for_project(project_id) == []
    assert norm_repo.get_for_project(project_id) == initial_norm


def test_repository_connection_ownership_and_standalone_behavior(pub_repo, history_repo, norm_repo, temp_db_path):
    project_id = "lean_energy"
    pub1 = Publication(
        record_id=UUID("00000000-0000-0000-0000-000000000001"),
        title="Standalone Pub",
        provenance=[ProvenanceEntry(source="openalex", source_record_id="W1")],
        created_at=_TIME,
    )

    # 1. Standalone operation without connection parameter (repo manages its own transaction and connection)
    pub_repo.add_publications(project_id, [pub1])
    assert len(pub_repo.get_publications(project_id)) == 1

    # 2. Shared connection operation (repo MUST NOT commit, rollback, or close external connection)
    external_conn = sqlite3.connect(temp_db_path)
    try:
        external_conn.execute("BEGIN TRANSACTION;")
        pub2 = Publication(
            record_id=UUID("00000000-0000-0000-0000-000000000002"),
            title="Shared Conn Pub",
            provenance=[ProvenanceEntry(source="openalex", source_record_id="W2")],
            created_at=_TIME,
        )
        pub_repo.add_publications(project_id, [pub2], connection=external_conn)
        
        # Verify uncommitted state on external connection before commit
        pubs_in_tx = pub_repo.get_publications(project_id, connection=external_conn)
        assert len(pubs_in_tx) == 2

        # Rollback externally
        external_conn.rollback()

        # Verify rollback succeeded and repo did NOT commit externally
        pubs_after_rollback = pub_repo.get_publications(project_id)
        assert len(pubs_after_rollback) == 1
    finally:
        external_conn.close()


def test_transaction_rollback_error_after_history_insert_before_commit(pub_repo, history_repo, norm_repo, tx_manager):
    project_id = "lean_energy"
    pub1 = Publication(
        record_id=UUID("00000000-0000-0000-0000-000000000001"),
        title="Initial Pub",
        provenance=[ProvenanceEntry(source="openalex", source_record_id="W1")],
        created_at=_TIME,
    )
    pub_repo.add_publications(project_id, [pub1])
    initial_pubs = pub_repo.get_publications(project_id)

    norm_execution = NormalizationExecution(
        run_id=uuid4(),
        project_id=project_id,
        status="completed",
        processed_records=1,
        clean_records=1,
        warnings_count=0,
        errors_count=0,
        rules_applied=(),
        audit_trail=(),
        started_at=_TIME,
        completed_at=_TIME,
    )
    norm_repo.save(norm_execution)
    initial_norm = norm_repo.get_for_project(project_id)

    # Failing normalization repo raising after history insert
    class FailingNormRepoAfterHistory:
        def delete_for_project(self, project_id, *, connection=None):
            raise RuntimeError("Error after history insert before transaction commit")

    failing_service = ProjectImportService(
        publication_repository=pub_repo,
        import_history_repository=history_repo,
        normalization_repository=FailingNormRepoAfterHistory(),
        transaction_manager=tx_manager,
    )

    record = SearchResultRecordResponse(
        id=str(UUID("00000000-0000-0000-0000-000000000002")),
        title="New Pub",
        authors=["Author"],
        year=2021,
        provider="openalex",
        source_id="W2",
        doi=None,
    )

    with pytest.raises(RuntimeError, match="Error after history insert before transaction commit"):
        failing_service.import_provider_results_group(
            project_id=project_id,
            provider_name="openalex",
            records_group=[record],
            query="test",
            group_total_available=10,
        )

    # Verify complete rollback of both publications AND history insert AND normalization preservation
    assert pub_repo.get_publications(project_id) == initial_pubs
    assert history_repo.list_for_project(project_id) == []
    assert norm_repo.get_for_project(project_id) == initial_norm


def test_transaction_all_supported_import_paths(import_service, pub_repo, history_repo, norm_repo, audit_service):
    project_id = "lean_energy"

    # 1. OpenAlex provider results import
    rec_oa = SearchResultRecordResponse(
        id=str(UUID("00000000-0000-0000-0000-000000000001")),
        title="OpenAlex Pub",
        authors=["Author OA"],
        year=2021,
        provider="openalex",
        source_id="W100",
        doi="10.1000/oa",
    )
    import_service.import_provider_results_group(
        project_id=project_id,
        provider_name="openalex",
        records_group=[rec_oa],
        query="query",
        group_total_available=1,
    )

    # 2. Crossref provider results import
    rec_cr = SearchResultRecordResponse(
        id=str(UUID("00000000-0000-0000-0000-000000000002")),
        title="Crossref Pub",
        authors=["Author CR"],
        year=2022,
        provider="crossref",
        source_id="10.1000/cr",
        doi="10.1000/cr",
    )
    import_service.import_provider_results_group(
        project_id=project_id,
        provider_name="crossref",
        records_group=[rec_cr],
        query="query",
        group_total_available=1,
    )

    # 3. RIS file import
    pub_ris = Publication(
        record_id=UUID("00000000-0000-0000-0000-000000000003"),
        title="RIS Pub",
        provenance=[ProvenanceEntry(source="ris", source_record_id="RIS-100")],
        created_at=_TIME,
    )
    import_service.import_bibliographic_publications(
        project_id=project_id,
        filename="test.ris",
        file_format="RIS",
        publications=[pub_ris],
    )

    # 4. BibTeX file import
    pub_bib = Publication(
        record_id=UUID("00000000-0000-0000-0000-000000000004"),
        title="BibTeX Pub",
        provenance=[ProvenanceEntry(source="bibtex", source_record_id="BIB-100")],
        created_at=_TIME,
    )
    import_service.import_bibliographic_publications(
        project_id=project_id,
        filename="test.bib",
        file_format="BibTeX",
        publications=[pub_bib],
    )

    # Verify total state
    pubs = pub_repo.get_publications(project_id)
    assert len(pubs) == 4
    history = history_repo.list_for_project(project_id)
    assert len(history) == 4

    report = audit_service.audit_project(project_id)
    assert report.status is IntegrityAuditStatus.OK

