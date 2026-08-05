from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest

from app.domain.duplicate_review import DuplicateDecision, DuplicateGroupReviewDecision
from app.domain.integrity_audit import IntegrityAuditStatus, IntegrityCheckLevel
from app.domain.provenance import ProvenanceEntry
from app.domain.publication import Publication
from app.repositories.duplicate_review_decision_repository import (
    SqliteDuplicateReviewDecisionRepository,
)
from app.repositories.import_history_repository import (
    ImportHistoryRecord,
    SqliteImportHistoryRepository,
)
from app.repositories.normalization_execution_repository import (
    SqliteNormalizationExecutionRepository,
)
from app.repositories.project_publication_repository import (
    SqliteProjectPublicationRepository,
)
from app.services.integrity_audit_service import ProjectIntegrityAuditService
from app.services.normalization_service import NormalizationExecution

_TIME = datetime(2026, 8, 1, 12, 0, tzinfo=timezone.utc)


class InMemoryPublicationRepository:
    def __init__(self, data: dict[str, list[Publication]]) -> None:
        self._data = data

    def get_publications(self, project_id: str) -> list[Publication]:
        if project_id not in self._data:
            from app.repositories.project_publication_repository import ProjectNotFoundError

            raise ProjectNotFoundError(project_id)
        return self._data[project_id]

    def add_publications(self, project_id: str, publications: list[Publication]) -> int:
        self._data.setdefault(project_id, []).extend(publications)
        return len(self._data[project_id])

    def import_source_publications(self, project_id: str, publications: list[Publication]):
        pass

    def replace_publications(self, project_id: str, publications: list[Publication]) -> None:
        self._data[project_id] = list(publications)


@pytest.fixture
def temp_db_path(tmp_path):
    return tmp_path / "test_integrity.db"


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
def decision_repo(temp_db_path):
    return SqliteDuplicateReviewDecisionRepository(temp_db_path)


def test_integrity_audit_healthy_project(pub_repo, history_repo, norm_repo, decision_repo):
    project_id = "lean_energy"
    pub1 = Publication(
        record_id=UUID("00000000-0000-0000-0000-000000000001"),
        title="Test Pub 1",
        provenance=[ProvenanceEntry(source="OpenAlex", source_record_id="W1")],
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
            query="test",
            records_count=1,
            total_available=1,
            status="success",
            warnings=(),
            created_at=_TIME,
        )
    )

    norm_repo.save(
        NormalizationExecution(
            run_id=uuid4(),
            project_id=project_id,
            status="completed",
            processed_records=1,
            clean_records=1,
            warnings_count=0,
            errors_count=0,
            rules_applied=("DOI normalized",),
            audit_trail=("DOI normalized: 0",),
            started_at=_TIME,
            completed_at=_TIME,
        )
    )

    service = ProjectIntegrityAuditService(
        publication_repository=pub_repo,
        import_history_repository=history_repo,
        normalization_repository=norm_repo,
        decision_repository=decision_repo,
    )

    report = service.audit_project(project_id)
    assert report.project_id == project_id
    assert report.status is IntegrityAuditStatus.OK
    assert report.is_ok


