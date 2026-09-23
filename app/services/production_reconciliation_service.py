"""Controlled, allow-list-only physical reconciliation of legacy pre-screening removals.

This module intentionally has no production defaults.  An operator must pass a database
path, project, import and the exact UUID allow-list; dry-run is the normal first call.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

from app.domain.pre_screening import PreScreeningArchivedRecord, PreScreeningRemovalReason
from app.domain.publication import Publication
from app.repositories.pre_screening_archive_repository import SqlitePreScreeningArchiveRepository
from app.repositories.transaction_manager import SqliteTransactionManager


class ReconciliationSafetyError(RuntimeError):
    """Structured, non-destructive precondition failure."""

    def __init__(self, code: str, message: str, details: dict[str, object] | None = None) -> None:
        self.code, self.details = code, details or {}
        super().__init__(message)


@dataclass(frozen=True)
class ReconciliationRequest:
    project_id: str
    import_id: UUID
    record_ids: tuple[UUID, ...]
    expected_target_count: int
    actor: str

    def fingerprint(self) -> str:
        payload = {
            "project_id": self.project_id,
            "import_id": str(self.import_id),
            "record_ids": sorted(str(item) for item in self.record_ids),
            "expected_target_count": self.expected_target_count,
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


@dataclass(frozen=True)
class ReconciliationReport:
    mode: str
    project_id: str
    import_id: str
    candidate_target_count: int
    validated_target_count: int
    already_archived: int
    archive_required: int
    physical_rows_to_remove: int
    expected_active_corpus_after: int
    affected_normalization_state: int
    affected_deduplication_state: int
    formal_screening_conflicts: int
    finalization_conflicts: int
    unknown_references: tuple[str, ...]
    status: str
    reconciliation_id: str | None = None

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


class ProductionReconciliationService:
    """Archive-before-delete reconciliation with one SQLite IMMEDIATE transaction.

    A crash before commit rolls back both archive snapshots and removals.  A crash after
    commit is replay-safe through ``corpus_reconciliation_runs``.
    """

    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path)
        # Applies WP1 and this module's migrations; never opens a configured default DB.
        from app.repositories.project_publication_repository import SqliteProjectPublicationRepository

        SqliteProjectPublicationRepository(self.database_path)
        self._archive = SqlitePreScreeningArchiveRepository(self.database_path)
        self._transactions = SqliteTransactionManager(self.database_path)

    def dry_run(self, request: ReconciliationRequest) -> ReconciliationReport:
        with sqlite3.connect(self.database_path) as conn:
            return self._preflight(conn, request, mode="dry-run")

    def execute(self, request: ReconciliationRequest, *, backup_acknowledged: bool) -> ReconciliationReport:
        if not backup_acknowledged:
            raise ReconciliationSafetyError(
                "BACKUP_ACKNOWLEDGEMENT_REQUIRED", "A verified fresh backup must be acknowledged."
            )
        with self._transactions.transaction() as conn:
            report = self._preflight(conn, request, mode="execute")
            if report.status == "already-reconciled":
                return report
            reconciliation_id = str(uuid4())
            rows = conn.execute(
                "SELECT record_id, document, import_id FROM project_publications WHERE project_id = ? AND record_id IN (%s)"
                % ",".join("?" * len(request.record_ids)),
                (request.project_id, *(str(i) for i in request.record_ids)),
            ).fetchall()
            for record_id, document, import_id in rows:
                publication = Publication.model_validate(json.loads(document))
                existing = self._archive.get_archived_record(request.project_id, UUID(record_id), connection=conn)
                if existing is None:
                    # Legacy installations may have only the status column.  Where the
                    # WP1 decision exists, preserve its reason, notes and reviewer in
                    # the durable snapshot instead of inventing a second decision.
                    decision = conn.execute(
                        """SELECT reason, notes, reviewer_id, decided_at
                           FROM pre_screening_decisions
                           WHERE project_id = ? AND record_id = ? AND status = 'removed'
                           ORDER BY decided_at DESC, created_at DESC LIMIT 1""",
                        (request.project_id, record_id),
                    ).fetchone()
                    reason = PreScreeningRemovalReason.RETRIEVAL_ARTEFACT
                    notes = None
                    removed_by = request.actor
                    removed_at = datetime.now(timezone.utc)
                    if decision is not None:
                        if decision[0] in {item.value for item in PreScreeningRemovalReason}:
                            reason = PreScreeningRemovalReason(decision[0])
                        notes = decision[1]
                        removed_by = decision[2] or request.actor
                        if decision[3]:
                            removed_at = datetime.fromisoformat(decision[3])
                    snapshot = PreScreeningArchivedRecord.from_publication(
                        publication,
                        request.project_id,
                        import_id=UUID(import_id),
                        removal_reason=reason,
                        removal_notes=notes,
                        removed_by=removed_by,
                        removed_at=removed_at,
                    )
                    self._archive.archive_record(snapshot, connection=conn)
                    existing = self._archive.get_archived_record(request.project_id, UUID(record_id), connection=conn)
                if existing is None or existing.document != publication.model_dump(mode="json"):
                    raise ReconciliationSafetyError(
                        "ARCHIVE_VERIFICATION_FAILED",
                        "Archive snapshot is missing or incomplete.",
                        {"record_id": record_id},
                    )
            # Derived canonical markers were created over the wrong corpus; clear only this
            # rebuildable marker, and record the mandatory WP2 rebuild contract in the ledger.
            conn.execute(
                "UPDATE project_publications SET superseded_by = NULL WHERE project_id = ?", (request.project_id,)
            )
            deleted = conn.execute(
                "DELETE FROM project_publications WHERE project_id = ? AND record_id IN (%s)"
                % ",".join("?" * len(request.record_ids)),
                (request.project_id, *(str(i) for i in request.record_ids)),
            ).rowcount
            if deleted != len(request.record_ids):
                raise ReconciliationSafetyError(
                    "DELETE_COUNT_MISMATCH", "Validated allow-list was not deleted exactly."
                )
            active_after = conn.execute(
                "SELECT COUNT(*) FROM project_publications WHERE project_id = ? AND (pre_screening_status IS NULL OR pre_screening_status = 'retained')",
                (request.project_id,),
            ).fetchone()[0]
            conn.execute(
                "INSERT INTO corpus_reconciliation_runs (reconciliation_id, request_fingerprint, project_id, import_id, target_ids, status, removed_count, active_count_after, actor) VALUES (?, ?, ?, ?, ?, 'complete', ?, ?, ?)",
                (
                    reconciliation_id,
                    request.fingerprint(),
                    request.project_id,
                    str(request.import_id),
                    json.dumps(sorted(str(i) for i in request.record_ids)),
                    deleted,
                    active_after,
                    request.actor,
                ),
            )
            return ReconciliationReport(
                **{
                    **report.as_dict(),
                    "mode": "execute",
                    "physical_rows_to_remove": deleted,
                    "expected_active_corpus_after": active_after,
                    "status": "complete",
                    "reconciliation_id": reconciliation_id,
                }
            )

    def _preflight(
        self, conn: sqlite3.Connection, request: ReconciliationRequest, *, mode: str
    ) -> ReconciliationReport:
        if (
            not request.record_ids
            or len(set(request.record_ids)) != len(request.record_ids)
            or request.expected_target_count != len(request.record_ids)
        ):
            raise ReconciliationSafetyError(
                "INVALID_ALLOW_LIST", "Allow-list must be non-empty, unique and exactly match expected_target_count."
            )
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise ReconciliationSafetyError(
                "DATABASE_INTEGRITY_FAILED", "SQLite integrity_check failed.", {"result": integrity}
            )
        if conn.execute("SELECT 1 FROM projects WHERE project_id = ?", (request.project_id,)).fetchone() is None:
            raise ReconciliationSafetyError("PROJECT_NOT_FOUND", "Target project does not exist.")
        completed = conn.execute(
            "SELECT reconciliation_id, active_count_after FROM corpus_reconciliation_runs WHERE request_fingerprint = ?",
            (request.fingerprint(),),
        ).fetchone()
        if completed:
            return ReconciliationReport(
                mode,
                request.project_id,
                str(request.import_id),
                len(request.record_ids),
                len(request.record_ids),
                len(request.record_ids),
                0,
                0,
                int(completed[1]),
                0,
                0,
                0,
                0,
                (),
                "already-reconciled",
                completed[0],
            )
        placeholders = ",".join("?" * len(request.record_ids))
        rows = conn.execute(
            "SELECT record_id, import_id, pre_screening_status FROM project_publications WHERE project_id = ? AND record_id IN (%s)"
            % placeholders,
            (request.project_id, *(str(i) for i in request.record_ids)),
        ).fetchall()
        if len(rows) != len(request.record_ids):
            raise ReconciliationSafetyError(
                "TARGET_MISSING_OR_WRONG_PROJECT", "Every allow-listed record must exist in the target project."
            )
        for record_id, import_id, status in rows:
            if import_id != str(request.import_id):
                raise ReconciliationSafetyError(
                    "WRONG_IMPORT", "Allow-list record has a different or NULL import_id.", {"record_id": record_id}
                )
            if status != "removed":
                raise ReconciliationSafetyError(
                    "TARGET_NOT_PRE_SCREENING_REMOVED",
                    "Allow-list record is not legacy pre-screening removed.",
                    {"record_id": record_id},
                )
        screening = conn.execute(
            "SELECT COUNT(*) FROM screening_decisions WHERE project_id = ? AND publication_id IN (%s)" % placeholders,
            (request.project_id, *(str(i) for i in request.record_ids)),
        ).fetchone()[0]
        finalization = conn.execute(
            "SELECT COUNT(*) FROM corpus_finalization_members m JOIN corpus_finalizations f ON f.finalization_id=m.finalization_id WHERE f.project_id=? AND m.record_id IN (%s)"
            % placeholders,
            (request.project_id, *(str(i) for i in request.record_ids)),
        ).fetchone()[0]
        if screening:
            raise ReconciliationSafetyError(
                "FORMAL_SCREENING_CONFLICT", "Formal screening history blocks physical removal.", {"count": screening}
            )
        if finalization:
            raise ReconciliationSafetyError(
                "FINALIZATION_CONFLICT", "Finalized corpus membership blocks physical removal.", {"count": finalization}
            )
        unknown = self._unknown_references(conn, request.project_id, [str(i) for i in request.record_ids])
        if unknown:
            raise ReconciliationSafetyError(
                "UNKNOWN_LOGICAL_REFERENCES",
                "Logical references must be explicitly reconciled before deletion.",
                {"references": unknown},
            )
        archived = sum(
            1
            for i in request.record_ids
            if self._archive.get_archived_record(request.project_id, i, connection=conn) is not None
        )
        active_now = conn.execute(
            "SELECT COUNT(*) FROM project_publications WHERE project_id = ? AND (pre_screening_status IS NULL OR pre_screening_status='retained')",
            (request.project_id,),
        ).fetchone()[0]
        norm = conn.execute(
            "SELECT COUNT(*) FROM normalization_executions WHERE project_id = ?", (request.project_id,)
        ).fetchone()[0]
        dedup = conn.execute(
            "SELECT COUNT(*) FROM duplicate_review_decisions WHERE project_id = ?", (request.project_id,)
        ).fetchone()[0]
        return ReconciliationReport(
            mode,
            request.project_id,
            str(request.import_id),
            len(request.record_ids),
            len(rows),
            archived,
            len(rows) - archived,
            len(rows),
            active_now,
            norm,
            dedup,
            0,
            0,
            (),
            "preflight-ok",
        )

    @staticmethod
    def _unknown_references(conn: sqlite3.Connection, project_id: str, ids: list[str]) -> tuple[str, ...]:
        # Known provenance/audit tables are retained intentionally; any other physical
        # publication reference is a stop condition rather than an implicit orphan.
        allowed = {
            "project_publications",
            "pre_screening_archive",
            "pre_screening_decisions",
            "screening_decisions",
            "corpus_finalization_members",
        }
        found: list[str] = []
        for (table,) in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"):
            if table in allowed:
                continue
            columns = {row[1] for row in conn.execute(f'PRAGMA table_info("{table}")')}
            column = (
                "publication_id" if "publication_id" in columns else "record_id" if "record_id" in columns else None
            )
            if column and "project_id" in columns:
                marks = ",".join("?" * len(ids))
                if conn.execute(
                    f'SELECT 1 FROM "{table}" WHERE project_id=? AND "{column}" IN ({marks}) LIMIT 1',
                    (project_id, *ids),
                ).fetchone():
                    found.append(table)
        return tuple(sorted(found))
