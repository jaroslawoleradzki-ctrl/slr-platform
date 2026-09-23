from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from uuid import UUID

from app.api.dto.pre_screening import (
    ImportedRecordResponse,
    ImportedRecordsPageResponse,
)
from app.domain.pre_screening import (
    PreScreeningArchivedRecord,
    PreScreeningDecision,
    PreScreeningRemovalReason,
    PreScreeningStatus,
)
from app.domain.publication import Publication
from app.repositories.corpus_finalization_repository import (
    CorpusFinalizationRepository,
    SqliteCorpusFinalizationRepository,
)
from app.repositories.pre_screening_archive_repository import (
    PreScreeningArchiveRepository,
    default_pre_screening_archive_repository,
)
from app.repositories.pre_screening_decision_repository import (
    PreScreeningDecisionRepository,
    default_pre_screening_decision_repository,
)
from app.repositories.project_publication_repository import (
    ProjectNotFoundError,
    ProjectPublicationRepository,
    default_project_publication_repository,
)
from app.repositories.screening_decision_repository import (
    ScreeningDecisionRepository,
    SqliteScreeningDecisionRepository,
)
from app.repositories.transaction_manager import (
    SqliteTransactionManager,
)


class PreScreeningRecordNotFoundError(LookupError):
    pass


class CorpusFinalizedError(RuntimeError):
    """Raised when attempting pre-screening modifications after corpus finalization."""

    pass


class RecordAlreadyScreenedError(RuntimeError):
    """Raised when attempting pre-screening modifications on a record with formal screening decisions."""

    pass


