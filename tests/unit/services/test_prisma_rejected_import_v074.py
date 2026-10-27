from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4

from app.domain.identifiers import Identifier, IdentifierType
from app.domain.project import Project
from app.domain.provenance import ProvenanceEntry
from app.domain.publication import Publication
from app.repositories.duplicate_merge_repository import SqliteDuplicateMergeRepository
from app.repositories.duplicate_review_decision_repository import SqliteDuplicateReviewDecisionRepository
from app.repositories.import_history_repository import ImportHistoryRecord, SqliteImportHistoryRepository
from app.repositories.import_review_repository import SqliteImportReviewRepository
from app.repositories.import_source_record_repository import ImportSourceRecord, SqliteImportSourceRecordRepository
from app.repositories.normalization_execution_repository import SqliteNormalizationExecutionRepository
from app.repositories.project_publication_repository import SqliteProjectPublicationRepository
from app.repositories.project_repository import SqliteProjectRepository
from app.repositories.transaction_manager import SqliteTransactionManager
from app.services.import_review_service import ImportReviewService
from app.services.prisma_metrics_service import PrismaMetricsService

PROJECT_ID = "prisma-rejected-project"


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


def _publication(number: int) -> Publication:
    return Publication(
        record_id=UUID(f"00000000-0000-0000-0000-{number:012d}"),
        title=f"Rejected publication {number}",
        publication_year=2024,
        identifiers=[Identifier(type=IdentifierType.DOI, value=f"10.1000/rejected-{number}")],
        provenance=[ProvenanceEntry(source="ris", source_record_id=str(number))],
    )


def test_prisma_classifies_rejected_import_as_removed_before_screening(tmp_path: Path) -> None:
    database = tmp_path / "prisma-rejected.db"
    SqliteProjectRepository(database).create(Project(project_id=PROJECT_ID, title="Review"))
    history = SqliteImportHistoryRepository(database)
    sources = SqliteImportSourceRecordRepository(database)
    publications = SqliteProjectPublicationRepository(database)
    decisions = SqliteDuplicateReviewDecisionRepository(database)
    merges = SqliteDuplicateMergeRepository(database)
    reviews = SqliteImportReviewRepository(database)
    import_id = uuid4()
    records = [_publication(1), _publication(2)]
    history.create(
        ImportHistoryRecord(
            import_id=import_id,
            project_id=PROJECT_ID,
            source_type="file",
            filename="rejected.ris",
            format="RIS",
            provider=None,
            query=None,
            records_count=2,
            total_available=None,
            status="warning",
            warnings=("Skipped 1 duplicate.",),
            created_at=datetime(2026, 10, 27, 10, 0, tzinfo=timezone.utc),
        )
    )
    for index, publication in enumerate(records):
        sources.create_source_record(
            ImportSourceRecord(
                source_record_id=f"rejected-source-{index + 1}",
                project_id=PROJECT_ID,
                import_id=import_id,
                source_filename="rejected.ris",
                source_file_hash=None,
                source_record_index=index + 1,
                title=publication.title,
                publication_year=publication.publication_year,
                original_doi=publication.identifiers[0].value,
                normalized_doi=publication.identifiers[0].value,
                authors=("Reviewer",),
                document_type="journal_article",
                provenance=publication.provenance[0].model_dump(mode="json"),
                canonical_publication_id=str(publication.record_id),
                recovery_status="imported",
            )
        )
    publications.import_source_publications(
        PROJECT_ID, records, import_id=import_id, preserve_source_occurrences=True
    )
    review_service = ImportReviewService(
        publication_repository=publications,
        import_history_repository=history,
        source_record_repository=sources,
        review_repository=reviews,
        normalization_repository=SqliteNormalizationExecutionRepository(database),
        transaction_manager=SqliteTransactionManager(database),
    )
    review_service.reject(
        PROJECT_ID, import_id, reviewer_id="alice", confirm_rejection=True
    )

    service = PrismaMetricsService(
        publication_repository=publications,
        import_history_repository=history,
        decision_repository=decisions,
        workflow_status_service=_Workflow(),
        source_record_repository=sources,
        merge_repository=merges,
        review_repository=reviews,
    )
    metrics = service.get_metrics(PROJECT_ID)

    assert metrics.total_identified == 2
    assert metrics.records_removed_rejected_import == 2
    assert metrics.records_removed_prescreening == 2
    assert metrics.records_after_normalization == 0
    assert metrics.records_before_dedup == 0
    assert metrics.canonical_publications == 0
    assert metrics.persisted_source_records == 2
    assert metrics.records_screened_title_abstract == 0
