from __future__ import annotations

import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Protocol, runtime_checkable
from uuid import UUID

from app.domain.pre_screening import (
    PreScreeningDecision,
    PreScreeningRemovalReason,
    PreScreeningStatus,
)


@runtime_checkable
class PreScreeningDecisionRepository(Protocol):
    def save_decision(
        self, decision: PreScreeningDecision, *, connection: sqlite3.Connection | None = None
    ) -> PreScreeningDecision: ...

    def get_latest_decision(
        self, project_id: str, record_id: UUID, *, connection: sqlite3.Connection | None = None
    ) -> PreScreeningDecision | None: ...

    def list_decisions_for_project(
        self, project_id: str, *, connection: sqlite3.Connection | None = None
    ) -> list[PreScreeningDecision]: ...

    def list_decisions_for_import(
        self, project_id: str, import_id: UUID, *, connection: sqlite3.Connection | None = None
    ) -> list[PreScreeningDecision]: ...

    def delete_for_project(
        self, project_id: str, *, connection: sqlite3.Connection | None = None
    ) -> None: ...


class SqlitePreScreeningDecisionRepository:
    def __init__(self, database_path: str | Path) -> None:
        self._database_path = Path(database_path)
        self._database_path.parent.mkdir(parents=True, exist_ok=True)
        self._apply_migrations()

    def save_decision(
        self, decision: PreScreeningDecision, *, connection: sqlite3.Connection | None = None
    ) -> PreScreeningDecision:
        def query(conn: sqlite3.Connection) -> None:
            conn.execute(
                """
                INSERT INTO pre_screening_decisions (
                    decision_id, project_id, record_id, import_id,
                    status, reason, notes, reviewer_id, decided_at, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(decision.decision_id),
                    decision.project_id,
                    str(decision.record_id),
                    str(decision.import_id) if decision.import_id is not None else None,
                    decision.status.value,
                    decision.reason.value if decision.reason is not None else None,
                    decision.notes,
                    decision.reviewer_id,
                    decision.decided_at.isoformat(),
                    decision.created_at.isoformat(),
                ),
            )

        if connection is not None:
            query(connection)
        else:
            with self._connect() as conn:
                query(conn)
        return decision

    def get_latest_decision(
        self, project_id: str, record_id: UUID, *, connection: sqlite3.Connection | None = None
    ) -> PreScreeningDecision | None:
        def query(conn: sqlite3.Connection) -> PreScreeningDecision | None:
            row = conn.execute(
                """
                SELECT decision_id, project_id, record_id, import_id,
                       status, reason, notes, reviewer_id, decided_at, created_at
                FROM pre_screening_decisions
                WHERE project_id = ? AND record_id = ?
                ORDER BY decided_at DESC, created_at DESC, rowid DESC
                LIMIT 1
                """,
                (project_id, str(record_id)),
            ).fetchone()
            if row is None:
                return None
            return self._row_to_decision(row)

        if connection is not None:
            return query(connection)
        with self._connect() as conn:
            return query(conn)

    def list_decisions_for_project(
        self, project_id: str, *, connection: sqlite3.Connection | None = None
    ) -> list[PreScreeningDecision]:
        def query(conn: sqlite3.Connection) -> list[PreScreeningDecision]:
            rows = conn.execute(
                """
                SELECT decision_id, project_id, record_id, import_id,
                       status, reason, notes, reviewer_id, decided_at, created_at
                FROM pre_screening_decisions
                WHERE project_id = ?
                ORDER BY decided_at DESC, created_at DESC, rowid DESC
                """,
                (project_id,),
            ).fetchall()
            return [self._row_to_decision(row) for row in rows]

        if connection is not None:
            return query(connection)
        with self._connect() as conn:
            return query(conn)

    def list_decisions_for_import(
        self, project_id: str, import_id: UUID, *, connection: sqlite3.Connection | None = None
    ) -> list[PreScreeningDecision]:
        def query(conn: sqlite3.Connection) -> list[PreScreeningDecision]:
            rows = conn.execute(
                """
                SELECT decision_id, project_id, record_id, import_id,
                       status, reason, notes, reviewer_id, decided_at, created_at
                FROM pre_screening_decisions
                WHERE project_id = ? AND import_id = ?
                ORDER BY decided_at DESC, created_at DESC, rowid DESC
                """,
                (project_id, str(import_id)),
            ).fetchall()
            return [self._row_to_decision(row) for row in rows]

        if connection is not None:
            return query(connection)
        with self._connect() as conn:
            return query(conn)

    def delete_for_project(
        self, project_id: str, *, connection: sqlite3.Connection | None = None
    ) -> None:
        if connection is not None:
            connection.execute(
                "DELETE FROM pre_screening_decisions WHERE project_id = ?", (project_id,)
            )
        else:
            with self._connect() as conn:
                conn.execute(
                    "DELETE FROM pre_screening_decisions WHERE project_id = ?", (project_id,)
                )

    @staticmethod
    def _row_to_decision(row: tuple[object, ...]) -> PreScreeningDecision:
        return PreScreeningDecision(
            decision_id=UUID(str(row[0])),
            project_id=str(row[1]),
            record_id=UUID(str(row[2])),
            import_id=UUID(str(row[3])) if row[3] is not None else None,
            status=PreScreeningStatus(str(row[4])),
            reason=PreScreeningRemovalReason(str(row[5])) if row[5] is not None else None,
            notes=str(row[6]) if row[6] is not None else None,
            reviewer_id=str(row[7]),
            decided_at=datetime.fromisoformat(str(row[8])),
            created_at=datetime.fromisoformat(str(row[9])),
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


def default_pre_screening_decision_repository() -> SqlitePreScreeningDecisionRepository:
    path = os.environ.get("SLR_DATABASE_PATH", "data/slr-platform.db")
    return SqlitePreScreeningDecisionRepository(path)
