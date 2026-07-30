from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Protocol
from uuid import UUID

from app.services.normalization_service import NormalizationExecution


class NormalizationExecutionRepository(Protocol):
    def save(self, execution: NormalizationExecution) -> NormalizationExecution: ...

    def get_for_project(self, project_id: str) -> NormalizationExecution | None: ...

    def delete_for_project(self, project_id: str) -> None: ...


class SqliteNormalizationExecutionRepository:
    """Stores the latest normalization execution for each project."""

    def __init__(self, database_path: str | Path) -> None:
        self._database_path = Path(database_path)
        self._database_path.parent.mkdir(parents=True, exist_ok=True)
        self._apply_migrations()

    def save(self, execution: NormalizationExecution) -> NormalizationExecution:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO normalization_executions (
                    project_id, run_id, status, processed_records, clean_records,
                    warnings_count, errors_count, started_at, completed_at,
                    audit_trail, rules_applied, error_message
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(project_id) DO UPDATE SET
                    run_id = excluded.run_id,
                    status = excluded.status,
                    processed_records = excluded.processed_records,
                    clean_records = excluded.clean_records,
                    warnings_count = excluded.warnings_count,
                    errors_count = excluded.errors_count,
                    started_at = excluded.started_at,
                    completed_at = excluded.completed_at,
                    audit_trail = excluded.audit_trail,
                    rules_applied = excluded.rules_applied,
                    error_message = excluded.error_message
                """,
                (
                    execution.project_id,
                    str(execution.run_id),
                    execution.status,
                    execution.processed_records,
                    execution.clean_records,
                    execution.warnings_count,
                    execution.errors_count,
                    execution.started_at.isoformat(),
                    execution.completed_at.isoformat(),
                    json.dumps(list(execution.audit_trail), ensure_ascii=False),
                    json.dumps(list(execution.rules_applied), ensure_ascii=False),
                    execution.error_message,
                ),
            )
        return execution

    def get_for_project(self, project_id: str) -> NormalizationExecution | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT project_id, run_id, status, processed_records, clean_records,
                       warnings_count, errors_count, started_at, completed_at,
                       audit_trail, rules_applied, error_message
                FROM normalization_executions
                WHERE project_id = ?
                """,
                (project_id,),
            ).fetchone()
        if row is None:
            return None
        return NormalizationExecution(
            project_id=str(row[0]),
            run_id=UUID(str(row[1])),
            status=str(row[2]),
            processed_records=int(row[3]),
            clean_records=int(row[4]),
            warnings_count=int(row[5]),
            errors_count=int(row[6]),
            started_at=datetime.fromisoformat(str(row[7])),
            completed_at=datetime.fromisoformat(str(row[8])),
            audit_trail=tuple(json.loads(str(row[9]))),
            rules_applied=tuple(json.loads(str(row[10]))),
            error_message=str(row[11]) if row[11] is not None else None,
        )

    def delete_for_project(self, project_id: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "DELETE FROM normalization_executions WHERE project_id = ?",
                (project_id,),
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


def default_normalization_execution_repository() -> SqliteNormalizationExecutionRepository:
    path = os.environ.get("SLR_DATABASE_PATH", "data/slr-platform.db")
    return SqliteNormalizationExecutionRepository(path)