def test_integrity_audit_import_history_statuses(pub_repo, history_repo, norm_repo, decision_repo):
    project_id = "lean_energy"
    pub1 = Publication(
        record_id=UUID("00000000-0000-0000-0000-000000000001"),
        title="Test Pub 1",
        provenance=[ProvenanceEntry(source="OpenAlex", source_record_id="W1")],
        created_at=_TIME,
    )
    pub2 = Publication(
        record_id=UUID("00000000-0000-0000-0000-000000000002"),
        title="Test Pub 2",
        provenance=[ProvenanceEntry(source="Crossref", source_record_id="W2")],
        created_at=_TIME,
    )
    pub_repo.add_publications(project_id, [pub1, pub2])

    # 1. Success import (+1)
    history_repo.create(
        ImportHistoryRecord(
            import_id=uuid4(),
            project_id=project_id,
            source_type="provider",
            filename=None,
            format=None,
            provider="openalex",
            query="test",
            records_count=1,
            total_available=1,
            status="success",
            warnings=(),
            created_at=_TIME,
        )
    )
    # 2. Warning import with duplicate skip (+1 imported, +1 skipped warning)
    history_repo.create(
        ImportHistoryRecord(
            import_id=uuid4(),
            project_id=project_id,
            source_type="file",
            filename="import.ris",
            format="RIS",
            provider=None,
            query=None,
            records_count=1,
            total_available=None,
            status="warning",
            warnings=("Skipped 1 duplicate record(s) already in the project.",),
            created_at=_TIME,
        )
    )
    # 3. Import with 0 imported records (all duplicates) (+0)
    history_repo.create(
        ImportHistoryRecord(
            import_id=uuid4(),
            project_id=project_id,
            source_type="file",
            filename="dup.ris",
            format="RIS",
            provider=None,
            query=None,
            records_count=0,
            total_available=None,
            status="warning",
            warnings=("Skipped 5 duplicate record(s) already in the project.",),
            created_at=_TIME,
        )
    )
    # 4. Failed import record (records_count = 0)
    history_repo.create(
        ImportHistoryRecord(
            import_id=uuid4(),
            project_id=project_id,
            source_type="file",
            filename="corrupt.ris",
            format="RIS",
            provider=None,
            query=None,
            records_count=0,
            total_available=None,
            status="failed",
            warnings=("Parsing failed",),
            created_at=_TIME,
        )
    )

    norm_repo.save(
        NormalizationExecution(
            run_id=uuid4(),
            project_id=project_id,
            status="completed",
            processed_records=2,
            clean_records=2,
            warnings_count=0,
            errors_count=0,
            rules_applied=(),
            audit_trail=(),
            started_at=_TIME,
            completed_at=_TIME,
        )
    )

    service = ProjectIntegrityAuditService(
        publication_repository=pub_repo,
        import_history_repository=history_repo,
        normalization_repository=norm_repo,
        decision_repository=decision_repo,
    )

    report = service.audit_project(project_id)
    # Should be OK because sum of success + warning records_count is 1 + 1 + 0 = 2, matching WC size 2
    assert report.status is IntegrityAuditStatus.OK
    assert not any(c.code == "IH_RECORD_COUNT_MISMATCH" for c in report.checks)


def test_integrity_audit_missing_unexecuted_stages_is_ok(pub_repo, history_repo, norm_repo, decision_repo):
    project_id = "ai_architecture"
    service = ProjectIntegrityAuditService(
        publication_repository=pub_repo,
        import_history_repository=history_repo,
        normalization_repository=norm_repo,
        decision_repository=decision_repo,
    )

    report = service.audit_project(project_id)
    assert report.status is IntegrityAuditStatus.OK
    codes = [c.code for c in report.checks]
    assert "NORM_NOT_EXECUTED" in codes
    assert "IH_NO_HISTORY" in codes
    assert "WC_EMPTY" in codes


def test_integrity_audit_detects_missing_provenance_error(pub_repo, history_repo, norm_repo, decision_repo):
    project_id = "lean_energy"
    pub_no_prov = Publication(
        record_id=UUID("00000000-0000-0000-0000-000000000002"),
        title="Pub Without Provenance",
        provenance=[],
        created_at=_TIME,
    )
    pub_repo.add_publications(project_id, [pub_no_prov])

    service = ProjectIntegrityAuditService(
        publication_repository=pub_repo,
        import_history_repository=history_repo,
        normalization_repository=norm_repo,
        decision_repository=decision_repo,
    )

    report = service.audit_project(project_id)
    assert report.status is IntegrityAuditStatus.ERROR
    prov_check = next(c for c in report.checks if c.code == "WC_PROVENANCE_MISSING")
    assert prov_check.level is IntegrityCheckLevel.ERROR
    assert prov_check.context["missing_count"] == 1


def test_integrity_audit_detects_incomplete_provenance_error(history_repo, norm_repo, decision_repo):
    project_id = "lean_energy"
    pub_inc_prov = Publication.model_construct(
        record_id=UUID("00000000-0000-0000-0000-000000000003"),
        title="Incomplete Provenance Pub",
        provenance=[ProvenanceEntry.model_construct(source="OpenAlex", source_record_id="")],
        created_at=_TIME,
    )
    mock_pub_repo = InMemoryPublicationRepository({project_id: [pub_inc_prov]})

    service = ProjectIntegrityAuditService(
        publication_repository=mock_pub_repo,
        import_history_repository=history_repo,
        normalization_repository=norm_repo,
        decision_repository=decision_repo,
    )

    report = service.audit_project(project_id)
    assert report.status is IntegrityAuditStatus.ERROR
    check = next(c for c in report.checks if c.code == "WC_PROVENANCE_INCOMPLETE")
    assert check.level is IntegrityCheckLevel.ERROR


