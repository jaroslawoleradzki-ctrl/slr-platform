from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol, runtime_checkable
from uuid import UUID, uuid4


@dataclass(frozen=True, slots=True)
class ImportSourceRecord:
    source_record_id: str
    project_id: str
    import_id: UUID
    source_filename: str | None
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


@dataclass(frozen=True, slots=True)
class ImportSkipAuditRecord:
    skip_audit_id: str
    project_id: str
    import_id: UUID
    source_filename: str | None
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


@runtime_checkable
class ImportSourceRecordRepository(Protocol):
    def create_source_record(self, record: ImportSourceRecord, *, connection=None) -> ImportSourceRecord: ...
    def create_skip_audit(self, record: ImportSkipAuditRecord, *, connection=None) -> ImportSkipAuditRecord: ...
    def list_source_records(self, project_id: str) -> list[ImportSourceRecord]: ...
    def list_skip_audit(self, project_id: str) -> list[ImportSkipAuditRecord]: ...
    def find_source_record(self, project_id: str, import_id: UUID, source_record_index: int) -> ImportSourceRecord | None: ...
    def exists_source_record(self, project_id: str, import_id: UUID, source_record_index: int) -> bool: ...


class SqliteImportSourceRecordRepository:
    def __init__(self, database_path: str | Path) -> None:
        self._database_path = Path(database_path)
        self._database_path.parent.mkdir(parents=True, exist_ok=True)
        self._apply_migrations()

    def _connect(self):
        return sqlite3.connect(self._database_path)

    def _apply_migrations(self):
        migration_directory = Path(__file__).parents[2] / "migrations"
        with self._connect() as connection:
            connection.execute("""CREATE TABLE IF NOT EXISTS schema_migrations (version TEXT PRIMARY KEY, applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)""")
            applied = {r[0] for r in connection.execute("SELECT version FROM schema_migrations").fetchall()}
            for migration in sorted(migration_directory.glob("*.sql")):
                if migration.name in applied:
                    continue
                connection.executescript(migration.read_text(encoding="utf-8"))
                connection.execute("INSERT INTO schema_migrations(version) VALUES (?)", (migration.name,))

    def create_source_record(self, record, *, connection=None):
        conn = connection or self._connect()
        close = connection is None
        try:
            conn.execute(
                """INSERT OR IGNORE INTO import_source_records
                (source_record_id, project_id, import_id, source_filename, source_record_index,
                 title, publication_year, original_doi, normalized_doi, authors_json, document_type,
                 provenance_json, canonical_publication_id, duplicate_match_type, duplicate_match_reason,
                 duplicate_candidate_group_id, recovery_status, created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    record.source_record_id,
                    record.project_id,
                    str(record.import_id),
                    record.source_filename,
                    record.source_record_index,
                    record.title,
                    record.publication_year,
                    record.original_doi,
                    record.normalized_doi,
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
                (skip_audit_id, project_id, import_id, source_filename, source_record_index,
                 source_title, source_doi, matched_publication_id, match_type, match_reason,
                 proposed_action, review_required, recovery_status, created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    record.skip_audit_id,
                    record.project_id,
                    str(record.import_id),
                    record.source_filename,
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

    def list_source_records(self, project_id):
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT source_record_id, project_id, import_id, source_filename, source_record_index,
                          title, publication_year, original_doi, normalized_doi, authors_json, document_type,
                          provenance_json, canonical_publication_id, duplicate_match_type, duplicate_match_reason,
                          duplicate_candidate_group_id, recovery_status, created_at
                   FROM import_source_records WHERE project_id=? ORDER BY created_at, source_record_index""",
                (project_id,),
            ).fetchall()
        return [self._source_from_row(r) for r in rows]

    def list_skip_audit(self, project_id):
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT skip_audit_id, project_id, import_id, source_filename, source_record_index,
                          source_title, source_doi, matched_publication_id, match_type, match_reason,
                          proposed_action, review_required, recovery_status, created_at
                   FROM import_skip_audit WHERE project_id=? ORDER BY created_at, source_record_index""",
                (project_id,),
            ).fetchall()
        return [self._skip_from_row(r) for r in rows]

    def find_source_record(self, project_id, import_id, source_record_index):
        with self._connect() as conn:
            row = conn.execute(
                """SELECT source_record_id, project_id, import_id, source_filename, source_record_index,
                          title, publication_year, original_doi, normalized_doi, authors_json, document_type,
                          provenance_json, canonical_publication_id, duplicate_match_type, duplicate_match_reason,
                          duplicate_candidate_group_id, recovery_status, created_at
                   FROM import_source_records WHERE project_id=? AND import_id=? AND source_record_index=?""",
                (project_id, str(import_id), source_record_index),
            ).fetchone()
        return self._source_from_row(row) if row else None

    def exists_source_record(self, project_id, import_id, source_record_index):
        return self.find_source_record(project_id, import_id, source_record_index) is not None

    def find_source_record_by_id(self, source_record_id):
        with self._connect() as conn:
            row = conn.execute(
                """SELECT source_record_id, project_id, import_id, source_filename, source_record_index,
                          title, publication_year, original_doi, normalized_doi, authors_json, document_type,
                          provenance_json, canonical_publication_id, duplicate_match_type, duplicate_match_reason,
                          duplicate_candidate_group_id, recovery_status, created_at
                   FROM import_source_records WHERE source_record_id=?""",
                (source_record_id,),
            ).fetchone()
        return self._source_from_row(row) if row else None

    @staticmethod
    def _source_from_row(row):
        return ImportSourceRecord(
            source_record_id=str(row[0]),
            project_id=str(row[1]),
            import_id=UUID(str(row[2])),
            source_filename=row[3] if isinstance(row[3], str) else None,
            source_record_index=int(row[4]),
            title=str(row[5]),
            publication_year=int(row[6]) if row[6] is not None else None,
            original_doi=row[7] if isinstance(row[7], str) else None,
            normalized_doi=row[8] if isinstance(row[8], str) else None,
            authors=tuple(json.loads(str(row[9]))),
            document_type=row[10] if isinstance(row[10], str) else None,
            provenance=json.loads(str(row[11])),
            canonical_publication_id=row[12] if isinstance(row[12], str) else None,
            duplicate_match_type=row[13] if isinstance(row[13], str) else None,
            duplicate_match_reason=row[14] if isinstance(row[14], str) else None,
            duplicate_candidate_group_id=row[15] if isinstance(row[15], str) else None,
            recovery_status=str(row[16]),
            created_at=datetime.fromisoformat(str(row[17])) if row[17] is not None else None,
        )

    @staticmethod
    def _skip_from_row(row):
        return ImportSkipAuditRecord(
            skip_audit_id=str(row[0]),
            project_id=str(row[1]),
            import_id=UUID(str(row[2])),
            source_filename=row[3] if isinstance(row[3], str) else None,
            source_record_index=int(row[4]),
            source_title=str(row[5]),
            source_doi=row[6] if isinstance(row[6], str) else None,
            matched_publication_id=row[7] if isinstance(row[7], str) else None,
            match_type=str(row[8]),
            match_reason=str(row[9]),
            proposed_action=str(row[10]),
            review_required=bool(row[11]),
            recovery_status=str(row[12]),
            created_at=datetime.fromisoformat(str(row[13])) if row[13] is not None else None,
        )


def default_import_source_record_repository():
    path = os.environ.get("SLR_DATABASE_PATH", "data/slr-platform.db")
    return SqliteImportSourceRecordRepository(path)
