from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from app.domain.author import Author
from app.domain.project import Project
from app.domain.provenance import ProvenanceEntry
from app.domain.publication import Publication
from app.repositories.duplicate_merge_repository import SqliteDuplicateMergeRepository
from app.repositories.duplicate_review_decision_repository import SqliteDuplicateReviewDecisionRepository
from app.repositories.import_history_repository import SqliteImportHistoryRepository
from app.repositories.import_source_record_repository import SqliteImportSourceRecordRepository
from app.repositories.normalization_execution_repository import SqliteNormalizationExecutionRepository
from app.repositories.project_publication_repository import SqliteProjectPublicationRepository
from app.repositories.project_repository import SqliteProjectRepository
from app.repositories.transaction_manager import SqliteTransactionManager
from app.services.project_duplicate_service import ProjectDuplicateService
from app.services.project_import_service import ProjectImportService
from app.services.screening_input_service import (
    ScreeningInputReadinessStatus,
    ScreeningInputService,
)

PROJECT_ID = "v074-workflow"


def _publication(number: int, author: str) -> Publication:
    return Publication(
        record_id=UUID(f"00000000-0000-0000-0000-{number:012d}"),
        title="A shared title for duplicate readiness",
        authors=[Author(display_name=author)],
        publication_year=2024 + number,
        provenance=[ProvenanceEntry(source="ris", source_record_id=f"ris-{number}")],
        created_at=datetime(2026, 10, 27, tzinfo=timezone.utc),
    )


def test_merge_followed_by_new_import_is_consistent_across_services(tmp_path: Path) -> None:
    database = tmp_path / "v074-workflow.db"
    SqliteProjectRepository(database).create(Project(project_id=PROJECT_ID, title="V074"))
    publications = SqliteProjectPublicationRepository(database)
    history = SqliteImportHistoryRepository(database)
    source_records = SqliteImportSourceRecordRepository(database)
    decisions = SqliteDuplicateReviewDecisionRepository(database)
    merges = SqliteDuplicateMergeRepository(database)
    transaction_manager = SqliteTransactionManager(database)
    import_service = ProjectImportService(
        publication_repository=publications,
        import_history_repository=history,
        normalization_repository=SqliteNormalizationExecutionRepository(database),
        transaction_manager=transaction_manager,
        source_record_repository=source_records,
    )
    duplicate_service = ProjectDuplicateService(
        publications,
        decisions,
        merge_repository=merges,
        transaction_manager=transaction_manager,
    )
    screening_service = ScreeningInputService(
        publications,
        decisions,
        merge_repository=merges,
    )

    first = _publication(1, "Author One")
    second = _publication(2, "Author Two")
    import_service.import_bibliographic_publications(
        PROJECT_ID, "first.ris", "RIS", [first]
    )
    import_service.import_bibliographic_publications(
        PROJECT_ID, "second.ris", "RIS", [second]
    )
    original_group = duplicate_service.get_candidate_duplicate_groups(PROJECT_ID).groups[0]
    duplicate_service.merge_group(PROJECT_ID, original_group.group_id)

    later = _publication(3, "Author Three")
    import_service.import_bibliographic_publications(
        PROJECT_ID, "third.ris", "RIS", [later]
    )

    duplicate_response = duplicate_service.get_candidate_duplicate_groups(PROJECT_ID)
    screening_input = screening_service.get_input_set(PROJECT_ID)

    pending = [group for group in duplicate_response.groups if group.status.value == "PENDING"]
    assert len(pending) == 1
    assert duplicate_response.readiness.status == "pending_review"
    assert duplicate_response.readiness.blocking_group_ids == [pending[0].group_id]
    assert screening_input.readiness_status is ScreeningInputReadinessStatus.UNRESOLVED_DUPLICATES
    assert screening_input.duplicate_readiness.blocking_group_ids == (pending[0].group_id,)
    assert screening_input.publications == ()
