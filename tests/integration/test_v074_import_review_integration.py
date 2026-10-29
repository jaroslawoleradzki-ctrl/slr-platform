from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

from app.domain.author import Author
from app.domain.project import Project
from app.domain.provenance import ProvenanceEntry
from app.domain.publication import Publication
from app.repositories.duplicate_merge_repository import SqliteDuplicateMergeRepository
from app.repositories.duplicate_review_decision_repository import SqliteDuplicateReviewDecisionRepository
from app.repositories.import_history_repository import SqliteImportHistoryRepository
from app.repositories.import_review_repository import SqliteImportReviewRepository
from app.repositories.import_source_record_repository import SqliteImportSourceRecordRepository
from app.repositories.normalization_execution_repository import SqliteNormalizationExecutionRepository
from app.repositories.project_publication_repository import SqliteProjectPublicationRepository
from app.repositories.project_repository import SqliteProjectRepository
from app.repositories.transaction_manager import SqliteTransactionManager
from app.services.import_review_service import ImportReviewService
from app.services.prisma_metrics_service import PrismaMetricsService
from app.services.project_import_service import ProjectImportService
from app.services.sources_summary_service import SourcesSummaryService

PROJECT_ID = "v074-import-review"


class _Stage:
    evaluated_count = 0
    eligible_count = 0


class _Workflow:
    def get_input_set(self, project_id):
        return None

    def get_status(self, project_id, reviewer_id="default_reviewer", *, input_set=None):
        return SimpleNamespace(
            title_abstract_screening=_Stage(),
            full_text_screening=_Stage(),
            quality_assessment=_Stage(),
        )

    def get_excluded_counts(self, project_id, reviewer_id="default_reviewer", *, input_set=None):
        return 0, 0


def _publication(number: int, author: str) -> Publication:
    return Publication(
        record_id=UUID(f"00000000-0000-0000-0000-{number:012d}"),
        title="Shared warning title for import review",
        authors=[Author(display_name=author)],
        publication_year=2024 + number,
        provenance=[ProvenanceEntry(source="ris", source_record_id=f"ris-{number}")],
        created_at=datetime(2026, 10, 27, tzinfo=timezone.utc),
    )


def test_warning_import_rejection_retains_audit_and_updates_prisma(tmp_path: Path) -> None:
    database = tmp_path / "v074-import-review.db"
    SqliteProjectRepository(database).create(Project(project_id=PROJECT_ID, title="Review"))
    publications = SqliteProjectPublicationRepository(database)
    history = SqliteImportHistoryRepository(database)
    sources = SqliteImportSourceRecordRepository(database)
    reviews = SqliteImportReviewRepository(database)
    decisions = SqliteDuplicateReviewDecisionRepository(database)
    merges = SqliteDuplicateMergeRepository(database)
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
        duplicate_decision_repository=decisions,
        merge_repository=merges,
        normalization_repository=SqliteNormalizationExecutionRepository(database),
        transaction_manager=transaction_manager,
    )

    first = _publication(1, "Author One")
    second = _publication(2, "Author Two")
    import_service.import_bibliographic_publications(PROJECT_ID, "first.ris", "RIS", [first])
    _, warning_history = import_service.import_bibliographic_publications(
        PROJECT_ID, "second.ris", "RIS", [second]
    )

    assert warning_history.status == "warning"
    review = review_service.get_review(PROJECT_ID, warning_history.import_id)
    assert review.can_reject is True
    review_service.reject(
        PROJECT_ID,
        warning_history.import_id,
        reviewer_id="alice",
        rationale="Imported by mistake.",
        confirm_rejection=True,
    )

    remaining = publications.get_publications(PROJECT_ID)
    assert [publication.record_id for publication in remaining] == [first.record_id]
    assert history.get(PROJECT_ID, warning_history.import_id) is not None
    assert len(sources.list_source_records_for_import(PROJECT_ID, warning_history.import_id)) == 1

    metrics = PrismaMetricsService(
        publication_repository=publications,
        import_history_repository=history,
        decision_repository=decisions,
        workflow_status_service=_Workflow(),
        source_record_repository=sources,
        merge_repository=merges,
        review_repository=reviews,
    ).get_metrics(PROJECT_ID)
    assert metrics.total_identified == 2
    assert metrics.records_removed_rejected_import == 1
    assert metrics.records_removed_prescreening == 1
    assert metrics.records_after_normalization == 1
    assert metrics.canonical_publications == 1


def test_warning_import_acceptance_updates_sources_without_changing_prisma(tmp_path: Path) -> None:
    database = tmp_path / "v074-import-accept.db"
    SqliteProjectRepository(database).create(Project(project_id=PROJECT_ID, title="Review"))
    publications = SqliteProjectPublicationRepository(database)
    history = SqliteImportHistoryRepository(database)
    sources = SqliteImportSourceRecordRepository(database)
    reviews = SqliteImportReviewRepository(database)
    decisions = SqliteDuplicateReviewDecisionRepository(database)
    merges = SqliteDuplicateMergeRepository(database)
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
        duplicate_decision_repository=decisions,
        merge_repository=merges,
        normalization_repository=SqliteNormalizationExecutionRepository(database),
        transaction_manager=transaction_manager,
    )
    summary_service = SourcesSummaryService(
        publication_repository=publications,
        import_history_repository=history,
        source_record_repository=sources,
        review_repository=reviews,
    )
    metrics_service = PrismaMetricsService(
        publication_repository=publications,
        import_history_repository=history,
        decision_repository=decisions,
        workflow_status_service=_Workflow(),
        source_record_repository=sources,
        merge_repository=merges,
        review_repository=reviews,
    )

    import_service.import_bibliographic_publications(
        PROJECT_ID, "first.ris", "RIS", [_publication(1, "Author One")]
    )
    _, warning_history = import_service.import_bibliographic_publications(
        PROJECT_ID, "second.ris", "RIS", [_publication(2, "Author Two")]
    )
    before_summary = summary_service.get_sources_summary(PROJECT_ID)
    before_metrics = metrics_service.get_metrics(PROJECT_ID)

    assert before_summary.source_summaries[0].successful_imports_count == 1
    assert before_summary.source_summaries[0].warning_imports_count == 1
    assert before_summary.import_history[0].effective_status == "warning"

    review_service.accept(PROJECT_ID, warning_history.import_id, reviewer_id="alice")

    after_summary = summary_service.get_sources_summary(PROJECT_ID)
    after_metrics = metrics_service.get_metrics(PROJECT_ID)

    assert after_summary.source_summaries[0].successful_imports_count == 2
    assert after_summary.source_summaries[0].warning_imports_count == 0
    assert (
        after_summary.source_summaries[0].records_added_count
        == before_summary.source_summaries[0].records_added_count
    )
    assert (
        after_summary.working_collection.total_records
        == before_summary.working_collection.total_records
    )
    assert all(
        item.effective_status != "warning" for item in after_summary.import_history
    )
    assert after_metrics == before_metrics
