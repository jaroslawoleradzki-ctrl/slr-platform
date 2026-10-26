from __future__ import annotations

import json
import os
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol, runtime_checkable
from uuid import UUID, uuid4

_SOURCE_TABLE = "import_source_records"
_SKIP_TABLE = "import_skip_audit"

_SOURCE_DDL = """
CREATE TABLE IF NOT EXISTS import_source_records (
    project_id TEXT NOT NULL,
    source_record_id TEXT NOT NULL,
    import_id TEXT NOT NULL,
    source_filename TEXT,
    source_file_hash TEXT,
    record_fingerprint TEXT,
    import_format TEXT,
    source_record_index INTEGER NOT NULL,
    title TEXT NOT NULL,
    publication_year INTEGER,
    original_doi TEXT,
    normalized_doi TEXT,
    doi_status TEXT NOT NULL DEFAULT 'missing',
    authors_json TEXT NOT NULL DEFAULT '[]' CHECK (json_valid(authors_json)),
    document_type TEXT,
    provenance_json TEXT NOT NULL CHECK (json_valid(provenance_json)),
    canonical_publication_id TEXT,
    duplicate_match_type TEXT,
    duplicate_match_reason TEXT,
    duplicate_candidate_group_id TEXT,
    recovery_status TEXT NOT NULL DEFAULT 'not_needed',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (project_id, source_record_id),
    UNIQUE (project_id, import_id, source_record_index)
)
"""

_SKIP_DDL = """
CREATE TABLE IF NOT EXISTS import_skip_audit (
    skip_audit_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    import_id TEXT NOT NULL,
    source_record_id TEXT,
    source_filename TEXT,
    source_file_hash TEXT,
    record_fingerprint TEXT,
    import_format TEXT,
    source_record_index INTEGER NOT NULL,
    source_title TEXT NOT NULL,
    source_doi TEXT,
    matched_publication_id TEXT,
    match_type TEXT NOT NULL,
    match_reason TEXT NOT NULL,
    proposed_action TEXT NOT NULL,
    review_required INTEGER NOT NULL DEFAULT 0 CHECK (review_required IN (0, 1)),
    recovery_status TEXT NOT NULL DEFAULT 'pending_review',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (project_id, import_id, source_record_index)
)
"""

_SOURCE_INDEXES = (
    "CREATE INDEX IF NOT EXISTS idx_import_source_records_project ON import_source_records(project_id)",
    "CREATE INDEX IF NOT EXISTS idx_import_source_records_import ON import_source_records(project_id, import_id)",
    "CREATE INDEX IF NOT EXISTS idx_import_source_records_canonical ON import_source_records(project_id, canonical_publication_id)",
    "CREATE INDEX IF NOT EXISTS idx_import_source_records_doi ON import_source_records(project_id, normalized_doi)",
    "CREATE INDEX IF NOT EXISTS idx_import_source_records_file_hash ON import_source_records(project_id, source_file_hash)",
    "CREATE INDEX IF NOT EXISTS idx_import_source_records_fingerprint ON import_source_records(project_id, record_fingerprint)",
    "CREATE INDEX IF NOT EXISTS idx_import_source_records_group ON import_source_records(project_id, duplicate_candidate_group_id)",
)

_SKIP_INDEXES = (
    "CREATE INDEX IF NOT EXISTS idx_import_skip_audit_project ON import_skip_audit(project_id)",
    "CREATE INDEX IF NOT EXISTS idx_import_skip_audit_import ON import_skip_audit(project_id, import_id)",
    "CREATE INDEX IF NOT EXISTS idx_import_skip_audit_match ON import_skip_audit(project_id, matched_publication_id)",
    "CREATE INDEX IF NOT EXISTS idx_import_skip_audit_source ON import_skip_audit(project_id, source_record_id)",
)

