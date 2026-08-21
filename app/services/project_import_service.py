from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from uuid import UUID, uuid4

from app.api.dto.search_strategy import (
    ManualSourceDatabase,
    SearchResultRecordResponse,
)
from app.domain.author import Author
from app.domain.identifiers import Identifier, IdentifierType
from app.domain.provenance import ProvenanceEntry
from app.domain.publication import Publication
from app.repositories.import_history_repository import (
    ImportHistoryRecord,
    ImportHistoryRepository,
    SqliteImportHistoryRepository,
    default_import_history_repository,
)
from app.repositories.normalization_execution_repository import (
    NormalizationExecutionRepository,
    SqliteNormalizationExecutionRepository,
    default_normalization_execution_repository,
)
from app.repositories.project_publication_repository import (
    ProjectPublicationRepository,
    PublicationImportResult,
    SqliteProjectPublicationRepository,
    default_project_publication_repository,
)
from app.repositories.search_result_snapshot_repository import (
    SearchResultSnapshotRepository,
)
from app.repositories.transaction_manager import (
    SqliteTransactionManager,
    default_transaction_manager,
)


class ProjectImportService:
    """Service orchestrating atomic multi-repository imports under one transaction boundary."""

    def __init__(
        self,
        publication_repository: ProjectPublicationRepository | None = None,
        import_history_repository: ImportHistoryRepository | None = None,
        normalization_repository: NormalizationExecutionRepository | None = None,
        transaction_manager: SqliteTransactionManager | None = None,
        snapshot_repository: SearchResultSnapshotRepository | None = None,
    ) -> None:
        self._pub_repo = publication_repository or default_project_publication_repository()
        self._history_repo = import_history_repository or default_import_history_repository()
        self._norm_repo = normalization_repository or default_normalization_execution_repository()
        self._tx_manager = transaction_manager or default_transaction_manager()
        self._snapshot_repo = snapshot_repository

    def import_provider_results_group(
        self,
        project_id: str,
        provider_name: str,
        records_group: list[SearchResultRecordResponse],
        query: str | None,
        group_total_available: int | None,
        *,
        connection: sqlite3.Connection | None = None,
    ) -> PublicationImportResult:
        publications = []
        for record in records_group:
            if self._snapshot_repo is not None:
                snapshot = self._snapshot_repo.get(project_id, UUID(record.id))
                if snapshot.provider != record.provider or snapshot.source_id != record.source_id:
                    raise ValueError("search result identity does not match authoritative snapshot")
                if snapshot.provider != provider_name:
                    raise ValueError("snapshot provider does not match import group")
                publications.append(snapshot.publication)
                continue
            identifiers = []
            if record.doi is not None:
                identifiers.append(Identifier(type=IdentifierType.DOI, value=record.doi))
            publications.append(
                Publication(
                    record_id=UUID(record.id),
                    title=record.title,
                    authors=[Author(display_name=name) for name in record.authors],
                    publication_year=record.year,
                    identifiers=identifiers,
                    provenance=[ProvenanceEntry(source=record.provider, source_record_id=record.source_id)],
                )
            )

        if connection is not None:
            return self._import_provider_group_with_conn(
                connection,
                project_id,
                provider_name,
                publications,
                query,
                group_total_available,
            )

        with self._tx_manager.transaction() as conn:
            return self._import_provider_group_with_conn(
                conn,
                project_id,
                provider_name,
                publications,
                query,
                group_total_available,
            )

    def _import_provider_group_with_conn(
        self,
        conn: sqlite3.Connection,
        project_id: str,
        provider_name: str,
        publications: list[Publication],
        query: str | None,
        group_total_available: int | None,
    ) -> PublicationImportResult:
        if isinstance(self._pub_repo, SqliteProjectPublicationRepository):
            group_result = self._pub_repo.import_source_publications(project_id, publications, connection=conn)
        else:
            group_result = self._pub_repo.import_source_publications(project_id, publications)

        history_record = ImportHistoryRecord(
            import_id=uuid4(),
            project_id=project_id,
            source_type="provider",
            filename=None,
            format=None,
            provider=provider_name,
            query=query,
            records_count=group_result.imported_count,
            total_available=group_total_available,
            status="success",
            warnings=(),
            created_at=datetime.now(timezone.utc),
            fingerprint=None,
        )

        if isinstance(self._history_repo, SqliteImportHistoryRepository):
            self._history_repo.create(history_record, connection=conn)
        else:
            self._history_repo.create(history_record)

        if group_result.imported_count > 0:
            if isinstance(self._norm_repo, SqliteNormalizationExecutionRepository):
                self._norm_repo.delete_for_project(project_id, connection=conn)
            else:
                self._norm_repo.delete_for_project(project_id)

        return group_result

    def import_bibliographic_publications(
        self,
        project_id: str,
        filename: str,
        file_format: str,
        publications: list[Publication],
        source_database: ManualSourceDatabase | None = None,
        source_label: str | None = None,
        *,
        connection: sqlite3.Connection | None = None,
    ) -> tuple[PublicationImportResult, ImportHistoryRecord]:
        if connection is not None:
            return self._import_file_with_conn(
                connection,
                project_id,
                filename,
                file_format,
                publications,
                source_database,
                source_label,
            )

        with self._tx_manager.transaction() as conn:
            return self._import_file_with_conn(
                conn,
                project_id,
                filename,
                file_format,
                publications,
                source_database,
                source_label,
            )

    def _import_file_with_conn(
        self,
        conn: sqlite3.Connection,
        project_id: str,
        filename: str,
        file_format: str,
        publications: list[Publication],
        source_database: ManualSourceDatabase | None = None,
        source_label: str | None = None,
    ) -> tuple[PublicationImportResult, ImportHistoryRecord]:
        if isinstance(self._pub_repo, SqliteProjectPublicationRepository):
            import_result = self._pub_repo.import_source_publications(project_id, publications, connection=conn)
        else:
            import_result = self._pub_repo.import_source_publications(project_id, publications)

        warnings: list[str] = []
        if import_result.skipped_count:
            warnings.append(f"Skipped {import_result.skipped_count} duplicate record(s) already in the project.")

        import_id = uuid4()
        history_record = ImportHistoryRecord(
            import_id=import_id,
            project_id=project_id,
            source_type="file",
            filename=filename,
            format=file_format,
            provider=None,
            query=None,
            records_count=import_result.imported_count,
            total_available=None,
            status="warning" if warnings else "success",
            warnings=tuple(warnings),
            created_at=datetime.now(timezone.utc),
            source_database=source_database,
            source_label=source_label,
        )

        if isinstance(self._history_repo, SqliteImportHistoryRepository):
            self._history_repo.create(history_record, connection=conn)
        else:
            self._history_repo.create(history_record)

        if import_result.imported_count > 0:
            if isinstance(self._norm_repo, SqliteNormalizationExecutionRepository):
                self._norm_repo.delete_for_project(project_id, connection=conn)
            else:
                self._norm_repo.delete_for_project(project_id)

        return import_result, history_record


default_project_import_service = ProjectImportService()
