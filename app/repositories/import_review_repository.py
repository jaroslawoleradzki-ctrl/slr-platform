from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Protocol, runtime_checkable
from uuid import UUID

from app.domain.import_review import ImportReviewDecision


class ImportReviewConflictError(Exception):
    """Raised when an import already has a different terminal decision."""


@runtime_checkable
class ImportReviewRepository(Protocol):
    def create(
        self,
        decision: ImportReviewDecision,
        *,
        connection: sqlite3.Connection | None = None,
    ) -> ImportReviewDecision: ...

    def get(
        self,
        project_id: str,
        import_id: UUID,
        *,
        connection: sqlite3.Connection | None = None,
    ) -> ImportReviewDecision | None: ...

    def list_for_project(
        self,
        project_id: str,
        *,
        connection: sqlite3.Connection | None = None,
    ) -> dict[UUID, ImportReviewDecision]: ...

    def list_rejected_import_ids(
        self,
        project_id: str,
        *,
        connection: sqlite3.Connection | None = None,
    ) -> set[UUID]: ...

    def delete_for_project(
        self,
        project_id: str,
        *,
        connection: sqlite3.Connection | None = None,
    ) -> None: ...


class SqliteImportReviewRepository:
    def __init__(self, database_path: str | Path) -> None:
        self._database_path = Path(database_path)
        self._database_path.parent.mkdir(parents=True, exist_ok=True)
        self._apply_migrations()

    def create(
        self,
        decision: ImportReviewDecision,
        *,
        connection: sqlite3.Connection | None = None,
    ) -> ImportReviewDecision:
        def execute(conn: sqlite3.Connection) -> None:
            try:
                conn.execute(
                    """
                    INSERT INTO import_review_decisions (
                        decision_id, project_id, import_id, decision, reviewer_id,
                        rationale, decided_at, import_status_at_decision,
                        warning_snapshot_json, affected_source_record_ids_json,
                        affected_publication_ids_json,
                        removed_publication_snapshots_json,
                        deleted_publication_count,
                        retained_source_record_count, prisma_treatment
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(decision.decision_id),
                        decision.project_id,
                        str(decision.import_id),
                        decision.decision,
                        decision.reviewer_id,
                        decision.rationale,
                        decision.decided_at.isoformat(),
                        decision.import_status_at_decision,
                        json.dumps(list(decision.warning_snapshot), ensure_ascii=False),
                        json.dumps(list(decision.affected_source_record_ids), ensure_ascii=False),
                        json.dumps(list(decision.affected_publication_ids), ensure_ascii=False),
                        json.dumps(list(decision.removed_publication_snapshots), ensure_ascii=False),
                        decision.deleted_publication_count,
                        decision.retained_source_record_count,
                        decision.prisma_treatment,
                    ),
                )
            except sqlite3.IntegrityError as exc:
                existing = self.get(
                    decision.project_id, decision.import_id, connection=conn
                )
                if existing is not None:
                    raise ImportReviewConflictError(
                        f"Import '{decision.import_id}' already has decision "
                        f"'{existing.decision}'."
                    ) from exc
                raise

        if connection is not None:
            execute(connection)
        else:
            with self._connect() as conn:
                execute(conn)
        return decision

    def get(
        self,
        project_id: str,
        import_id: UUID,
        *,
        connection: sqlite3.Connection | None = None,
    ) -> ImportReviewDecision | None:
        def query(conn: sqlite3.Connection) -> ImportReviewDecision | None:
            row = conn.execute(
                """
                SELECT decision_id, project_id, import_id, decision, reviewer_id,
                       rationale, decided_at, import_status_at_decision,
                       warning_snapshot_json, affected_source_record_ids_json,
                       affected_publication_ids_json,
                       removed_publication_snapshots_json,
                       deleted_publication_count, retained_source_record_count,
                       prisma_treatment
                FROM import_review_decisions
                WHERE project_id = ? AND import_id = ?
                """,
                (project_id, str(import_id)),
            ).fetchone()
            return self._row_to_decision(row) if row is not None else None

        if connection is not None:
            return query(connection)
        with self._connect() as conn:
            return query(conn)

    def list_for_project(
        self,
        project_id: str,
        *,
        connection: sqlite3.Connection | None = None,
    ) -> dict[UUID, ImportReviewDecision]:
        def query(conn: sqlite3.Connection) -> dict[UUID, ImportReviewDecision]:
            rows = conn.execute(
                """
                SELECT decision_id, project_id, import_id, decision, reviewer_id,
                       rationale, decided_at, import_status_at_decision,
                       warning_snapshot_json, affected_source_record_ids_json,
                       affected_publication_ids_json,
                       removed_publication_snapshots_json,
                       deleted_publication_count, retained_source_record_count,
                       prisma_treatment
                FROM import_review_decisions
                WHERE project_id = ?
                ORDER BY decided_at ASC, decision_id ASC
                """,
                (project_id,),
            ).fetchall()
            return {
                UUID(str(row[2])): self._row_to_decision(row)
                for row in rows
            }

        if connection is not None:
            return query(connection)
        with self._connect() as conn:
            return query(conn)

    def list_rejected_import_ids(
        self,
        project_id: str,
        *,
        connection: sqlite3.Connection | None = None,
    ) -> set[UUID]:
        def query(conn: sqlite3.Connection) -> set[UUID]:
            rows = conn.execute(
                """
                SELECT import_id
                FROM import_review_decisions
                WHERE project_id = ? AND decision = 'rejected'
                """,
                (project_id,),
            ).fetchall()
            return {UUID(str(row[0])) for row in rows}

        if connection is not None:
            return query(connection)
        with self._connect() as conn:
            return query(conn)

    def delete_for_project(
        self,
        project_id: str,
        *,
        connection: sqlite3.Connection | None = None,
    ) -> None:
        if connection is not None:
            connection.execute(
                "DELETE FROM import_review_decisions WHERE project_id = ?",
                (project_id,),
            )
        else:
            with self._connect() as conn:
                conn.execute(
                    "DELETE FROM import_review_decisions WHERE project_id = ?",
                    (project_id,),
                )

    @staticmethod
    def _row_to_decision(row: tuple[object, ...]) -> ImportReviewDecision:
        return ImportReviewDecision(
            decision_id=UUID(str(row[0])),
            project_id=str(row[1]),
            import_id=UUID(str(row[2])),
            decision=str(row[3]),
            reviewer_id=str(row[4]),
            rationale=str(row[5]) if row[5] is not None else None,
            decided_at=datetime.fromisoformat(str(row[6])),
            import_status_at_decision=str(row[7]),
            warning_snapshot=tuple(str(value) for value in json.loads(str(row[8]))),
            affected_source_record_ids=tuple(
                str(value) for value in json.loads(str(row[9]))
            ),
            affected_publication_ids=tuple(
                str(value) for value in json.loads(str(row[10]))
            ),
            removed_publication_snapshots=tuple(
                dict(value) for value in json.loads(str(row[11]))
            ),
            deleted_publication_count=int(str(row[12])),
            retained_source_record_count=int(str(row[13])),
            prisma_treatment=str(row[14]),
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


def default_import_review_repository() -> SqliteImportReviewRepository:
    path = os.environ.get("SLR_DATABASE_PATH", "data/slr-platform.db")
    return SqliteImportReviewRepository(path)