_RECOVERY_DDL = """
CREATE TABLE IF NOT EXISTS import_recovery_approvals (
    approval_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    source_record_id TEXT NOT NULL,
    reviewer_identity TEXT NOT NULL,
    decision TEXT NOT NULL CHECK (decision IN ('approved', 'rejected')),
    rationale TEXT NOT NULL,
    approved_at TEXT NOT NULL,
    recovery_executed_at TEXT,
    recovery_outcome TEXT,
    canonical_publication_id TEXT,
    UNIQUE (project_id, source_record_id)
);

CREATE TABLE IF NOT EXISTS import_recovery_audit (
    recovery_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    source_record_id TEXT NOT NULL,
    approval_id TEXT NOT NULL,
    reviewer_identity TEXT NOT NULL,
    executed_at TEXT NOT NULL,
    outcome TEXT NOT NULL,
    canonical_publication_id TEXT,
    detail TEXT,
    FOREIGN KEY (project_id, source_record_id)
        REFERENCES import_recovery_approvals(project_id, source_record_id)
);

CREATE INDEX IF NOT EXISTS idx_import_recovery_approvals_project
    ON import_recovery_approvals(project_id, decision);
CREATE INDEX IF NOT EXISTS idx_import_recovery_audit_project
    ON import_recovery_audit(project_id, executed_at);
"""


@dataclass(frozen=True, slots=True)
class ImportSourceRecord:
    source_record_id: str
    project_id: str
    import_id: UUID
    source_filename: str | None
    source_file_hash: str | None
    source_record_index: int
    title: str
    publication_year: int | None
    original_doi: str | None
    normalized_doi: str | None
    authors: tuple[str, ...]
    document_type: str | None
    provenance: dict
    canonical_publication_id: str | None = None
    duplicate_match_type: str | None = None
    duplicate_match_reason: str | None = None
    duplicate_candidate_group_id: str | None = None
    recovery_status: str = "not_needed"
    created_at: datetime | None = None
    record_fingerprint: str | None = None
    import_format: str | None = None
    doi_status: str = "missing"


@dataclass(frozen=True, slots=True)
class ImportSkipAuditRecord:
    skip_audit_id: str
    project_id: str
    import_id: UUID
    source_filename: str | None
    source_file_hash: str | None
    source_record_index: int
    source_title: str
    source_doi: str | None
    matched_publication_id: str | None
    match_type: str
    match_reason: str
    proposed_action: str
    review_required: bool
    recovery_status: str = "pending_review"
    created_at: datetime | None = None
    source_record_id: str | None = None
    record_fingerprint: str | None = None
    import_format: str | None = None


@dataclass(frozen=True, slots=True)
class RecoveryApproval:
    approval_id: str
    project_id: str
    source_record_id: str
    reviewer_identity: str
    decision: str
    rationale: str
    approved_at: datetime
    recovery_executed_at: datetime | None = None
    recovery_outcome: str | None = None
    canonical_publication_id: str | None = None


@runtime_checkable
class ImportSourceRecordRepository(Protocol):
    def create_source_record(self, record: ImportSourceRecord, *, connection=None) -> ImportSourceRecord: ...
    def create_skip_audit(self, record: ImportSkipAuditRecord, *, connection=None) -> ImportSkipAuditRecord: ...
    def list_source_records(self, project_id: str) -> list[ImportSourceRecord]: ...
    def list_source_records_for_import(self, project_id: str, import_id: UUID) -> list[ImportSourceRecord]: ...
    def list_skip_audit(self, project_id: str) -> list[ImportSkipAuditRecord]: ...
    def list_skip_audit_for_import(self, project_id: str, import_id: UUID) -> list[ImportSkipAuditRecord]: ...
    def find_source_record(self, project_id: str, import_id: UUID, source_record_index: int) -> ImportSourceRecord | None: ...
    def find_source_record_by_id(self, project_id: str, source_record_id: str) -> ImportSourceRecord | None: ...
    def exists_source_record(self, project_id: str, import_id: UUID, source_record_index: int) -> bool: ...
    def update_candidate_group(self, project_id: str, publication_ids: list[str], group_id: str) -> int: ...
    def clear_candidate_groups(self, project_id: str) -> None: ...
    def mark_recovered(
        self,
        project_id: str,
        source_record_id: str,
        canonical_publication_id: str,
        *,
        connection=None,
    ) -> None: ...
    def save_recovery_approval(self, approval: RecoveryApproval, *, connection=None) -> RecoveryApproval: ...
    def get_recovery_approval(self, project_id: str, source_record_id: str) -> RecoveryApproval | None: ...
    def list_recovery_approvals(self, project_id: str) -> list[RecoveryApproval]: ...
    def record_recovery_execution(
        self,
        approval: RecoveryApproval,
        *,
        executed_at: datetime,
        outcome: str,
        canonical_publication_id: str | None,
        detail: str | None = None,
        connection=None,
    ) -> str: ...


