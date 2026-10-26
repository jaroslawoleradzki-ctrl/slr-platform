from __future__ import annotations

import hashlib
import sqlite3
from datetime import datetime, timezone
from uuid import UUID, uuid4

from app.normalization.doi import normalize_doi_strict
from app.services.import_identity import (
    fingerprint_publication,
    source_occurrence_id,
)

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
    SqliteImportSourceRecordRepository,
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


def _doi_evidence(publication: Publication) -> tuple[str | None, str | None, str]:
    """Return (valid normalized DOI, original DOI text, DOI status)."""

    original: str | None = None
    valid: str | None = None
    for identifier in publication.identifiers:
        if identifier.type is IdentifierType.DOI:
            original = identifier.value.strip()
            valid = normalize_doi_strict(original)
            if valid is None:
                return None, original, "invalid"
        elif identifier.type is IdentifierType.OTHER and identifier.source == "invalid_doi":
            original = original or identifier.value.strip()
    if valid is None and original is None:
        return None, None, "missing"
    return valid, original, "valid" if valid else "invalid"


def _source_label(publication: Publication) -> str:
    return publication.provenance[0].source if publication.provenance else ""


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
        if source_record_repository is not None:
            self._source_repo = source_record_repository
        else:
            database_path = (
                getattr(self._pub_repo, "_database_path", None)
                or getattr(self._history_repo, "_database_path", None)
                or getattr(self._tx_manager, "_database_path", None)
            )
            if database_path is not None:
                self._source_repo = SqliteImportSourceRecordRepository(database_path)
            else:
                self._source_repo = default_import_source_record_repository()

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

        self._persist_provider_source_records(
            conn,
            project_id,
            provider_name,
            import_id,
            publications,
            group_result,
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

    def _persist_provider_source_records(
        self,
        conn: sqlite3.Connection,
        project_id: str,
        provider_name: str,
        import_id: UUID,
        publications: list[Publication],
        group_result: PublicationImportResult,
    ) -> None:
        inserted_ids = (
            {str(record_id) for record_id in group_result.inserted_record_ids}
            if group_result.inserted_record_ids is not None
            else {str(publication.record_id) for publication in publications}
        )
        try:
            existing = self._pub_repo.get_publications(project_id, connection=conn)
        except TypeError:
            existing = self._pub_repo.get_publications(project_id)
        by_source_key: dict[tuple[str, str], Publication] = {}
        by_doi: dict[str, Publication] = {}
        for publication in [*existing, *[p for p in publications if str(p.record_id) in inserted_ids]]:
            if publication.provenance:
                provenance = publication.provenance[0]
                by_source_key[
                    (
                        provenance.source.strip().casefold(),
                        provenance.source_record_id.strip(),
                    )
                ] = publication
            for identifier in publication.identifiers:
                if identifier.type is IdentifierType.DOI:
                    valid_doi = normalize_doi_strict(identifier.value)
                    if valid_doi:
                        by_doi.setdefault(valid_doi, publication)
        ordinals: dict[str, int] = {}
        filename = f"provider:{provider_name}"
        for index, publication in enumerate(publications, 1):
            fingerprint = fingerprint_publication(publication)
            ordinal = ordinals.get(fingerprint, 0) + 1
            ordinals[fingerprint] = ordinal
            source_record_id = source_occurrence_id(
                project_id=project_id,
                source_label=provider_name,
                filename=filename,
                record_fingerprint=fingerprint,
                ordinal=ordinal,
            )
            existing_source = self._source_repo.find_source_record_by_id(
                project_id, source_record_id
            )
            valid_doi, original_doi, doi_status = _doi_evidence(publication)
            provenance = publication.provenance[0] if publication.provenance else None
            key = (
                provenance.source.strip().casefold(),
                provenance.source_record_id.strip(),
            ) if provenance else ("", "")
            canonical = (
                str(publication.record_id)
                if str(publication.record_id) in inserted_ids
                else str(by_doi[valid_doi].record_id)
                if valid_doi and valid_doi in by_doi
                else str(by_source_key[key].record_id)
                if key in by_source_key
                else None
            )
            if existing_source is not None:
                self._source_repo.create_skip_audit(
                    ImportSkipAuditRecord(
                        skip_audit_id=str(uuid4()),
                        project_id=project_id,
                        import_id=import_id,
                        source_record_id=source_record_id,
                        source_filename=None,
                        source_file_hash=None,
                        record_fingerprint=fingerprint,
                        import_format=f"provider:{provider_name}",
                        source_record_index=index,
                        source_title=publication.title,
                        source_doi=original_doi,
                        matched_publication_id=existing_source.canonical_publication_id,
                        match_type="repeated_occurrence",
                        match_reason="Provider source occurrence was already imported",
                        proposed_action="no_op",
                        review_required=False,
                        recovery_status="not_needed",
                    ),
                    connection=conn,
                )
                continue
            matched = canonical is None or str(publication.record_id) not in inserted_ids
            match_type = None
            match_reason = None
            if matched and valid_doi and valid_doi in by_doi:
                match_type = "exact_doi"
                match_reason = "Normalized DOI equals an existing publication"
            elif matched:
                match_type = "provider_key_duplicate"
                match_reason = "Provider source record already exists in the project"
            recovery_status = "imported" if not matched else "linked"
            self._source_repo.create_source_record(
                ImportSourceRecord(
                    source_record_id=source_record_id,
                    project_id=project_id,
                    import_id=import_id,
                    source_filename=None,
                    source_file_hash=None,
                    record_fingerprint=fingerprint,
                    import_format=f"provider:{provider_name}",
                    source_record_index=index,
                    title=publication.title,
                    publication_year=publication.publication_year,
                    original_doi=original_doi,
                    normalized_doi=valid_doi,
                    doi_status=doi_status,
                    authors=tuple(a.display_name for a in publication.authors),
                    document_type=(
                        publication.document_type.value
                        if publication.document_type
                        else None
                    ),
                    provenance=(
                        provenance.model_dump(mode="json")
                        if provenance is not None
                        else {}
                    ),
                    canonical_publication_id=canonical,
                    duplicate_match_type=match_type,
                    duplicate_match_reason=match_reason,
                    recovery_status=recovery_status,
                ),
                connection=conn,
            )
            if matched:
                self._source_repo.create_skip_audit(
                    ImportSkipAuditRecord(
                        skip_audit_id=str(uuid4()),
                        project_id=project_id,
                        import_id=import_id,
                        source_record_id=source_record_id,
                        source_filename=None,
                        source_file_hash=None,
                        record_fingerprint=fingerprint,
                        import_format=f"provider:{provider_name}",
                        source_record_index=index,
                        source_title=publication.title,
                        source_doi=original_doi,
                        matched_publication_id=canonical,
                        match_type=match_type or "provider_key_duplicate",
                        match_reason=match_reason or "Provider source key duplicate",
                        proposed_action="link_to_existing_canonical",
                        review_required=False,
                        recovery_status="not_needed",
                    ),
                    connection=conn,
                )

    def import_bibliographic_publications(
        self,
        project_id: str,
        filename: str,
        file_format: str,
        publications: list[Publication],
        source_database: ManualSourceDatabase | None = None,
        source_label: str | None = None,
        source_file_hash: str | None = None,
        record_fingerprints: list[str] | None = None,
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
                record_fingerprints,
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
                record_fingerprints,
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
        record_fingerprints: list[str] | None = None,
    ) -> tuple[PublicationImportResult, ImportHistoryRecord]:
        import_id = uuid4()
        try:
            existing_pubs = self._pub_repo.get_publications(project_id, connection=conn)
        except TypeError:
            existing_pubs = self._pub_repo.get_publications(project_id)
        existing_ids = {str(pub.record_id) for pub in existing_pubs}
        existing_by_doi: dict[str, Publication] = {}
        for pub in existing_pubs:
            for ident in pub.identifiers:
                if ident.type is IdentifierType.DOI:
                    valid_doi = normalize_doi_strict(ident.value)
                    if valid_doi:
                        existing_by_doi.setdefault(valid_doi, pub)

        fingerprints = (
            list(record_fingerprints)
            if record_fingerprints is not None
            else [fingerprint_publication(p) for p in publications]
        )
        if len(fingerprints) != len(publications):
            raise ValueError("record fingerprint count must match publication count")

        file_hash = source_file_hash
        if file_hash is None:
            fallback_payload = "|".join(
                f"{p.title.strip().casefold()}::{','.join(a.display_name for a in p.authors)}::{p.publication_year or ''}"
                for p in publications
            )
            file_hash = hashlib.sha256(
                f"{filename}|{fallback_payload}".encode("utf-8")
            ).hexdigest()

        title_counts: dict[str, int] = {}
        for pub in existing_pubs:
            key = pub.title.strip().casefold()
            title_counts[key] = title_counts.get(key, 0) + 1
        for publication in publications:
            key = publication.title.strip().casefold()
            title_counts[key] = title_counts.get(key, 0) + 1

        ordinal_by_fingerprint: dict[str, int] = {}
        prepared: list[dict] = []
        for index, publication in enumerate(publications):
            fingerprint = fingerprints[index]
            ordinal = ordinal_by_fingerprint.get(fingerprint, 0) + 1
            ordinal_by_fingerprint[fingerprint] = ordinal
            valid_doi, original_doi, doi_status = _doi_evidence(publication)
            prepared.append(
                {
                    "index": index,
                    "publication": publication,
                    "fingerprint": fingerprint,
                    "source_record_id": source_occurrence_id(
                        project_id=project_id,
                        source_label=_source_label(publication),
                        filename=filename,
                        record_fingerprint=fingerprint,
                        ordinal=ordinal,
                    ),
                    "valid_doi": valid_doi,
                    "original_doi": original_doi,
                    "doi_status": doi_status,
                    "source_label": _source_label(publication),
                }
            )

        new_publications: list[Publication] = []
        planned: list[dict] = []
        skip_audits: list[ImportSkipAuditRecord] = []
        repeated_count = 0
        doi_duplicate_count = 0
        skipped_count = 0
        invalid_doi_count = 0
        seen_doi: dict[str, str] = {}

        for item in prepared:
            publication: Publication = item["publication"]
            index: int = item["index"]
            source_record_id: str = item["source_record_id"]
            valid_doi: str | None = item["valid_doi"]
            original_doi: str | None = item["original_doi"]
            doi_status: str = item["doi_status"]
            if doi_status == "invalid":
                invalid_doi_count += 1

            existing_source = self._source_repo.find_source_record_by_id(
                project_id, source_record_id
            )
            if existing_source is not None:
                repeated_count += 1
                skipped_count += 1
                skip_audits.append(
                    ImportSkipAuditRecord(
                        skip_audit_id=str(uuid4()),
                        project_id=project_id,
                        import_id=import_id,
                        source_record_id=source_record_id,
                        source_filename=filename,
                        source_file_hash=file_hash,
                        record_fingerprint=item["fingerprint"],
                        import_format=file_format,
                        source_record_index=index + 1,
                        source_title=publication.title,
                        source_doi=original_doi,
                        matched_publication_id=existing_source.canonical_publication_id,
                        match_type="repeated_occurrence",
                        match_reason=(
                            "Source occurrence was already imported; content fingerprint "
                            "and file identity are unchanged"
                        ),
                        proposed_action="no_op",
                        review_required=False,
                        recovery_status="not_needed",
                    )
                )
                continue

            matched_existing = (
                existing_by_doi.get(valid_doi) if valid_doi is not None else None
            )
            if matched_existing is not None:
                canonical_id = str(matched_existing.record_id)
                doi_duplicate_count += 1
                skipped_count += 1
                planned.append(
                    {
                        **item,
                        "canonical_id": canonical_id,
                        "status": "linked_exact_doi",
                        "match_type": "exact_doi",
                        "match_reason": "Normalized DOI equals an existing publication",
                        "review_required": False,
                    }
                )
                skip_audits.append(
                    ImportSkipAuditRecord(
                        skip_audit_id=str(uuid4()),
                        project_id=project_id,
                        import_id=import_id,
                        source_record_id=source_record_id,
                        source_filename=filename,
                        source_file_hash=file_hash,
                        record_fingerprint=item["fingerprint"],
                        import_format=file_format,
                        source_record_index=index + 1,
                        source_title=publication.title,
                        source_doi=original_doi,
                        matched_publication_id=canonical_id,
                        match_type="exact_doi",
                        match_reason="Normalized DOI equals an existing publication",
                        proposed_action="link_to_existing_canonical",
                        review_required=False,
                        recovery_status="not_needed",
                    )
                )
                continue

            if valid_doi is not None and valid_doi in seen_doi:
                canonical_id = seen_doi[valid_doi]
                doi_duplicate_count += 1
                skipped_count += 1
                planned.append(
                    {
                        **item,
                        "canonical_id": canonical_id,
                        "status": "linked_exact_doi",
                        "match_type": "exact_doi",
                        "match_reason": (
                            "Normalized DOI repeats an earlier record in the same import"
                        ),
                        "review_required": False,
                    }
                )
                skip_audits.append(
                    ImportSkipAuditRecord(
                        skip_audit_id=str(uuid4()),
                        project_id=project_id,
                        import_id=import_id,
                        source_record_id=source_record_id,
                        source_filename=filename,
                        source_file_hash=file_hash,
                        record_fingerprint=item["fingerprint"],
                        import_format=file_format,
                        source_record_index=index + 1,
                        source_title=publication.title,
                        source_doi=original_doi,
                        matched_publication_id=canonical_id,
                        match_type="exact_doi",
                        match_reason=(
                            "Normalized DOI repeats an earlier record in the same import"
                        ),
                        proposed_action="link_to_existing_canonical",
                        review_required=False,
                        recovery_status="not_needed",
                    )
                )
                continue

            if valid_doi is not None:
                seen_doi[valid_doi] = str(publication.record_id)
            title_match = title_counts.get(publication.title.strip().casefold(), 0) > 1
            is_title_candidate = valid_doi is None and title_match
            new_publications.append(publication)
            planned.append(
                {
                    **item,
                    "canonical_id": str(publication.record_id),
                    "status": "pending_insert",
                    "match_type": (
                        "title_candidate"
                        if is_title_candidate
                        else "invalid_doi"
                        if doi_status == "invalid"
                        else None
                    ),
                    "match_reason": (
                        "Same normalized title without a valid DOI requires manual review"
                        if is_title_candidate
                        else "DOI value is not syntactically valid; record preserved for manual review"
                        if doi_status == "invalid"
                        else None
                    ),
                    "review_required": bool(is_title_candidate or doi_status == "invalid"),
                    "title_candidate": is_title_candidate,
                }
            )

        try:
            if isinstance(self._pub_repo, SqliteProjectPublicationRepository):
                import_result = self._pub_repo.import_source_publications(
                    project_id,
                    new_publications,
                    import_id=import_id,
                    connection=conn,
                    preserve_source_occurrences=True,
                )
            else:
                import_result = self._pub_repo.import_source_publications(
                    project_id,
                    new_publications,
                    import_id=import_id,
                    preserve_source_occurrences=True,
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

        inserted_ids = (
            {str(record_id) for record_id in import_result.inserted_record_ids}
            if import_result.inserted_record_ids is not None
            else {str(publication.record_id) for publication in new_publications}
        )
        known_canonical_ids = existing_ids | inserted_ids
        title_candidate_count = 0
        actual_imported_count = 0

        for item in planned:
            publication = item["publication"]
            canonical_id = item["canonical_id"]
            status = item["status"]
            match_type = item["match_type"]
            match_reason = item["match_reason"]
            recovery_status = "linked" if status == "linked_exact_doi" else "imported"
            if status == "pending_insert" and canonical_id not in inserted_ids:
                # The repository declined an insert despite the service's plan.
                # Never claim success: persist an explicit auditable skip.
                skipped_count += 1
                canonical_id = ""
                status = "skipped_repository"
                recovery_status = "skipped_repository"
                match_type = "repository_skipped"
                match_reason = "Canonical repository declined the planned insert"
                skip_audits.append(
                    ImportSkipAuditRecord(
                        skip_audit_id=str(uuid4()),
                        project_id=project_id,
                        import_id=import_id,
                        source_record_id=item["source_record_id"],
                        source_filename=filename,
                        source_file_hash=file_hash,
                        record_fingerprint=item["fingerprint"],
                        import_format=file_format,
                        source_record_index=item["index"] + 1,
                        source_title=publication.title,
                        source_doi=item["original_doi"],
                        matched_publication_id=None,
                        match_type="repository_skipped",
                        match_reason=match_reason,
                        proposed_action="manual_review",
                        review_required=True,
                        recovery_status="pending_review",
                    )
                )
            if canonical_id and canonical_id not in known_canonical_ids:
                canonical_id = ""
                status = "skipped_repository"
                recovery_status = "skipped_repository"
                match_type = "repository_skipped"
                match_reason = "Canonical publication reference could not be verified"
                skip_audits.append(
                    ImportSkipAuditRecord(
                        skip_audit_id=str(uuid4()),
                        project_id=project_id,
                        import_id=import_id,
                        source_record_id=item["source_record_id"],
                        source_filename=filename,
                        source_file_hash=file_hash,
                        record_fingerprint=item["fingerprint"],
                        import_format=file_format,
                        source_record_index=item["index"] + 1,
                        source_title=publication.title,
                        source_doi=item["original_doi"],
                        matched_publication_id=None,
                        match_type="repository_skipped",
                        match_reason=match_reason,
                        proposed_action="manual_review",
                        review_required=True,
                        recovery_status="pending_review",
                    )
                )
            if status == "pending_insert":
                status = "imported"
            if status == "imported":
                actual_imported_count += 1
                if item.get("title_candidate"):
                    title_candidate_count += 1
            self._source_repo.create_source_record(
                ImportSourceRecord(
                    source_record_id=item["source_record_id"],
                    project_id=project_id,
                    import_id=import_id,
                    source_filename=filename,
                    source_file_hash=file_hash,
                    record_fingerprint=item["fingerprint"],
                    import_format=file_format,
                    source_record_index=item["index"] + 1,
                    title=publication.title,
                    publication_year=publication.publication_year,
                    original_doi=item["original_doi"],
                    normalized_doi=item["valid_doi"],
                    doi_status=item["doi_status"],
                    authors=tuple(a.display_name for a in publication.authors),
                    document_type=(
                        publication.document_type.value
                        if publication.document_type
                        else None
                    ),
                    provenance=(
                        publication.provenance[0].model_dump(mode="json")
                        if publication.provenance
                        else {}
                    ),
                    canonical_publication_id=canonical_id or None,
                    duplicate_match_type=match_type,
                    duplicate_match_reason=match_reason,
                    recovery_status=recovery_status,
                ),
                connection=conn,
            )

        for skip_record in skip_audits:
            self._source_repo.create_skip_audit(skip_record, connection=conn)

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
        if invalid_doi_count:
            warnings.append(
                f"Preserved {invalid_doi_count} record(s) with invalid DOI metadata for manual review."
            )
        if any(r.match_type == "repository_skipped" for r in skip_audits):
            warnings.append(
                "One or more canonical insertions were declined by the repository and require review."
            )

        history_record = ImportHistoryRecord(
            import_id=import_id,
            project_id=project_id,
            source_type="file",
            filename=filename,
            format=file_format,
            provider=None,
            query=None,
            records_count=actual_imported_count,
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
            imported_count=actual_imported_count,
            skipped_count=skipped_count + import_result.skipped_count,
            working_collection_count=import_result.working_collection_count,
            inserted_record_ids=tuple(
                publication.record_id
                for item in planned
                if item["status"] == "imported"
                for publication in [item["publication"]]
            ),
        )

        if import_result.imported_count > 0:
            if isinstance(self._norm_repo, SqliteNormalizationExecutionRepository):
                self._norm_repo.delete_for_project(project_id, connection=conn)
            else:
                self._norm_repo.delete_for_project(project_id)

        return import_result, history_record


default_project_import_service = ProjectImportService()