class PreScreeningReviewService:
    """Service providing pre-screening review, search/filter, manual removal, archival, and restore."""

    def __init__(
        self,
        publication_repository: ProjectPublicationRepository | None = None,
        decision_repository: PreScreeningDecisionRepository | None = None,
        finalization_repository: CorpusFinalizationRepository | None = None,
        screening_decision_repository: ScreeningDecisionRepository | None = None,
        archive_repository: PreScreeningArchiveRepository | None = None,
        transaction_manager: SqliteTransactionManager | None = None,
    ) -> None:
        self._pub_repo = publication_repository or default_project_publication_repository()
        self._decision_repo = decision_repository or default_pre_screening_decision_repository()
        self._finalization_repo = finalization_repository or (
            SqliteCorpusFinalizationRepository(self._pub_repo._database_path)
            if hasattr(self._pub_repo, "_database_path")
            else None
        )
        self._screening_decision_repo = screening_decision_repository or (
            SqliteScreeningDecisionRepository(self._pub_repo._database_path)
            if hasattr(self._pub_repo, "_database_path")
            else None
        )
        self._archive_repo = archive_repository or (
            default_pre_screening_archive_repository()
            if hasattr(self._pub_repo, "_database_path")
            else None
        )
        self._tx_manager = transaction_manager or (
            SqliteTransactionManager(self._pub_repo._database_path)
            if hasattr(self._pub_repo, "_database_path")
            else None
        )

    def _ensure_modifiable(self, project_id: str, record_id: UUID) -> None:
        if self._finalization_repo is not None:
            finalization = self._finalization_repo.get_latest_finalization(project_id)
            if finalization is not None:
                raise CorpusFinalizedError(
                    f"Corpus for project '{project_id}' is finalized; pre-screening modifications are locked."
                )
        if self._screening_decision_repo is not None:
            from app.domain.screening import ScreeningStage

            for stage in (ScreeningStage.TITLE_ABSTRACT, ScreeningStage.FULL_TEXT):
                history = self._screening_decision_repo.list_history(project_id, record_id, stage)
                if history:
                    raise RecordAlreadyScreenedError(
                        f"Record '{record_id}' already has formal {stage.value} screening decisions; cannot modify pre-screening state."
                    )

    def archive_pre_screening_removal(
        self,
        project_id: str,
        import_id: UUID,
        record_id: UUID,
        *,
        reason: PreScreeningRemovalReason,
        notes: str | None = None,
        reviewer_id: str = "default_reviewer",
        physical_delete: bool = False,
        connection: sqlite3.Connection | None = None,
    ) -> PreScreeningArchivedRecord:
        """Domain operation preparing a publication for pre-screening removal and durable archival."""
        self._ensure_project(project_id)
        self._ensure_modifiable(project_id, record_id)

        pub = self._find_publication_in_project(project_id, record_id)
        now = datetime.now(timezone.utc)

        if pub is None:
            # If not in project_publications, check if already archived in this project
            if self._archive_repo is not None:
                existing = self._archive_repo.get_archived_record(project_id, record_id, connection=connection)
                if existing is not None:
                    return existing
            raise PreScreeningRecordNotFoundError(
                f"Publication '{record_id}' was not found in project '{project_id}'."
            )

        archived = PreScreeningArchivedRecord.from_publication(
            publication=pub,
            project_id=project_id,
            removal_reason=reason,
            import_id=import_id,
            removal_notes=notes,
            removed_by=reviewer_id,
            removed_at=now,
        )

        decision = PreScreeningDecision(
            project_id=project_id,
            record_id=record_id,
            import_id=import_id,
            status=PreScreeningStatus.REMOVED,
            reason=reason,
            notes=notes,
            reviewer_id=reviewer_id,
            decided_at=now,
            created_at=now,
        )

        def _execute(conn: sqlite3.Connection | None) -> None:
            if self._archive_repo is not None:
                self._archive_repo.archive_record(archived, connection=conn)
            self._decision_repo.save_decision(decision, connection=conn)
            if physical_delete:
                if hasattr(self._pub_repo, "delete_publication"):
                    self._pub_repo.delete_publication(project_id, record_id, connection=conn)
            else:
                self._pub_repo.update_pre_screening_status(project_id, record_id, "removed", connection=conn)

        if connection is not None:
            _execute(connection)
        elif self._tx_manager is not None:
            with self._tx_manager.transaction() as conn:
                _execute(conn)
        else:
            _execute(None)

        return archived

    def remove_record(
        self,
        project_id: str,
        import_id: UUID,
        record_id: UUID,
        *,
        reason: PreScreeningRemovalReason,
        notes: str | None = None,
        reviewer_id: str = "default_reviewer",
    ) -> ImportedRecordResponse:
        self._ensure_project(project_id)
        self._ensure_modifiable(project_id, record_id)
        pub = self._find_record(project_id, record_id)

        archived = self.archive_pre_screening_removal(
            project_id,
            import_id,
            record_id,
            reason=reason,
            notes=notes,
            reviewer_id=reviewer_id,
            physical_delete=False,
        )

        decision = PreScreeningDecision(
            decision_id=archived.archive_id,
            project_id=project_id,
            record_id=record_id,
            import_id=import_id,
            status=PreScreeningStatus.REMOVED,
            reason=reason,
            notes=notes,
            reviewer_id=reviewer_id,
            decided_at=archived.removed_at,
            created_at=archived.created_at,
        )

        return ImportedRecordResponse.from_domain(
            publication=pub,
            project_id=project_id,
            import_id=import_id,
            status=PreScreeningStatus.REMOVED,
            latest_decision=decision,
        )

    def restore_record(
        self,
        project_id: str,
        import_id: UUID,
        record_id: UUID,
        *,
        reviewer_id: str = "default_reviewer",
    ) -> ImportedRecordResponse:
        self._ensure_project(project_id)
        self._ensure_modifiable(project_id, record_id)

        now = datetime.now(timezone.utc)
        decision = PreScreeningDecision(
            project_id=project_id,
            record_id=record_id,
            import_id=import_id,
            status=PreScreeningStatus.RETAINED,
            reviewer_id=reviewer_id,
            decided_at=now,
            created_at=now,
        )

        pub = self._find_publication_in_project(project_id, record_id)

        if pub is not None:
            def _execute_existing(conn: sqlite3.Connection | None) -> None:
                self._decision_repo.save_decision(decision, connection=conn)
                self._pub_repo.update_pre_screening_status(project_id, record_id, "retained", connection=conn)
                if self._archive_repo is not None:
                    self._archive_repo.delete_archived_record(project_id, record_id, connection=conn)

            if self._tx_manager is not None:
                with self._tx_manager.transaction() as conn:
                    _execute_existing(conn)
            else:
                _execute_existing(None)

            return ImportedRecordResponse.from_domain(
                publication=pub,
                project_id=project_id,
                import_id=import_id,
                status=PreScreeningStatus.RETAINED,
                latest_decision=decision,
            )

        # Record was physically deleted and resides in archive
        if self._archive_repo is not None:
            archive_repo = self._archive_repo
            archived = archive_repo.get_archived_record(project_id, record_id)
            if archived is not None:
                restored_pub = archived.to_publication()

                def _execute_restored(conn: sqlite3.Connection | None) -> None:
                    self._pub_repo.import_source_publications(
                        project_id, [restored_pub], import_id=import_id, connection=conn
                    )
                    self._decision_repo.save_decision(decision, connection=conn)
                    archive_repo.delete_archived_record(project_id, record_id, connection=conn)

                if self._tx_manager is not None:
                    with self._tx_manager.transaction() as conn:
                        _execute_restored(conn)
                else:
                    _execute_restored(None)

                return ImportedRecordResponse.from_domain(
                    publication=restored_pub,
                    project_id=project_id,
                    import_id=import_id,
                    status=PreScreeningStatus.RETAINED,
                    latest_decision=decision,
                )

        raise PreScreeningRecordNotFoundError(f"Record '{record_id}' not found in project '{project_id}'.")

    def list_imported_records(
        self,
        project_id: str,
        import_id: UUID,
        *,
        search: str | None = None,
        status_filter: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> ImportedRecordsPageResponse:
        self._ensure_project(project_id)
        if limit < 1:
            raise ValueError("limit must be at least 1")
        if offset < 0:
            raise ValueError("offset must not be negative")

        total_imported, retained_count, removed_count = self._pub_repo.get_import_counts(project_id, import_id)

        filtered_count = self._pub_repo.count_import_publications(
            project_id,
            import_id,
            search=search,
            status_filter=status_filter,
        )

        records_with_status = self._pub_repo.get_import_publications(
            project_id,
            import_id,
            search=search,
            status_filter=status_filter,
            offset=offset,
            limit=limit,
        )

        items: list[ImportedRecordResponse] = []
        for pub, status_str in records_with_status:
            status = PreScreeningStatus(status_str)
            latest_decision = None
            if status == PreScreeningStatus.REMOVED:
                latest_decision = self._decision_repo.get_latest_decision(project_id, pub.record_id)
            items.append(
                ImportedRecordResponse.from_domain(
                    publication=pub,
                    project_id=project_id,
                    import_id=import_id,
                    status=status,
                    latest_decision=latest_decision,
                )
            )

        return ImportedRecordsPageResponse(
            project_id=project_id,
            import_id=import_id,
            total=filtered_count,
            offset=offset,
            limit=limit,
            total_imported=total_imported,
            retained_count=retained_count,
            removed_count=removed_count,
            items=items,
        )

    def get_import_counts(self, project_id: str, import_id: UUID) -> tuple[int, int, int]:
        self._ensure_project(project_id)
        return self._pub_repo.get_import_counts(project_id, import_id)

    def get_archived_record(self, project_id: str, record_id: UUID) -> PreScreeningArchivedRecord | None:
        self._ensure_project(project_id)
        if self._archive_repo is not None:
            return self._archive_repo.get_archived_record(project_id, record_id)
        return None

    def list_archived_records(
        self,
        project_id: str,
        *,
        import_id: UUID | None = None,
        search: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> list[PreScreeningArchivedRecord]:
        self._ensure_project(project_id)
        if self._archive_repo is not None:
            return self._archive_repo.list_archived_for_project(
                project_id, import_id=import_id, search=search, offset=offset, limit=limit
            )
        return []

    def _ensure_project(self, project_id: str) -> None:
        try:
            self._pub_repo.get_publications(project_id)
        except ProjectNotFoundError as exc:
            raise ProjectNotFoundError(project_id) from exc

    def _find_publication_in_project(self, project_id: str, record_id: UUID) -> Publication | None:
        pubs = self._pub_repo.get_publications(project_id)
        for pub in pubs:
            if pub.record_id == record_id:
                return pub
        return None

    def _find_record(self, project_id: str, record_id: UUID) -> Publication:
        pub = self._find_publication_in_project(project_id, record_id)
        if pub is not None:
            return pub
        raise PreScreeningRecordNotFoundError(f"Record '{record_id}' not found in project '{project_id}'.")


def default_pre_screening_review_service() -> PreScreeningReviewService:
    return PreScreeningReviewService()
