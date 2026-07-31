from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True, slots=True)
class ImportHistoryRecord:
    import_id: UUID
    project_id: str
    source_type: str
    filename: str | None
    format: str | None
    provider: str | None
    query: str | None
    records_count: int
    total_available: int | None
    status: str
    warnings: tuple[str, ...]
    created_at: datetime
    fingerprint: str | None = None


class ImportHistoryRepository(Protocol):
    def create(self, record: ImportHistoryRecord) -> ImportHistoryRecord: ...

    def list_for_project(self, project_id: str) -> list[ImportHistoryRecord]: ...

    def find_by_fingerprint(
        self, project_id: str, fingerprint: str
    ) -> ImportHistoryRecord | None: ...


class SqliteImportHistoryRepository:
    def __init__(self, database_path: str | Path) -> None:
        self._database_path = Path(database_path)
        self._database_path.parent.mkdir(parents=True, exist_ok=True)
        self._apply_migrations()

    def create(self, record: ImportHistoryRecord) -> ImportHistoryRecord:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO import_history (
                    import_id, project_id, source_type, filename, format,
                    provider, query, records_count, total_available, status,
                    warnings, created_at, fingerprint
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(record.import_id),
                    record.project_id,
                    record.source_type,
                    record.filename,
                    record.format,
                    record.provider,
                    record.query,
                    record.records_count,
                    record.total_available,
                    record.status,
                    json.dumps(list(record.warnings), ensure_ascii=False),
                    record.created_at.isoformat(),
                    record.fingerprint,
                ),
            )
        return record

    def list_for_project(self, project_id: str) -> list[ImportHistoryRecord]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT import_id, project_id, source_type, filename, format,
                       provider, query, records_count, total_available, status,
                       warnings, created_at, fingerprint
                FROM import_history
                WHERE project_id = ?
                ORDER BY created_at DESC, rowid DESC
                """,
                (project_id,),
            ).fetchall()
        return [
            ImportHistoryRecord(
                import_id=UUID(row[0]),
                project_id=row[1],
                source_type=row[2],
                filename=row[3],
                format=row[4],
                provider=row[5],
                query=row[6],
                records_count=row[7],
                total_available=row[8],
                status=row[9],
                warnings=tuple(json.loads(row[10])),
                created_at=datetime.fromisoformat(row[11]),
                fingerprint=row[12],
            )
            for row in rows
        ]

    def find_by_fingerprint(
        self, project_id: str, fingerprint: str
    ) -> ImportHistoryRecord | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT import_id, project_id, source_type, filename, format,
                       provider, query, records_count, total_available, status,
                       warnings, created_at, fingerprint
                FROM import_history
                WHERE project_id = ? AND fingerprint = ?
                """,
                (project_id, fingerprint),
            ).fetchone()
        if row is None:
            return None
        return self._record_from_row(row)

    @staticmethod
    def _record_from_row(row: tuple[object, ...]) -> ImportHistoryRecord:
        return ImportHistoryRecord(
            import_id=UUID(str(row[0])),
            project_id=str(row[1]),
            source_type=str(row[2]),
            filename=row[3] if isinstance(row[3], str) else None,
            format=row[4] if isinstance(row[4], str) else None,
            provider=row[5] if isinstance(row[5], str) else None,
            query=row[6] if isinstance(row[6], str) else None,
            records_count=int(str(row[7])),
            total_available=int(str(row[8])) if row[8] is not None else None,
            status=str(row[9]),
            warnings=tuple(json.loads(str(row[10]))),
            created_at=datetime.fromisoformat(str(row[11])),
            fingerprint=row[12] if isinstance(row[12], str) else None,
        )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._database_path)

    def _apply_migrations(self) -> None:
        migration_directory = Path(__file__).parents[2] / "migrations"
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version TEXT PRIMARY KEY,
                    applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            applied = {
                row[0]
                for row in connection.execute(
                    "SELECT version FROM schema_migrations"
                ).fetchall()
            }
            for migration in sorted(migration_directory.glob("*.sql")):
                if migration.name in applied:
                    continue
                connection.executescript(migration.read_text(encoding="utf-8"))
                connection.execute(
                    "INSERT INTO schema_migrations(version) VALUES (?)",
                    (migration.name,),
                )


def default_import_history_repository() -> SqliteImportHistoryRepository:
    path = os.environ.get("SLR_DATABASE_PATH", "data/slr-platform.db")
    return SqliteImportHistoryRepository(path)
