from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.repositories.conflict_resolution_repository import (
    SqliteConflictResolutionRepository,
    default_conflict_resolution_repository,
)
from app.repositories.duplicate_merge_repository import (
    DuplicateMergeRepository,
    default_duplicate_merge_repository,
)
from app.repositories.duplicate_review_decision_repository import (
    DuplicateReviewDecisionRepository,
    default_duplicate_review_decision_repository,
)
from app.repositories.extraction_repository import SqliteExtractionRepository, default_extraction_repository
from app.repositories.full_text_availability_repository import (
    FullTextAvailabilityRepository,
    default_full_text_availability_repository,
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
from app.repositories.quality_assessment_repository import (
    ProjectQualityAssessmentConfigurationRepository,
    QualityAssessmentRepository,
)
from app.repositories.screening_criterion_repository import (
    ScreeningCriterionRepository,
    default_screening_criterion_repository,
)
from app.repositories.screening_decision_repository import (
    ScreeningDecisionRepository,
    default_screening_decision_repository,
)
from app.repositories.screening_reviewer_assignment_repository import (
    SqliteScreeningReviewerAssignmentRepository,
    default_screening_reviewer_assignment_repository,
)
from app.repositories.search_result_snapshot_repository import (
    SearchResultSnapshotRepository,
    default_search_result_snapshot_repository,
)
from app.repositories.search_strategy_repository import SearchStrategyRepository, default_search_strategy_repository
from app.repositories.sqlite_quality_assessment_repository import (
    default_project_quality_assessment_configuration_repository,
    default_quality_assessment_repository,
)
from app.repositories.synthesis_classification_repository import (
    SynthesisClassificationRepository,
    default_synthesis_classification_repository,
)
from app.repositories.synthesis_context_repository import (
    SqliteSynthesisContextRepository,
    default_synthesis_context_repository,
)
from app.repositories.synthesis_gap_repository import (
    SqliteSynthesisGapRepository,
    default_synthesis_gap_repository,
)
from app.repositories.synthesis_matrix_repository import (
    SqliteSynthesisMatrixRepository,
    default_synthesis_matrix_repository,
)
from app.repositories.synthesis_mechanism_repository import (
    SqliteSynthesisMechanismRepository,
    default_synthesis_mechanism_repository,
)
from app.repositories.synthesis_snapshot_repository import (
    SqliteSynthesisSnapshotRepository,
    default_synthesis_snapshot_repository,
)
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
        duplicate_merge_repo: DuplicateMergeRepository | None = None,
        screening_decision_repo: ScreeningDecisionRepository | None = None,
        screening_criterion_repo: ScreeningCriterionRepository | None = None,
        search_strategy_repo: SearchStrategyRepository | None = None,
        search_result_snapshot_repo: SearchResultSnapshotRepository | None = None,
        full_text_availability_repo: FullTextAvailabilityRepository | None = None,
        screening_reviewer_assignment_repo: SqliteScreeningReviewerAssignmentRepository | None = None,
        conflict_resolution_repo: SqliteConflictResolutionRepository | None = None,
        quality_assessment_repo: QualityAssessmentRepository | None = None,
        quality_assessment_config_repo: ProjectQualityAssessmentConfigurationRepository | None = None,
        extraction_repo: SqliteExtractionRepository | None = None,
        classification_repo: SynthesisClassificationRepository | None = None,
        matrix_repo: SqliteSynthesisMatrixRepository | None = None,
        mechanism_repo: SqliteSynthesisMechanismRepository | None = None,
        context_repo: SqliteSynthesisContextRepository | None = None,
        gap_repo: SqliteSynthesisGapRepository | None = None,
        snapshot_repo: SqliteSynthesisSnapshotRepository | None = None,
        tx_manager: SqliteTransactionManager | None = None,
    ) -> None:
        self._project_repo = project_repo or default_project_repository()
        self._import_history_repo = import_history_repo or default_import_history_repository()
        self._normalization_repo = normalization_repo or default_normalization_execution_repository()
        self._publication_repo = publication_repo or default_project_publication_repository()
        self._duplicate_review_repo = duplicate_review_repo or default_duplicate_review_decision_repository()
        self._duplicate_merge_repo = duplicate_merge_repo or default_duplicate_merge_repository()
        self._screening_decision_repo = screening_decision_repo or default_screening_decision_repository()
        self._full_text_availability_repo = (
            full_text_availability_repo or default_full_text_availability_repository()
        )
        self._screening_criterion_repo = screening_criterion_repo or default_screening_criterion_repository()
        self._search_strategy_repo = search_strategy_repo or default_search_strategy_repository()
        self._search_result_snapshot_repo = search_result_snapshot_repo or default_search_result_snapshot_repository()
        self._screening_reviewer_assignment_repo = (
            screening_reviewer_assignment_repo or default_screening_reviewer_assignment_repository()
        )
        self._quality_assessment_repo = (
            quality_assessment_repo or default_quality_assessment_repository()
        )
        self._quality_assessment_config_repo = (
            quality_assessment_config_repo
            or default_project_quality_assessment_configuration_repository()
        )
        self._conflict_resolution_repo = conflict_resolution_repo or default_conflict_resolution_repository()
        self._extraction_repo = extraction_repo or default_extraction_repository()
        self._classification_repo = classification_repo or default_synthesis_classification_repository()
        self._matrix_repo = matrix_repo or default_synthesis_matrix_repository()
        self._mechanism_repo = mechanism_repo or default_synthesis_mechanism_repository()
        self._context_repo = context_repo or default_synthesis_context_repository()
        self._gap_repo = gap_repo or default_synthesis_gap_repository()
        self._snapshot_repo = snapshot_repo or default_synthesis_snapshot_repository()
        self._tx_manager = tx_manager or default_transaction_manager()

    def delete_project(self, project_id: str) -> None:
        with self._tx_manager.transaction() as conn:
            # Delete dependent data first. All repositories accept an optional connection.
            self._import_history_repo.delete_for_project(project_id, connection=conn)
            self._normalization_repo.delete_for_project(project_id, connection=conn)
            self._duplicate_review_repo.delete_for_project(project_id, connection=conn)
            self._duplicate_merge_repo.delete_for_project(project_id, connection=conn)
            self._publication_repo.delete_for_project(project_id, connection=conn)
            self._conflict_resolution_repo.delete_for_project(project_id, connection=conn)
            self._extraction_repo.delete_for_project(project_id, connection=conn)
            self._screening_decision_repo.delete_for_project(project_id, connection=conn)
            self._screening_reviewer_assignment_repo.delete_for_project(project_id, connection=conn)
            self._full_text_availability_repo.delete_for_project(project_id, connection=conn)
            self._screening_criterion_repo.delete_for_project(project_id, connection=conn)
            self._search_result_snapshot_repo.delete_for_project(project_id, connection=conn)
            self._search_strategy_repo.delete_for_project(project_id, connection=conn)
            self._quality_assessment_repo.delete_for_project(project_id, connection=conn)
            self._quality_assessment_config_repo.delete_for_project(project_id, connection=conn)
            # Phase 10 synthesis data (Tasks 10.2-10.7). Deletion is ordered so that
            # dependent tables are removed before their parents.
            self._snapshot_repo.delete_for_project(project_id, connection=conn)
            self._gap_repo.delete_for_project(project_id, connection=conn)
            self._context_repo.delete_for_project(project_id, connection=conn)
            self._mechanism_repo.delete_for_project(project_id, connection=conn)
            self._matrix_repo.delete_for_project(project_id, connection=conn)
            self._classification_repo.delete_for_project(project_id, connection=conn)
            # Delete the project row last. The repository existence check is
            # deliberately inside this transaction so a missing project also
            # rolls back every preceding cleanup statement.
            self._project_repo.delete(project_id, connection=conn)


def default_project_deletion_service() -> SqliteProjectDeletionService:
    return SqliteProjectDeletionService()
