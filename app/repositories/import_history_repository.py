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
    filename: str
    format: str
    records_count: int
    status: str
    warnings: tuple[str, ...]
    created_at: datetime


class ImportHistoryRepository(Protocol):
    def create(self, record: ImportHistoryRecord) -> ImportHistoryRecord: ...

    def list_for_project(self, project_id: str) -> list[ImportHistoryRecord]: ...


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
                    import_id, project_id, filename, format, records_count,
                    status, warnings, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(record.import_id),
                    record.project_id,
                    record.filename,
                    record.format,
                    record.records_count,
                    record.status,
                    json.dumps(list(record.warnings), ensure_ascii=False),
                    record.created_at.isoformat(),
                ),
            )
        return record

    def list_for_project(self, project_id: str) -> list[ImportHistoryRecord]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT import_id, project_id, filename, format, records_count,
                       status, warnings, created_at
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
                filename=row[2],
                format=row[3],
                records_count=row[4],
                status=row[5],
                warnings=tuple(json.loads(row[6])),
                created_at=datetime.fromisoformat(row[7]),
            )
            for row in rows
        ]

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