def test_integrity_audit_detects_duplicate_record_id_error(history_repo, norm_repo, decision_repo):
    project_id = "lean_energy"
    rec_id = UUID("00000000-0000-0000-0000-000000000005")
    pub1 = Publication(
        record_id=rec_id,
        title="Pub 1",
        provenance=[ProvenanceEntry(source="OpenAlex", source_record_id="W1")],
        created_at=_TIME,
    )
    pub2 = Publication(
        record_id=rec_id,
        title="Pub 2 Duplicate ID",
        provenance=[ProvenanceEntry(source="Crossref", source_record_id="W2")],
        created_at=_TIME,
    )
    mock_pub_repo = InMemoryPublicationRepository({project_id: [pub1, pub2]})

    service = ProjectIntegrityAuditService(
        publication_repository=mock_pub_repo,
        import_history_repository=history_repo,
        normalization_repository=norm_repo,
        decision_repository=decision_repo,
    )

    report = service.audit_project(project_id)
    assert report.status is IntegrityAuditStatus.ERROR
    check = next(c for c in report.checks if c.code == "WC_DUPLICATE_RECORD_ID")
    assert check.level is IntegrityCheckLevel.ERROR


def test_integrity_audit_detects_orphaned_dedup_decision_warning(pub_repo, history_repo, norm_repo, decision_repo):
    project_id = "lean_energy"
    pub1 = Publication(
        record_id=UUID("00000000-0000-0000-0000-000000000001"),
        title="Test Pub 1",
        provenance=[ProvenanceEntry(source="OpenAlex", source_record_id="W1")],
        created_at=_TIME,
    )
    pub_repo.add_publications(project_id, [pub1])

    # Save a decision for a group_id that doesn't exist in candidate groups
    orphaned_group_id = "00000000-0000-0000-0000-999999999999"
    decision_repo.save_decision(
        project_id,
        orphaned_group_id,
        DuplicateGroupReviewDecision(decision=DuplicateDecision.APPROVE),
    )

    service = ProjectIntegrityAuditService(
        publication_repository=pub_repo,
        import_history_repository=history_repo,
        normalization_repository=norm_repo,
        decision_repository=decision_repo,
    )

    report = service.audit_project(project_id)
    assert report.status is IntegrityAuditStatus.WARNING
    check = next(c for c in report.checks if c.code == "DEDUP_DECISION_ORPHANED")
    assert check.level is IntegrityCheckLevel.WARNING
    assert orphaned_group_id in check.context["orphaned_group_ids"]


def test_integrity_audit_is_read_only(pub_repo, history_repo, norm_repo, decision_repo):
    project_id = "lean_energy"
    pub1 = Publication(
        record_id=UUID("00000000-0000-0000-0000-000000000001"),
        title="Test Pub 1",
        provenance=[ProvenanceEntry(source="OpenAlex", source_record_id="W1")],
        created_at=_TIME,
    )
    pub_repo.add_publications(project_id, [pub1])

    # Record state before
    pubs_before = pub_repo.get_publications(project_id)
    history_before = history_repo.list_for_project(project_id)
    norm_before = norm_repo.get_for_project(project_id)
    decisions_before = decision_repo.list_decisions_for_project(project_id)

    service = ProjectIntegrityAuditService(
        publication_repository=pub_repo,
        import_history_repository=history_repo,
        normalization_repository=norm_repo,
        decision_repository=decision_repo,
    )

    # Run audit
    _ = service.audit_project(project_id)

    # Record state after
    assert pub_repo.get_publications(project_id) == pubs_before
    assert history_repo.list_for_project(project_id) == history_before
    assert norm_repo.get_for_project(project_id) == norm_before
    assert decision_repo.list_decisions_for_project(project_id) == decisions_before


def test_integrity_audit_consecutive_runs_are_identical(pub_repo, history_repo, norm_repo, decision_repo):
    project_id = "lean_energy"
    pub1 = Publication(
        record_id=UUID("00000000-0000-0000-0000-000000000001"),
        title="Test Pub 1",
        provenance=[ProvenanceEntry(source="OpenAlex", source_record_id="W1")],
        created_at=_TIME,
    )
    pub_repo.add_publications(project_id, [pub1])

    service = ProjectIntegrityAuditService(
        publication_repository=pub_repo,
        import_history_repository=history_repo,
        normalization_repository=norm_repo,
        decision_repository=decision_repo,
    )

    report_run1 = service.audit_project(project_id)
    report_run2 = service.audit_project(project_id)

    assert report_run1 == report_run2
