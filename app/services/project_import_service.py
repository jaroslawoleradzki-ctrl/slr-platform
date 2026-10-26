from __future__ import annotations

import hashlib
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
from app.repositories.import_source_record_repository import (
    ImportSkipAuditRecord,
    ImportSourceRecord,
    ImportSourceRecordRepository,
    default_import_source_record_repository,
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
        source_record_repository: ImportSourceRecordRepository | None = None,
    ) -> None:
        self._pub_repo = publication_repository or default_project_publication_repository()
        self._history_repo = import_history_repository or default_import_history_repository()
        self._norm_repo = normalization_repository or default_normalization_execution_repository()
        self._tx_manager = transaction_manager or default_transaction_manager()
        self._snapshot_repo = snapshot_repository
        self._source_repo = source_record_repository or default_import_source_record_repository()

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
        import_id = uuid4()
        try:
            if isinstance(self._pub_repo, SqliteProjectPublicationRepository):
                group_result = self._pub_repo.import_source_publications(
                    project_id, publications, import_id=import_id, connection=conn
                )
            else:
                group_result = self._pub_repo.import_source_publications(
                    project_id, publications, import_id=import_id
                )
        except TypeError:
            if isinstance(self._pub_repo, SqliteProjectPublicationRepository):
                group_result = self._pub_repo.import_source_publications(
                    project_id, publications, connection=conn
                )
            else:
                group_result = self._pub_repo.import_source_publications(
                    project_id, publications
                )

        history_record = ImportHistoryRecord(
            import_id=import_id,
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
        source_file_hash: str | None = None,
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
                source_file_hash,
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
                source_file_hash,
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
        source_file_hash: str | None = None,
    ) -> tuple[PublicationImportResult, ImportHistoryRecord]:
        import_id = uuid4()
        try:
            existing_pubs = self._pub_repo.get_publications(project_id, connection=conn)
        except TypeError:
            existing_pubs = self._pub_repo.get_publications(project_id)
        existing_by_doi: dict[str, object] = {}
        for pub in existing_pubs:
            for ident in pub.identifiers:
                if ident.type is IdentifierType.DOI:
                    existing_by_doi.setdefault(ident.value.strip().casefold(), pub)

        new_publications: list[Publication] = []
        skipped_count = 0
        repeated_count = 0
        doi_duplicate_count = 0
        title_candidate_count = 0
        for index, publication in enumerate(publications):
            doi = None
            for ident in publication.identifiers:
                if ident.type is IdentifierType.DOI:
                    doi = ident.value.strip()
                    break
            normalized_doi = doi.casefold() if doi else None

            file_hash = source_file_hash
            if file_hash is None:
                fallback_payload = "|".join(
                    f"{p.title.strip().casefold()}::{','.join(a.display_name for a in p.authors)}::{p.publication_year or ''}"
                    for p in publications
                )
                file_hash = hashlib.sha256(f"{filename}|{fallback_payload}".encode("utf-8")).hexdigest()
            occurrence_payload = f"{project_id}|{file_hash}|{index + 1}"
            source_record_id = hashlib.sha256(occurrence_payload.encode("utf-8")).hexdigest()

            if self._source_repo.find_source_record_by_id(project_id, source_record_id) is not None:
                repeated_count += 1
                continue

            matched = existing_by_doi.get(normalized_doi) if normalized_doi else None
            if matched is not None:
                # Exact DOI duplicate: preserve source record and audit the skip.
                self._source_repo.create_source_record(
                    ImportSourceRecord(
                        source_record_id=source_record_id,
                        project_id=project_id,
                        import_id=import_id,
                        source_filename=filename,
                        source_file_hash=file_hash,
                        source_record_index=index + 1,
                        title=publication.title,
                        publication_year=publication.publication_year,
                        original_doi=doi,
                        normalized_doi=normalized_doi,
                        authors=tuple(a.display_name for a in publication.authors),
                        document_type=publication.document_type.value if publication.document_type else None,
                        provenance=publication.provenance[0].model_dump(mode="json") if publication.provenance else {},
                        canonical_publication_id=str(matched.record_id),
                        duplicate_match_type="exact_doi",
                        duplicate_match_reason="Normalized DOI equals an existing publication",
                        recovery_status="not_needed",
                    ),
                    connection=conn,
                )
                self._source_repo.create_skip_audit(
                    ImportSkipAuditRecord(
                        skip_audit_id=str(uuid4()),
                        project_id=project_id,
                        import_id=import_id,
                        source_filename=filename,
                        source_file_hash=file_hash,
                        source_record_index=index + 1,
                        source_title=publication.title,
                        source_doi=doi,
                        matched_publication_id=str(matched.record_id),
                        match_type="exact_doi",
                        match_reason="Normalized DOI equals an existing publication",
                        proposed_action="link_to_existing_canonical",
                        review_required=False,
                    ),
                    connection=conn,
                )
                skipped_count += 1
                doi_duplicate_count += 1
                continue

            new_publications.append(publication)
            title_match = any(
                p.title.strip().casefold() == publication.title.strip().casefold() for p in existing_pubs
            )
            if title_match and not normalized_doi:
                title_candidate_count += 1
            self._source_repo.create_source_record(
                ImportSourceRecord(
                    source_record_id=source_record_id,
                    project_id=project_id,
                    import_id=import_id,
                    source_filename=filename,
                    source_file_hash=file_hash,
                    source_record_index=index + 1,
                    title=publication.title,
                    publication_year=publication.publication_year,
                    original_doi=doi,
                    normalized_doi=normalized_doi,
                    authors=tuple(a.display_name for a in publication.authors),
                    document_type=publication.document_type.value if publication.document_type else None,
                    provenance=publication.provenance[0].model_dump(mode="json") if publication.provenance else {},
                    canonical_publication_id=str(publication.record_id),
                    duplicate_match_type="title_candidate" if title_match and not normalized_doi else None,
                    duplicate_match_reason="Same title without DOI requires manual review" if title_match and not normalized_doi else None,
                    recovery_status="imported",
                ),
                connection=conn,
            )

        try:
            if isinstance(self._pub_repo, SqliteProjectPublicationRepository):
                import_result = self._pub_repo.import_source_publications(
                    project_id, new_publications, import_id=import_id, connection=conn
                )
            else:
                import_result = self._pub_repo.import_source_publications(
                    project_id, new_publications, import_id=import_id
                )
        except TypeError:
            if isinstance(self._pub_repo, SqliteProjectPublicationRepository):
                import_result = self._pub_repo.import_source_publications(
                    project_id, new_publications, connection=conn
                )
            else:
                import_result = self._pub_repo.import_source_publications(
                    project_id, new_publications
                )

        warnings: list[str] = []
        if doi_duplicate_count:
            warnings.append(
                f"Linked {doi_duplicate_count} exact DOI duplicate source record(s) to existing canonical publications."
            )
        if repeated_count:
            warnings.append(
                f"Skipped {repeated_count} repeated source occurrence(s) from a previously imported file."
            )
        if title_candidate_count:
            warnings.append(
                f"Imported {title_candidate_count} title-only candidate(s); manual duplicate review is required."
            )

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

        import_result = PublicationImportResult(
            imported_count=import_result.imported_count,
            skipped_count=skipped_count + import_result.skipped_count,
            working_collection_count=import_result.working_collection_count,
        )

        if import_result.imported_count > 0:
            if isinstance(self._norm_repo, SqliteNormalizationExecutionRepository):
                self._norm_repo.delete_for_project(project_id, connection=conn)
            else:
                self._norm_repo.delete_for_project(project_id)

        return import_result, history_record


default_project_import_service = ProjectImportService()
