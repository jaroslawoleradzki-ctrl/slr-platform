from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.repositories.duplicate_review_decision_repository import (
    DuplicateReviewDecisionRepository,
    default_duplicate_review_decision_repository,
)
from app.repositories.import_history_repository import ImportHistoryRepository, default_import_history_repository
from app.repositories.normalization_execution_repository import (
    NormalizationExecutionRepository,
    default_normalization_execution_repository,
)
from app.repositories.project_publication_repository import (
    ProjectPublicationRepository,
    default_project_publication_repository,
)
from app.repositories.project_repository import ProjectRepository, default_project_repository
from app.repositories.screening_criterion_repository import (
    ScreeningCriterionRepository,
    default_screening_criterion_repository,
)
from app.repositories.screening_decision_repository import (
    ScreeningDecisionRepository,
    default_screening_decision_repository,
)
from app.repositories.search_result_snapshot_repository import (
    SearchResultSnapshotRepository,
    default_search_result_snapshot_repository,
)
from app.repositories.search_strategy_repository import SearchStrategyRepository, default_search_strategy_repository
from app.repositories.transaction_manager import SqliteTransactionManager, default_transaction_manager


@runtime_checkable
class ProjectDeletionService(Protocol):
    """Service that atomically deletes a project and all its related data."""

    def delete_project(self, project_id: str) -> None: ...


class SqliteProjectDeletionService:
    def __init__(
        self,
        project_repo: ProjectRepository | None = None,
        import_history_repo: ImportHistoryRepository | None = None,
        normalization_repo: NormalizationExecutionRepository | None = None,
        publication_repo: ProjectPublicationRepository | None = None,
        duplicate_review_repo: DuplicateReviewDecisionRepository | None = None,
        screening_decision_repo: ScreeningDecisionRepository | None = None,
        screening_criterion_repo: ScreeningCriterionRepository | None = None,
        search_strategy_repo: SearchStrategyRepository | None = None,
        search_result_snapshot_repo: SearchResultSnapshotRepository | None = None,
        tx_manager: SqliteTransactionManager | None = None,
    ) -> None:
        self._project_repo = project_repo or default_project_repository()
        self._import_history_repo = import_history_repo or default_import_history_repository()
        self._normalization_repo = normalization_repo or default_normalization_execution_repository()
        self._publication_repo = publication_repo or default_project_publication_repository()
        self._duplicate_review_repo = duplicate_review_repo or default_duplicate_review_decision_repository()
        self._screening_decision_repo = screening_decision_repo or default_screening_decision_repository()
        self._screening_criterion_repo = screening_criterion_repo or default_screening_criterion_repository()
        self._search_strategy_repo = search_strategy_repo or default_search_strategy_repository()
        self._search_result_snapshot_repo = (
            search_result_snapshot_repo or default_search_result_snapshot_repository()
        )
        self._tx_manager = tx_manager or default_transaction_manager()

    def delete_project(self, project_id: str) -> None:
        with self._tx_manager.transaction() as conn:
            # Delete dependent data first. All repositories accept an optional connection.
            self._import_history_repo.delete_for_project(project_id, connection=conn)
            self._normalization_repo.delete_for_project(project_id, connection=conn)
            self._publication_repo.delete_for_project(project_id, connection=conn)
            self._duplicate_review_repo.delete_for_project(project_id, connection=conn)
            self._screening_decision_repo.delete_for_project(project_id, connection=conn)
            self._screening_criterion_repo.delete_for_project(project_id, connection=conn)
            self._search_result_snapshot_repo.delete_for_project(project_id, connection=conn)
            self._search_strategy_repo.delete_for_project(project_id, connection=conn)
            # Delete the project row last. The repository existence check is
            # deliberately inside this transaction so a missing project also
            # rolls back every preceding cleanup statement.
            self._project_repo.delete(project_id, connection=conn)


def default_project_deletion_service() -> SqliteProjectDeletionService:
    return SqliteProjectDeletionService()
