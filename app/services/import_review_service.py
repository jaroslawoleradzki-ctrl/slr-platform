from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from app.domain.import_review import (
    ImportReviewDecision,
    ImportReviewDecisionType,
    effective_import_status,
)
from app.repositories.duplicate_merge_repository import (
    DuplicateMergeRepository,
    InMemoryDuplicateMergeRepository,
    default_duplicate_merge_repository,
)
from app.repositories.duplicate_review_decision_repository import (
    DuplicateReviewDecisionRepository,
    default_duplicate_review_decision_repository,
)
from app.repositories.import_history_repository import (
    ImportHistoryRecord,
    ImportHistoryRepository,
    default_import_history_repository,
)
from app.repositories.import_review_repository import (
    ImportReviewConflictError,
    ImportReviewRepository,
    default_import_review_repository,
)
from app.repositories.import_source_record_repository import (
    ImportSourceRecordRepository,
    default_import_source_record_repository,
)
from app.repositories.normalization_execution_repository import (
    NormalizationExecutionRepository,
    default_normalization_execution_repository,
)
from app.repositories.project_publication_repository import (
    ProjectPublicationRepository,
    default_project_publication_repository,
)
from app.repositories.transaction_manager import (
    SqliteTransactionManager,
    default_transaction_manager,
)
from app.services.duplicate_group_builder import DuplicateGroupBuilder
from app.services.project_duplicate_service import ProjectDuplicateService


class ImportNotFoundError(LookupError):
    """Raised when an import does not exist in the requested project."""


class ImportReviewStateError(ValueError):
    """Raised when an import cannot enter a review decision."""


class ImportRejectionConfirmationRequired(ValueError):
    """Raised when a rejection is not explicitly confirmed."""


@dataclass(frozen=True, slots=True)
class ImportReviewBlocker:
    code: str
    message: str
    count: int
    publication_ids: tuple[str, ...] = ()


class ImportRejectionBlockedError(RuntimeError):
    def __init__(self, blockers: tuple[ImportReviewBlocker, ...]) -> None:
        self.blockers = blockers
        super().__init__("Import rejection is blocked by dependent research state.")


@dataclass(frozen=True, slots=True)
class ImportWarningCategory:
    code: str
    label: str
    count: int


@dataclass(frozen=True, slots=True)
class ImportReviewDetail:
    record: ImportHistoryRecord
    decision: ImportReviewDecision | None
    effective_status: str
    review_status: str
    can_accept: bool
    can_reject: bool
    blockers: tuple[ImportReviewBlocker, ...]
    warning_categories: tuple[ImportWarningCategory, ...]
    source_record_count: int
    canonical_publication_count: int
    exact_doi_match_count: int
    repeated_source_count: int
    title_candidate_count: int
    similar_title_candidate_count: int
    skipped_canonical_count: int
    invalid_doi_count: int
    validation_error_count: int
    audit_available: bool


