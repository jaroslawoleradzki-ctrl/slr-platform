"""Real-backend integration tests for v0.7.6 status/counter propagation."""

from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from app.domain.author import Author
from app.domain.project import Project
from app.domain.provenance import ProvenanceEntry
from app.domain.publication import Publication
from app.repositories.duplicate_merge_repository import SqliteDuplicateMergeRepository
from app.repositories.duplicate_review_decision_repository import (
    SqliteDuplicateReviewDecisionRepository,
)
from app.repositories.import_history_repository import SqliteImportHistoryRepository
from app.repositories.import_review_repository import SqliteImportReviewRepository
from app.repositories.import_source_record_repository import (
    SqliteImportSourceRecordRepository,
)
from app.repositories.normalization_execution_repository import (
    SqliteNormalizationExecutionRepository,
)
from app.repositories.project_publication_repository import (
    SqliteProjectPublicationRepository,
)
from app.repositories.project_repository import SqliteProjectRepository
from app.repositories.transaction_manager import SqliteTransactionManager
from app.services.import_review_service import ImportReviewService
from app.services.project_import_service import ProjectImportService
from app.services.sources_summary_service import SourcesSummaryService

PROJECT_ID = "v076-workflow-status"


def _publication(number: int = 1) -> Publication:
    return Publication(
        record_id=UUID(f"00000000-0000-0000-0000-{number:012d}"),
        title="Shared warning title for workflow status",
        authors=[Author(display_name="Author One")],
        publication_year=2024,
        provenance=[ProvenanceEntry(source="ris", source_record_id=f"ris-{number}")],
        created_at=datetime(2026, 10, 29, tzinfo=timezone.utc),
    )


def _build(tmp_path: Path):
    database = tmp_path / "v076-workflow-status.db"
    SqliteProjectRepository(database).create(Project(project_id=PROJECT_ID, title="Status"))
    publications = SqliteProjectPublicationRepository(database)
    history = SqliteImportHistoryRepository(database)
    sources = SqliteImportSourceRecordRepository(database)
    reviews = SqliteImportReviewRepository(database)
    transaction_manager = SqliteTransactionManager(database)
    import_service = ProjectImportService(
        publication_repository=publications,
        import_history_repository=history,
        normalization_repository=SqliteNormalizationExecutionRepository(database),
        transaction_manager=transaction_manager,
        source_record_repository=sources,
    )
    review_service = ImportReviewService(
        publication_repository=publications,
        import_history_repository=history,
        source_record_repository=sources,
        review_repository=reviews,
        duplicate_decision_repository=SqliteDuplicateReviewDecisionRepository(database),
        merge_repository=SqliteDuplicateMergeRepository(database),
        normalization_repository=SqliteNormalizationExecutionRepository(database),
        transaction_manager=transaction_manager,
    )
    summary_service = SourcesSummaryService(
        publication_repository=publications,
        import_history_repository=history,
        source_record_repository=sources,
        review_repository=reviews,
    )
    return import_service, review_service, summary_service, publications, sources


def _warning_import(import_service, publications):
    publication = _publication()
    import_service.import_bibliographic_publications(PROJECT_ID, "first.ris", "RIS", [publication])
    _, warning_history = import_service.import_bibliographic_publications(
        PROJECT_ID, "second.ris", "RIS", [publication]
    )
    assert warning_history.status == "warning"
    return warning_history


def test_accept_updates_warning_derived_counters_only(tmp_path: Path) -> None:
    import_service, review_service, summary_service, publications, sources = _build(tmp_path)
    warning_history = _warning_import(import_service, publications)

    before = summary_service.get_sources_summary(PROJECT_ID)
    before_source_records = len(sources.list_source_records(PROJECT_ID))
    before_ris = next(item for item in before.source_summaries if item.source == "ris")
    assert before_ris.warning_imports_count == 1
    assert before_ris.successful_imports_count == 1
    assert before_ris.records_added_count == 2

    review_service.accept(
        PROJECT_ID, warning_history.import_id, reviewer_id="alice", rationale="confirmed"
    )

    after = summary_service.get_sources_summary(PROJECT_ID)
    after_ris = next(item for item in after.source_summaries if item.source == "ris")
    assert after_ris.warning_imports_count == 0
    assert after_ris.successful_imports_count == 2
    assert after_ris.records_added_count == before_ris.records_added_count == 2
    assert after.working_collection.total_records == before.working_collection.total_records == 1
    assert publications.count_by_project(PROJECT_ID) == 1
    assert len(sources.list_source_records(PROJECT_ID)) == before_source_records


def test_reject_updates_warning_derived_counters_and_retains_audit(tmp_path: Path) -> None:
    import_service, review_service, summary_service, publications, sources = _build(tmp_path)
    warning_history = _warning_import(import_service, publications)

    before = summary_service.get_sources_summary(PROJECT_ID)
    before_source_records = len(sources.list_source_records(PROJECT_ID))
    review_service.reject(
        PROJECT_ID,
        warning_history.import_id,
        reviewer_id="alice",
        rationale="duplicate import",
        confirm_rejection=True,
    )

    after = summary_service.get_sources_summary(PROJECT_ID)
    after_ris = next(item for item in after.source_summaries if item.source == "ris")
    assert after_ris.warning_imports_count == 0
    assert after_ris.successful_imports_count == before.source_summaries[0].successful_imports_count
    assert after.working_collection.total_records == before.working_collection.total_records == 1
    assert publications.count_by_project(PROJECT_ID) == 1
    assert len(sources.list_source_records(PROJECT_ID)) == before_source_records