class SqliteImportSourceRecordRepository:
    def __init__(self, database_path: str | Path) -> None:
        self._database_path = Path(database_path)
        self._database_path.parent.mkdir(parents=True, exist_ok=True)
        self._apply_migrations()
        self._ensure_import_schema()

    def _connect(self):
        return sqlite3.connect(self._database_path)

    # ------------------------------------------------------------------
    # Migrations and forward-compatibility repair
    # ------------------------------------------------------------------

    def _apply_migrations(self):
        migration_directory = Path(__file__).parents[2] / "migrations"
        with self._connect() as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS schema_migrations ("
                "version TEXT PRIMARY KEY, applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"
            )
            applied = {
                row[0]
                for row in connection.execute("SELECT version FROM schema_migrations").fetchall()
            }
            for migration in sorted(migration_directory.glob("*.sql")):
                if migration.name in applied:
                    continue
                sql = migration.read_text(encoding="utf-8")
                owns_transaction = bool(
                    re.search(r"(?im)^\s*(?:BEGIN|COMMIT)\b", sql)
                )
                try:
                    if owns_transaction:
                        # Legacy migrations such as 0023 manage their own
                        # transaction. Executing them inside another explicit
                        # transaction is invalid SQLite usage.
                        self._execute_script(connection, sql)
                        connection.execute(
                            "INSERT INTO schema_migrations(version) VALUES (?)",
                            (migration.name,),
                        )
                        connection.commit()
                    else:
                        connection.execute("BEGIN IMMEDIATE")
                        self._execute_script(connection, sql)
                        connection.execute(
                            "INSERT INTO schema_migrations(version) VALUES (?)",
                            (migration.name,),
                        )
                        connection.commit()
                except Exception:
                    connection.rollback()
                    raise

    @staticmethod
    def _execute_script(connection: sqlite3.Connection, sql: str) -> None:
        buffer = ""
        for line in sql.splitlines(keepends=True):
            buffer += line
            if sqlite3.complete_statement(buffer):
                statement = buffer.strip()
                buffer = ""
                if statement:
                    connection.execute(statement)
        if buffer.strip():
            connection.execute(buffer)

    def _ensure_import_schema(self) -> None:
        """Upgrade earlier v0.7.3 schemas without losing rows.

        Migration 0034/0035 were edited in place in the earlier remediation.
        Databases that already recorded those filenames in ``schema_migrations``
        therefore keep the old table shape.  This routine detects the legacy
        shape and rebuilds both tables in one transaction, copying every common
        column and preserving all rows.
        """

        with self._connect() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                self._ensure_table(
                    connection,
                    table=_SOURCE_TABLE,
                    required_columns={
                        "project_id",
                        "source_record_id",
                        "import_id",
                        "source_filename",
                        "source_file_hash",
                        "record_fingerprint",
                        "import_format",
                        "source_record_index",
                        "title",
                        "publication_year",
                        "original_doi",
                        "normalized_doi",
                        "doi_status",
                        "authors_json",
                        "document_type",
                        "provenance_json",
                        "canonical_publication_id",
                        "duplicate_match_type",
                        "duplicate_match_reason",
                        "duplicate_candidate_group_id",
                        "recovery_status",
                        "created_at",
                    },
                    ddl=_SOURCE_DDL,
                    indexes=_SOURCE_INDEXES,
                    required_composite_pk=True,
                    unique_sets={("project_id", "import_id", "source_record_index")},
                )
                self._ensure_table(
                    connection,
                    table=_SKIP_TABLE,
                    required_columns={
                        "skip_audit_id",
                        "project_id",
                        "import_id",
                        "source_record_id",
                        "source_filename",
                        "source_file_hash",
                        "record_fingerprint",
                        "import_format",
                        "source_record_index",
                        "source_title",
                        "source_doi",
                        "matched_publication_id",
                        "match_type",
                        "match_reason",
                        "proposed_action",
                        "review_required",
                        "recovery_status",
                        "created_at",
                    },
                    ddl=_SKIP_DDL,
                    indexes=_SKIP_INDEXES,
                    required_composite_pk=False,
                    unique_sets={("project_id", "import_id", "source_record_index")},
                )
                self._execute_script(connection, _RECOVERY_DDL)
                connection.commit()
            except Exception:
                connection.rollback()
                raise

    @staticmethod
    def _table_info(connection: sqlite3.Connection, table: str) -> list[tuple]:
        return connection.execute(f"PRAGMA table_info({table})").fetchall()

    @classmethod
    def _unique_sets(cls, connection: sqlite3.Connection, table: str) -> set[tuple[str, ...]]:
        result: set[tuple[str, ...]] = set()
        for index in connection.execute(f"PRAGMA index_list({table})").fetchall():
            if not index[2]:
                continue
            columns = tuple(
                row[2]
                for row in connection.execute(f"PRAGMA index_info('{index[1]}')").fetchall()
            )
            result.add(columns)
        return result

    def _ensure_table(
        self,
        connection: sqlite3.Connection,
        *,
        table: str,
        required_columns: set[str],
        ddl: str,
        indexes: tuple[str, ...],
        required_composite_pk: bool,
        unique_sets: set[tuple[str, ...]],
    ) -> None:
        info = self._table_info(connection, table)
        if not info:
            self._execute_script(
                connection, ddl + ";\n" + ";\n".join(indexes) + ";"
            )
            return

        existing = {row[1] for row in info}
        primary_key = [row[1] for row in info if row[5]]
        existing_unique = self._unique_sets(connection, table)
        composite_ok = (
            not required_composite_pk
            or set(primary_key) == {"project_id", "source_record_id"}
        )
        unique_ok = unique_sets.issubset(existing_unique)
        missing = required_columns - existing
        if composite_ok and unique_ok and not missing:
            self._execute_script(connection, ";\n".join(indexes) + ";")
            return

        legacy = f"{table}__legacy_v073"
        connection.execute(f"ALTER TABLE {table} RENAME TO {legacy}")
        self._execute_script(connection, ddl + ";")
        legacy_columns = {
            row[1] for row in self._table_info(connection, legacy)
        }
        common = sorted(existing & legacy_columns)
        if common:
            column_list = ", ".join(common)
            connection.execute(
                f"INSERT OR IGNORE INTO {table} ({column_list}) "
                f"SELECT {column_list} FROM {legacy}"
            )
        connection.execute(f"DROP TABLE {legacy}")
        self._execute_script(connection, ";\n".join(indexes) + ";")
        # Fill new required columns for copied legacy rows.
        if "doi_status" in {row[1] for row in self._table_info(connection, table)}:
            connection.execute(
                f"UPDATE {table} SET doi_status = "
                "CASE WHEN normalized_doi IS NOT NULL THEN 'valid' "
                "WHEN original_doi IS NOT NULL THEN 'invalid' ELSE 'missing' END"
            )

    # ------------------------------------------------------------------
    # Source records
    # ------------------------------------------------------------------

    def create_source_record(self, record, *, connection=None):
        conn = connection or self._connect()
        close = connection is None
        try:
            conn.execute(
                """INSERT OR IGNORE INTO import_source_records
                (project_id, source_record_id, import_id, source_filename, source_file_hash,
                 record_fingerprint, import_format, source_record_index, title, publication_year,
                 original_doi, normalized_doi, doi_status, authors_json, document_type,
                 provenance_json, canonical_publication_id, duplicate_match_type,
                 duplicate_match_reason, duplicate_candidate_group_id, recovery_status, created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    record.project_id,
                    record.source_record_id,
                    str(record.import_id),
                    record.source_filename,
                    record.source_file_hash,
                    record.record_fingerprint,
                    record.import_format,
                    record.source_record_index,
                    record.title,
                    record.publication_year,
                    record.original_doi,
                    record.normalized_doi,
                    record.doi_status,
                    json.dumps(list(record.authors), ensure_ascii=False),
                    record.document_type,
                    json.dumps(record.provenance, ensure_ascii=False),
                    record.canonical_publication_id,
                    record.duplicate_match_type,
                    record.duplicate_match_reason,
                    record.duplicate_candidate_group_id,
                    record.recovery_status,
                    (record.created_at or datetime.now(timezone.utc)).isoformat(),
                ),
            )
            if close:
                conn.commit()
        finally:
            if close:
                conn.close()
        return record

    def create_skip_audit(self, record, *, connection=None):
        conn = connection or self._connect()
        close = connection is None
        try:
            conn.execute(
                """INSERT OR IGNORE INTO import_skip_audit
                (skip_audit_id, project_id, import_id, source_record_id, source_filename,
                 source_file_hash, record_fingerprint, import_format, source_record_index,
                 source_title, source_doi, matched_publication_id, match_type, match_reason,
                 proposed_action, review_required, recovery_status, created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    record.skip_audit_id,
                    record.project_id,
                    str(record.import_id),
                    record.source_record_id,
                    record.source_filename,
                    record.source_file_hash,
                    record.record_fingerprint,
                    record.import_format,
                    record.source_record_index,
                    record.source_title,
                    record.source_doi,
                    record.matched_publication_id,
                    record.match_type,
                    record.match_reason,
                    record.proposed_action,
                    1 if record.review_required else 0,
                    record.recovery_status,
                    (record.created_at or datetime.now(timezone.utc)).isoformat(),
                ),
            )
            if close:
                conn.commit()
        finally:
            if close:
                conn.close()
        return record

    _SOURCE_COLUMNS = """project_id, source_record_id, import_id, source_filename, source_file_hash,
        record_fingerprint, import_format, source_record_index, title, publication_year,
        original_doi, normalized_doi, doi_status, authors_json, document_type, provenance_json,
        canonical_publication_id, duplicate_match_type, duplicate_match_reason,
        duplicate_candidate_group_id, recovery_status, created_at"""

    _SKIP_COLUMNS = """skip_audit_id, project_id, import_id, source_record_id, source_filename,
        source_file_hash, record_fingerprint, import_format, source_record_index, source_title,
        source_doi, matched_publication_id, match_type, match_reason, proposed_action,
        review_required, recovery_status, created_at"""

    def list_source_records(self, project_id):
        with self._connect() as conn:
            rows = conn.execute(
                f"""SELECT {self._SOURCE_COLUMNS} FROM import_source_records
                    WHERE project_id=? ORDER BY created_at, source_record_index""",
                (project_id,),
            ).fetchall()
        return [self._source_from_row(r) for r in rows]

    def list_source_records_for_import(self, project_id, import_id):
        with self._connect() as conn:
            rows = conn.execute(
                f"""SELECT {self._SOURCE_COLUMNS} FROM import_source_records
                    WHERE project_id=? AND import_id=? ORDER BY source_record_index""",
                (project_id, str(import_id)),
            ).fetchall()
        return [self._source_from_row(r) for r in rows]

    def list_skip_audit(self, project_id):
        with self._connect() as conn:
            rows = conn.execute(
                f"""SELECT {self._SKIP_COLUMNS} FROM import_skip_audit
                    WHERE project_id=? ORDER BY created_at, source_record_index""",
                (project_id,),
            ).fetchall()
        return [self._skip_from_row(r) for r in rows]

    def list_skip_audit_for_import(self, project_id, import_id):
        with self._connect() as conn:
            rows = conn.execute(
                f"""SELECT {self._SKIP_COLUMNS} FROM import_skip_audit
                    WHERE project_id=? AND import_id=? ORDER BY source_record_index""",
                (project_id, str(import_id)),
            ).fetchall()
        return [self._skip_from_row(r) for r in rows]

    def find_source_record(self, project_id, import_id, source_record_index):
        with self._connect() as conn:
            row = conn.execute(
                f"""SELECT {self._SOURCE_COLUMNS} FROM import_source_records
                    WHERE project_id=? AND import_id=? AND source_record_index=?""",
                (project_id, str(import_id), source_record_index),
            ).fetchone()
        return self._source_from_row(row) if row else None

    def exists_source_record(self, project_id, import_id, source_record_index):
        return self.find_source_record(project_id, import_id, source_record_index) is not None

    def find_source_record_by_id(self, project_id, source_record_id):
        with self._connect() as conn:
            row = conn.execute(
                f"""SELECT {self._SOURCE_COLUMNS} FROM import_source_records
                    WHERE project_id=? AND source_record_id=?""",
                (project_id, source_record_id),
            ).fetchone()
        return self._source_from_row(row) if row else None

    def update_candidate_group(self, project_id, publication_ids, group_id):
        if not publication_ids:
            return 0
        placeholders = ",".join("?" for _ in publication_ids)
        with self._connect() as conn:
            cursor = conn.execute(
                f"""UPDATE import_source_records
                    SET duplicate_candidate_group_id=?
                    WHERE project_id=? AND canonical_publication_id IN ({placeholders})""",
                (group_id, project_id, *publication_ids),
            )
            conn.commit()
            return cursor.rowcount

    def clear_candidate_groups(self, project_id):
        with self._connect() as conn:
            conn.execute(
                "UPDATE import_source_records SET duplicate_candidate_group_id=NULL "
                "WHERE project_id=?",
                (project_id,),
            )
            conn.commit()

    def mark_recovered(
        self,
        project_id,
        source_record_id,
        canonical_publication_id,
        *,
        connection=None,
    ) -> None:
        conn = connection or self._connect()
        close = connection is None
        try:
            conn.execute(
                """UPDATE import_source_records
                   SET canonical_publication_id=?, recovery_status='recovered',
                       duplicate_match_type='recovered',
                       duplicate_match_reason='Researcher-approved historical recovery'
                   WHERE project_id=? AND source_record_id=?""",
                (canonical_publication_id, project_id, source_record_id),
            )
            conn.execute(
                """UPDATE import_skip_audit
                   SET recovery_status='recovered', matched_publication_id=?
                   WHERE project_id=? AND source_record_id=?""",
                (canonical_publication_id, project_id, source_record_id),
            )
            if close:
                conn.commit()
        finally:
            if close:
                conn.close()

    # ------------------------------------------------------------------
    # Recovery approvals and audit
    # ------------------------------------------------------------------

    def save_recovery_approval(self, approval, *, connection=None):
        conn = connection or self._connect()
        close = connection is None
        try:
            conn.execute(
                """INSERT INTO import_recovery_approvals
                   (approval_id, project_id, source_record_id, reviewer_identity, decision,
                    rationale, approved_at, recovery_executed_at, recovery_outcome,
                    canonical_publication_id)
                   VALUES (?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(project_id, source_record_id) DO UPDATE SET
                     reviewer_identity=excluded.reviewer_identity,
                     decision=excluded.decision,
                     rationale=excluded.rationale,
                     approved_at=excluded.approved_at,
                     recovery_executed_at=NULL,
                     recovery_outcome=NULL,
                     canonical_publication_id=NULL""",
                (
                    approval.approval_id,
                    approval.project_id,
                    approval.source_record_id,
                    approval.reviewer_identity,
                    approval.decision,
                    approval.rationale,
                    approval.approved_at.isoformat(),
                    approval.recovery_executed_at.isoformat()
                    if approval.recovery_executed_at
                    else None,
                    approval.recovery_outcome,
                    approval.canonical_publication_id,
                ),
            )
            if close:
                conn.commit()
        finally:
            if close:
                conn.close()
        return approval

    def get_recovery_approval(self, project_id, source_record_id):
        with self._connect() as conn:
            row = conn.execute(
                """SELECT approval_id, project_id, source_record_id, reviewer_identity,
                          decision, rationale, approved_at, recovery_executed_at,
                          recovery_outcome, canonical_publication_id
                   FROM import_recovery_approvals
                   WHERE project_id=? AND source_record_id=?""",
                (project_id, source_record_id),
            ).fetchone()
        return self._approval_from_row(row) if row else None

    def list_recovery_approvals(self, project_id):
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT approval_id, project_id, source_record_id, reviewer_identity,
                          decision, rationale, approved_at, recovery_executed_at,
                          recovery_outcome, canonical_publication_id
                   FROM import_recovery_approvals
                   WHERE project_id=? ORDER BY approved_at, source_record_id""",
                (project_id,),
            ).fetchall()
        return [self._approval_from_row(row) for row in rows]

    def record_recovery_execution(
        self,
        approval,
        *,
        executed_at,
        outcome,
        canonical_publication_id,
        detail=None,
        connection=None,
    ):
        conn = connection or self._connect()
        close = connection is None
        recovery_id = str(uuid4())
        try:
            conn.execute(
                """UPDATE import_recovery_approvals
                   SET recovery_executed_at=?, recovery_outcome=?, canonical_publication_id=?
                   WHERE project_id=? AND source_record_id=?""",
                (
                    executed_at.isoformat(),
                    outcome,
                    canonical_publication_id,
                    approval.project_id,
                    approval.source_record_id,
                ),
            )
            conn.execute(
                """INSERT INTO import_recovery_audit
                   (recovery_id, project_id, source_record_id, approval_id, reviewer_identity,
                    executed_at, outcome, canonical_publication_id, detail)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (
                    recovery_id,
                    approval.project_id,
                    approval.source_record_id,
                    approval.approval_id,
                    approval.reviewer_identity,
                    executed_at.isoformat(),
                    outcome,
                    canonical_publication_id,
                    detail,
                ),
            )
            if close:
                conn.commit()
        finally:
            if close:
                conn.close()
        return recovery_id

    # ------------------------------------------------------------------
    # Row mapping
    # ------------------------------------------------------------------

    @staticmethod
    def _source_from_row(row):
        return ImportSourceRecord(
            project_id=str(row[0]),
            source_record_id=str(row[1]),
            import_id=UUID(str(row[2])),
            source_filename=row[3] if isinstance(row[3], str) else None,
            source_file_hash=row[4] if isinstance(row[4], str) else None,
            record_fingerprint=row[5] if isinstance(row[5], str) else None,
            import_format=row[6] if isinstance(row[6], str) else None,
            source_record_index=int(row[7]),
            title=str(row[8]),
            publication_year=int(row[9]) if row[9] is not None else None,
            original_doi=row[10] if isinstance(row[10], str) else None,
            normalized_doi=row[11] if isinstance(row[11], str) else None,
            doi_status=str(row[12]),
            authors=tuple(json.loads(str(row[13]))),
            document_type=row[14] if isinstance(row[14], str) else None,
            provenance=json.loads(str(row[15])),
            canonical_publication_id=row[16] if isinstance(row[16], str) else None,
            duplicate_match_type=row[17] if isinstance(row[17], str) else None,
            duplicate_match_reason=row[18] if isinstance(row[18], str) else None,
            duplicate_candidate_group_id=row[19] if isinstance(row[19], str) else None,
            recovery_status=str(row[20]),
            created_at=datetime.fromisoformat(str(row[21])) if row[21] is not None else None,
        )

    @staticmethod
    def _skip_from_row(row):
        return ImportSkipAuditRecord(
            skip_audit_id=str(row[0]),
            project_id=str(row[1]),
            import_id=UUID(str(row[2])),
            source_record_id=row[3] if isinstance(row[3], str) else None,
            source_filename=row[4] if isinstance(row[4], str) else None,
            source_file_hash=row[5] if isinstance(row[5], str) else None,
            record_fingerprint=row[6] if isinstance(row[6], str) else None,
            import_format=row[7] if isinstance(row[7], str) else None,
            source_record_index=int(row[8]),
            source_title=str(row[9]),
            source_doi=row[10] if isinstance(row[10], str) else None,
            matched_publication_id=row[11] if isinstance(row[11], str) else None,
            match_type=str(row[12]),
            match_reason=str(row[13]),
            proposed_action=str(row[14]),
            review_required=bool(row[15]),
            recovery_status=str(row[16]),
            created_at=datetime.fromisoformat(str(row[17])) if row[17] is not None else None,
        )

    @staticmethod
    def _approval_from_row(row):
        return RecoveryApproval(
            approval_id=str(row[0]),
            project_id=str(row[1]),
            source_record_id=str(row[2]),
            reviewer_identity=str(row[3]),
            decision=str(row[4]),
            rationale=str(row[5]),
            approved_at=datetime.fromisoformat(str(row[6])),
            recovery_executed_at=datetime.fromisoformat(str(row[7]))
            if row[7] is not None
            else None,
            recovery_outcome=str(row[8]) if row[8] is not None else None,
            canonical_publication_id=str(row[9]) if row[9] is not None else None,
        )


def default_import_source_record_repository():
    path = os.environ.get("SLR_DATABASE_PATH", "data/slr-platform.db")
    return SqliteImportSourceRecordRepository(path)