class ImportReviewService:
    def __init__(
        self,
        publication_repository: ProjectPublicationRepository | None = None,
        import_history_repository: ImportHistoryRepository | None = None,
        source_record_repository: ImportSourceRecordRepository | None = None,
        review_repository: ImportReviewRepository | None = None,
        duplicate_decision_repository: DuplicateReviewDecisionRepository | None = None,
        merge_repository: DuplicateMergeRepository | None = None,
        normalization_repository: NormalizationExecutionRepository | None = None,
        transaction_manager: SqliteTransactionManager | None = None,
        builder: DuplicateGroupBuilder | None = None,
    ) -> None:
        self._publications = publication_repository or default_project_publication_repository()
        self._history = import_history_repository or default_import_history_repository()
        self._source_records = (
            source_record_repository or default_import_source_record_repository()
        )
        self._reviews = review_repository or default_import_review_repository()
        self._duplicate_decisions = (
            duplicate_decision_repository or default_duplicate_review_decision_repository()
        )
        database_path = getattr(self._publications, "_database_path", None)
        self._merge_repository = merge_repository or (
            default_duplicate_merge_repository()
            if database_path is not None
            else InMemoryDuplicateMergeRepository()
        )
        self._normalization = normalization_repository or default_normalization_execution_repository()
        self._transaction_manager = transaction_manager or (
            SqliteTransactionManager(database_path)
            if database_path is not None
            else default_transaction_manager()
        )
        self._builder = builder or DuplicateGroupBuilder()
        self._database_path = Path(database_path) if database_path is not None else None
        self._duplicate_projection = (
            ProjectDuplicateService(
                repository=self._publications,
                transaction_manager=self._transaction_manager,
                source_record_repository=self._source_records,
            )
            if database_path is not None
            else None
        )

    def get_review(self, project_id: str, import_id: UUID) -> ImportReviewDetail:
        record = self._history.get(project_id, import_id)
        if record is None:
            raise ImportNotFoundError(import_id)
        decision = self._reviews.get(project_id, import_id)
        source_records = self._source_records.list_source_records_for_import(project_id, import_id)
        skip_records = self._source_records.list_skip_audit_for_import(project_id, import_id)
        blockers = self._blockers(project_id, import_id, record, source_records, skip_records)
        return self._detail(record, decision, source_records, skip_records, blockers)

    def accept(
        self,
        project_id: str,
        import_id: UUID,
        *,
        reviewer_id: str,
        rationale: str | None = None,
    ) -> ImportReviewDecision:
        reviewer = self._validate_reviewer(reviewer_id)
        with self._transaction_manager.transaction() as connection:
            record = self._history.get(project_id, import_id, connection=connection)
            if record is None:
                raise ImportNotFoundError(import_id)
            existing = self._reviews.get(project_id, import_id, connection=connection)
            if existing is not None:
                if existing.decision == ImportReviewDecisionType.ACCEPTED.value:
                    return existing
                raise ImportReviewConflictError(
                    f"Import '{import_id}' already has decision '{existing.decision}'."
                )
            self._require_warning_import(record)
            source_records = self._source_records.list_source_records_for_import(
                project_id, import_id
            )
            owned_ids = self._publications.get_publication_ids_for_import(
                project_id, import_id, connection=connection
            )
            decision = ImportReviewDecision(
                project_id=project_id,
                import_id=import_id,
                decision=ImportReviewDecisionType.ACCEPTED.value,
                reviewer_id=reviewer,
                rationale=self._clean_rationale(rationale),
                decided_at=datetime.now(timezone.utc),
                import_status_at_decision=record.status,
                warning_snapshot=record.warnings,
                affected_source_record_ids=tuple(
                    item.source_record_id for item in source_records
                ),
                affected_publication_ids=tuple(sorted(str(value) for value in owned_ids)),
                deleted_publication_count=0,
                retained_source_record_count=len(source_records),
                prisma_treatment="not_applicable",
            )
            return self._reviews.create(decision, connection=connection)

    def reject(
        self,
        project_id: str,
        import_id: UUID,
        *,
        reviewer_id: str,
        rationale: str | None = None,
        confirm_rejection: bool = False,
    ) -> ImportReviewDecision:
        if not confirm_rejection:
            raise ImportRejectionConfirmationRequired(
                "Rejection requires explicit confirmation."
            )
        reviewer = self._validate_reviewer(reviewer_id)
        with self._transaction_manager.transaction() as connection:
            record = self._history.get(project_id, import_id, connection=connection)
            if record is None:
                raise ImportNotFoundError(import_id)
            existing = self._reviews.get(project_id, import_id, connection=connection)
            if existing is not None:
                if existing.decision == ImportReviewDecisionType.REJECTED.value:
                    return existing
                raise ImportReviewConflictError(
                    f"Import '{import_id}' already has decision '{existing.decision}'."
                )
            self._require_warning_import(record)
            source_records = self._source_records.list_source_records_for_import(
                project_id, import_id
            )
            skip_records = self._source_records.list_skip_audit_for_import(
                project_id, import_id
            )
            owned_ids = self._publications.get_publication_ids_for_import(
                project_id, import_id, connection=connection
            )
            blockers = self._blockers(
                project_id,
                import_id,
                record,
                source_records,
                skip_records,
                owned_ids=owned_ids,
                connection=connection,
            )
            if blockers:
                raise ImportRejectionBlockedError(tuple(blockers))

            publications = self._publications.get_publications_by_ids(
                project_id, sorted(owned_ids), connection=connection
            )
            snapshots = tuple(
                publication.model_dump(mode="json") for publication in publications
            )
            decision = ImportReviewDecision(
                project_id=project_id,
                import_id=import_id,
                decision=ImportReviewDecisionType.REJECTED.value,
                reviewer_id=reviewer,
                rationale=self._clean_rationale(rationale),
                decided_at=datetime.now(timezone.utc),
                import_status_at_decision=record.status,
                warning_snapshot=record.warnings,
                affected_source_record_ids=tuple(
                    item.source_record_id for item in source_records
                ),
                affected_publication_ids=tuple(
                    sorted(str(value) for value in owned_ids)
                ),
                removed_publication_snapshots=snapshots,
                deleted_publication_count=len(publications),
                retained_source_record_count=len(source_records),
                prisma_treatment="removed_before_screening_rejected_import",
            )
            self._reviews.create(decision, connection=connection)
            if owned_ids:
                self._publications.delete_publications(
                    project_id, sorted(owned_ids), connection=connection
                )
                self._normalization.delete_for_project(
                    project_id, connection=connection
                )
                if self._duplicate_projection is not None:
                    self._duplicate_projection.materialize_candidate_group_projection(
                        project_id, connection=connection
                    )
            return decision

    def _detail(
        self,
        record: ImportHistoryRecord,
        decision: ImportReviewDecision | None,
        source_records,
        skip_records,
        blockers: tuple[ImportReviewBlocker, ...],
    ) -> ImportReviewDetail:
        repeated = sum(
            1 for item in skip_records if item.match_type == "repeated_occurrence"
        )
        exact = sum(1 for item in skip_records if item.match_type == "exact_doi")
        title = sum(
            1
            for item in source_records
            if item.duplicate_match_type
            in {"title_candidate", "identical_title", "conflicting_identifiers"}
        )
        similar = sum(
            1 for item in source_records if item.duplicate_match_type == "similar_title"
        )
        invalid = sum(1 for item in source_records if getattr(item, "doi_status", "missing") == "invalid")
        categories = tuple(
            category
            for category in (
                ImportWarningCategory("exact_doi", "Dokładne duplikaty DOI", exact),
                ImportWarningCategory("repeated_occurrence", "Powtórzone wystąpienia", repeated),
                ImportWarningCategory("title_candidate", "Kandydaci tytułowi", title + similar),
                ImportWarningCategory("invalid_doi", "Niepoprawne DOI", invalid),
                ImportWarningCategory(
                    "skipped_canonical", "Pominięte wstawienia kanoniczne", len(skip_records)
                ),
                ImportWarningCategory(
                    "validation_error",
                    "Błędy walidacji",
                    1 if record.status == "failed" else 0,
                ),
            )
            if category.count > 0
        )
        review_status = (
            decision.decision
            if decision is not None
            else ("not_required" if record.status == "success" else "pending")
        )
        can_accept = record.status == "warning" and decision is None
        can_reject = can_accept and not blockers
        return ImportReviewDetail(
            record=record,
            decision=decision,
            effective_status=effective_import_status(
                record.status, decision.decision if decision else None
            ),
            review_status=review_status,
            can_accept=can_accept,
            can_reject=can_reject,
            blockers=blockers,
            warning_categories=categories,
            source_record_count=len(source_records) + repeated,
            canonical_publication_count=record.records_count,
            exact_doi_match_count=exact,
            repeated_source_count=repeated,
            title_candidate_count=title,
            similar_title_candidate_count=similar,
            skipped_canonical_count=len(skip_records),
            invalid_doi_count=invalid,
            validation_error_count=1 if record.status == "failed" else 0,
            audit_available=bool(source_records or skip_records),
        )

    def _blockers(
        self,
        project_id: str,
        import_id: UUID,
        record: ImportHistoryRecord,
        source_records,
        skip_records,
        *,
        owned_ids: set[UUID] | None = None,
        connection: sqlite3.Connection | None = None,
    ) -> tuple[ImportReviewBlocker, ...]:
        if owned_ids is None:
            owned_ids = self._publications.get_publication_ids_for_import(
                project_id, import_id, connection=connection
            )
        target_ids = sorted(str(value) for value in owned_ids)
        blockers: list[ImportReviewBlocker] = []

        if not owned_ids and not source_records and record.records_count > 0:
            blockers.append(
                ImportReviewBlocker(
                    code="unverifiable_ownership",
                    message="Import has no authoritative publication ownership evidence.",
                    count=record.records_count,
                )
            )

        if not target_ids:
            return tuple(blockers)

        target_set = set(target_ids)
        all_source_records = self._source_records.list_source_records(project_id)
        shared = {
            item.canonical_publication_id
            for item in all_source_records
            if item.import_id != import_id
            and item.canonical_publication_id in target_set
        }
        if shared:
            blockers.append(
                ImportReviewBlocker(
                    code="shared_publication",
                    message="Publication(s) are also referenced by another import.",
                    count=len(shared),
                    publication_ids=tuple(sorted(shared)),
                )
            )

        source_ids = {item.source_record_id for item in source_records}
        if source_ids:
            placeholders = ",".join("?" for _ in source_ids)
            params = [project_id, *sorted(source_ids)]
            def recovery_query(conn: sqlite3.Connection) -> set[str]:
                if connection is None and self._database_path is None:
                    return set()
                rows = conn.execute(
                    f"SELECT DISTINCT source_record_id FROM import_recovery_approvals WHERE project_id = ? AND source_record_id IN ({placeholders})",
                    params,
                ).fetchall()
                return {str(row[0]) for row in rows}
            if connection is not None:
                recovered_sources = recovery_query(connection)
            else:
                with self._read_connection() as conn:
                    recovered_sources = recovery_query(conn)
            if recovered_sources:
                blockers.append(
                    ImportReviewBlocker(
                        code="recovery_approval",
                        message="Import source records have an approved recovery decision.",
                        count=len(recovered_sources),
                    )
                )

        merged_ids, superseded_ids = self._merge_blockers(
            project_id, target_set, connection=connection
        )
        merged_ids.update(superseded_ids)
        if merged_ids:
            blockers.append(
                ImportReviewBlocker(
                    code="merged_publication",
                    message="Publication(s) belong to a duplicate merge or supersession chain.",
                    count=len(merged_ids),
                    publication_ids=tuple(sorted(merged_ids)),
                )
            )

        decided_ids = self._duplicate_decision_blockers(
            project_id, target_set, connection=connection
        )
        if decided_ids:
            blockers.append(
                ImportReviewBlocker(
                    code="duplicate_decision",
                    message="Publication(s) belong to a duplicate group with a reviewer decision.",
                    count=len(decided_ids),
                    publication_ids=tuple(sorted(decided_ids)),
                )
            )

        for code, message, table, column in (
            ("pre_screening_decision", "Publication(s) have a pre-screening decision.", "pre_screening_decisions", "record_id"),
            ("pre_screening_decision", "Publication(s) have a pre-screening archive entry.", "pre_screening_archive", "record_id"),
            ("screening_decision", "Publication(s) have a screening decision.", "screening_decisions", "publication_id"),
            ("full_text_metadata", "Publication(s) have full-text availability metadata.", "full_text_availability", "publication_id"),
            ("quality_assessment", "Publication(s) have a quality assessment.", "quality_assessments", "publication_id"),
            ("extraction", "Publication(s) have extraction records.", "extraction_records", "publication_id"),
            ("synthesis", "Publication(s) are referenced by synthesis records.", "synthesis_analytical_relations", "publication_id"),
            ("synthesis", "Publication(s) are referenced by synthesis context records.", "synthesis_relation_context_links", "publication_id"),
            ("synthesis", "Publication(s) are referenced by synthesis mechanism records.", "synthesis_mechanism_pathways", "publication_id"),
            ("synthesis", "Publication(s) are referenced by synthesis gap records.", "synthesis_research_gap_links", "publication_id"),
        ):
            found = self._query_publication_ids(
                table, column, project_id, target_set, connection=connection
            )
            if found:
                blockers.append(
                    ImportReviewBlocker(
                        code=code,
                        message=message,
                        count=len(found),
                        publication_ids=tuple(sorted(found)),
                    )
                )

        finalized = self._finalization_blockers(
            project_id, target_set, connection=connection
        )
        if finalized:
            blockers.append(
                ImportReviewBlocker(
                    code="corpus_finalized",
                    message="Publication(s) belong to a corpus finalization.",
                    count=len(finalized),
                    publication_ids=tuple(sorted(finalized)),
                )
            )

        return tuple(blockers)

    def _merge_blockers(
        self,
        project_id: str,
        target_ids: set[str],
        *,
        connection: sqlite3.Connection | None,
    ) -> tuple[set[str], set[str]]:
        merged: set[str] = set()
        superseded: set[str] = set()

        def read(conn: sqlite3.Connection) -> None:
            rows = conn.execute(
                "SELECT canonical_record_id, merged_publication_ids FROM duplicate_group_merges WHERE project_id = ?",
                (project_id,),
            ).fetchall()
            for row in rows:
                members = {str(value) for value in json.loads(str(row[1]))}
                canonical = str(row[0])
                if members & target_ids or canonical in target_ids:
                    merged.update(target_ids & (members | {canonical}))
            for row in conn.execute(
                "SELECT record_id, superseded_by FROM project_publications WHERE project_id = ?",
                (project_id,),
            ).fetchall():
                record_id = str(row[0])
                superseded_by = str(row[1]) if row[1] is not None else None
                if record_id in target_ids and superseded_by is not None:
                    superseded.add(record_id)
                if superseded_by in target_ids:
                    superseded.add(superseded_by)

        if connection is not None:
            read(connection)
        else:
            with self._read_connection() as conn:
                read(conn)
        return merged, superseded

    def _duplicate_decision_blockers(
        self,
        project_id: str,
        target_ids: set[str],
        *,
        connection: sqlite3.Connection | None,
    ) -> set[str]:
        decisions = self._duplicate_decisions.list_decisions_for_project(
            project_id, connection=connection
        )
        if not decisions:
            return set()
        publications = self._publications.get_all_publications(
            project_id, connection=connection
        )
        decided: set[str] = set()
        for group in self._builder.build(publications, include_title_candidates=True):
            group_id = str(group.group_id)
            if group_id not in decisions:
                continue
            members = {str(value) for value in group.publication_ids}
            decided.update(members & target_ids)
        def snapshots(conn: sqlite3.Connection) -> set[str]:
            found: set[str] = set(decided)
            rows = conn.execute(
                "SELECT publication_ids_json, group_id FROM duplicate_candidate_group_snapshots WHERE project_id = ?",
                (project_id,),
            ).fetchall()
            for row in rows:
                if str(row[1]) not in decisions:
                    continue
                members = {str(value) for value in json.loads(str(row[0]))}
                found.update(members & target_ids)
            return found

        if connection is not None:
            return snapshots(connection)
        with self._read_connection() as conn:
            return snapshots(conn)

    def _query_publication_ids(
        self,
        table: str,
        column: str,
        project_id: str,
        target_ids: set[str],
        *,
        connection: sqlite3.Connection | None,
    ) -> set[str]:
        placeholders = ",".join("?" for _ in target_ids)
        params = [project_id, *sorted(target_ids)]

        def query(conn: sqlite3.Connection) -> set[str]:
            rows = conn.execute(
                f"SELECT DISTINCT {column} FROM {table} WHERE project_id = ? AND {column} IN ({placeholders})",
                params,
            ).fetchall()
            return {str(row[0]) for row in rows if row[0] is not None}

        if connection is not None:
            return query(connection)
        with self._read_connection() as conn:
            return query(conn)

    def _finalization_blockers(
        self,
        project_id: str,
        target_ids: set[str],
        *,
        connection: sqlite3.Connection | None,
    ) -> set[str]:
        placeholders = ",".join("?" for _ in target_ids)
        params = [project_id, *sorted(target_ids)]

        def query(conn: sqlite3.Connection) -> set[str]:
            rows = conn.execute(
                f"""
                SELECT DISTINCT m.record_id
                FROM corpus_finalization_members m
                JOIN corpus_finalizations f ON f.finalization_id = m.finalization_id
                WHERE f.project_id = ? AND m.record_id IN ({placeholders})
                """,
                params,
            ).fetchall()
            return {str(row[0]) for row in rows}

        if connection is not None:
            return query(connection)
        with self._read_connection() as conn:
            return query(conn)

    def _read_connection(self) -> sqlite3.Connection:
        if self._database_path is None:
            raise ImportReviewStateError("Import review requires durable SQLite storage.")
        return sqlite3.connect(self._database_path)

    @staticmethod
    def _validate_reviewer(reviewer_id: str) -> str:
        reviewer = reviewer_id.strip()
        if not reviewer:
            raise ValueError("reviewer_id must not be blank.")
        return reviewer

    @staticmethod
    def _clean_rationale(rationale: str | None) -> str | None:
        if rationale is None:
            return None
        cleaned = rationale.strip()
        return cleaned or None

    @staticmethod
    def _require_warning_import(record: ImportHistoryRecord) -> None:
        if record.status != "warning":
            raise ImportReviewStateError(
                "Only warning imports can receive an accept or reject decision."
            )


__all__ = [
    "ImportNotFoundError",
    "ImportRejectionBlockedError",
    "ImportRejectionConfirmationRequired",
    "ImportReviewBlocker",
    "ImportReviewDetail",
    "ImportReviewService",
    "ImportReviewStateError",
    "ImportWarningCategory",
]
