"""Durable repository for search run checkpoints (v0.6.7 WP4)."""

from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol, runtime_checkable
from uuid import UUID


@dataclass(frozen=True, slots=True)
class SearchRunCheckpoint:
    search_run_id: UUID
    project_id: str
    job_id: UUID
    provider: str
    cursor: str | None
    pages_fetched: int
    fetched_count: int
    canonical_accepted_count: int
    canonical_rejected_count: int
    canonical_indeterminate_count: int
    deduplicated_count: int
    status: str
    resumable: bool
    plan_metadata: dict[str, Any] | None
    warnings: tuple[str, ...]
    created_at: datetime
    updated_at: datetime


@runtime_checkable
class SearchRunCheckpointRepository(Protocol):
    def save_checkpoint(
        self, checkpoint: SearchRunCheckpoint, *, connection: sqlite3.Connection | None = None
    ) -> None: ...

    def get_checkpoint(
        self, search_run_id: UUID, *, connection: sqlite3.Connection | None = None
    ) -> SearchRunCheckpoint | None: ...

    def get_checkpoints_for_job(
        self, job_id: UUID, *, connection: sqlite3.Connection | None = None
    ) -> list[SearchRunCheckpoint]: ...

    def get_latest_job_checkpoints(
        self, project_id: str, *, connection: sqlite3.Connection | None = None
    ) -> list[SearchRunCheckpoint]: ...

    def get_resumable_checkpoints(
        self, project_id: str, *, connection: sqlite3.Connection | None = None
    ) -> list[SearchRunCheckpoint]: ...

    def delete_for_project(
        self, project_id: str, *, connection: sqlite3.Connection | None = None
    ) -> None: ...


class SqliteSearchRunCheckpointRepository:
    def __init__(self, database_path: Path | str | None = None) -> None:
        self._database_path = (
            Path(database_path)
            if database_path is not None
            else Path(os.environ.get("SLR_DATABASE_PATH", "data/slr-platform.db"))
        )
        self._database_path.parent.mkdir(parents=True, exist_ok=True)
        self._apply_migrations()


    def save_checkpoint(
        self, checkpoint: SearchRunCheckpoint, *, connection: sqlite3.Connection | None = None
    ) -> None:
        if connection is not None:
            self._save_checkpoint_with_conn(connection, checkpoint)
        else:
            with sqlite3.connect(self._database_path) as conn:
                self._save_checkpoint_with_conn(conn, checkpoint)

    def _save_checkpoint_with_conn(
        self, conn: sqlite3.Connection, checkpoint: SearchRunCheckpoint
    ) -> None:
        conn.execute(
            """INSERT INTO search_run_checkpoints (
                search_run_id, project_id, job_id, provider, cursor,
                pages_fetched, fetched_count, canonical_accepted_count,
                canonical_rejected_count, canonical_indeterminate_count,
                deduplicated_count, status, resumable, plan_metadata,
                warnings, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(search_run_id) DO UPDATE SET
                job_id = excluded.job_id,
                cursor = excluded.cursor,
                pages_fetched = excluded.pages_fetched,
                fetched_count = excluded.fetched_count,
                canonical_accepted_count = excluded.canonical_accepted_count,
                canonical_rejected_count = excluded.canonical_rejected_count,
                canonical_indeterminate_count = excluded.canonical_indeterminate_count,
                deduplicated_count = excluded.deduplicated_count,
                status = excluded.status,
                resumable = excluded.resumable,
                plan_metadata = excluded.plan_metadata,
                warnings = excluded.warnings,
                updated_at = excluded.updated_at""",

            (
                str(checkpoint.search_run_id),
                checkpoint.project_id,
                str(checkpoint.job_id),
                checkpoint.provider,
                checkpoint.cursor,
                checkpoint.pages_fetched,
                checkpoint.fetched_count,
                checkpoint.canonical_accepted_count,
                checkpoint.canonical_rejected_count,
                checkpoint.canonical_indeterminate_count,
                checkpoint.deduplicated_count,
                checkpoint.status,
                1 if checkpoint.resumable else 0,
                json.dumps(checkpoint.plan_metadata) if checkpoint.plan_metadata is not None else None,
                json.dumps(list(checkpoint.warnings)),
                checkpoint.created_at.isoformat(),
                checkpoint.updated_at.isoformat(),
            ),
        )

    def get_checkpoint(
        self, search_run_id: UUID, *, connection: sqlite3.Connection | None = None
    ) -> SearchRunCheckpoint | None:
        if connection is not None:
            return self._get_checkpoint_with_conn(connection, search_run_id)
        with sqlite3.connect(self._database_path) as conn:
            return self._get_checkpoint_with_conn(conn, search_run_id)

    def _get_checkpoint_with_conn(
        self, conn: sqlite3.Connection, search_run_id: UUID
    ) -> SearchRunCheckpoint | None:
        cursor = conn.execute(
            """SELECT search_run_id, project_id, job_id, provider, cursor,
                      pages_fetched, fetched_count, canonical_accepted_count,
                      canonical_rejected_count, canonical_indeterminate_count,
                      deduplicated_count, status, resumable, plan_metadata,
                      warnings, created_at, updated_at
               FROM search_run_checkpoints WHERE search_run_id = ?""",
            (str(search_run_id),),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return self._map_row(row)

    def get_checkpoints_for_job(
        self, job_id: UUID, *, connection: sqlite3.Connection | None = None
    ) -> list[SearchRunCheckpoint]:
        if connection is not None:
            return self._get_checkpoints_for_job_with_conn(connection, job_id)
        with sqlite3.connect(self._database_path) as conn:
            return self._get_checkpoints_for_job_with_conn(conn, job_id)

    def _get_checkpoints_for_job_with_conn(
        self, conn: sqlite3.Connection, job_id: UUID
    ) -> list[SearchRunCheckpoint]:
        cursor = conn.execute(
            """SELECT search_run_id, project_id, job_id, provider, cursor,
                      pages_fetched, fetched_count, canonical_accepted_count,
                      canonical_rejected_count, canonical_indeterminate_count,
                      deduplicated_count, status, resumable, plan_metadata,
                      warnings, created_at, updated_at
               FROM search_run_checkpoints WHERE job_id = ?
               ORDER BY provider ASC""",
            (str(job_id),),
        )
        return [self._map_row(row) for row in cursor.fetchall()]

    def get_latest_job_checkpoints(
        self, project_id: str, *, connection: sqlite3.Connection | None = None
    ) -> list[SearchRunCheckpoint]:
        if connection is not None:
            return self._get_latest_job_checkpoints_with_conn(connection, project_id)
        with sqlite3.connect(self._database_path) as conn:
            return self._get_latest_job_checkpoints_with_conn(conn, project_id)

    def _get_latest_job_checkpoints_with_conn(
        self, conn: sqlite3.Connection, project_id: str
    ) -> list[SearchRunCheckpoint]:
        # Find the latest job_id for this project
        cursor = conn.execute(
            """SELECT job_id FROM search_run_checkpoints
               WHERE project_id = ?
               GROUP BY job_id
               ORDER BY MAX(updated_at) DESC LIMIT 1""",
            (project_id,),
        )
        row = cursor.fetchone()
        if row is None:
            return []
        latest_job_id = UUID(row[0])
        return self._get_checkpoints_for_job_with_conn(conn, latest_job_id)

    def get_resumable_checkpoints(
        self, project_id: str, *, connection: sqlite3.Connection | None = None
    ) -> list[SearchRunCheckpoint]:
        if connection is not None:
            return self._get_resumable_checkpoints_with_conn(connection, project_id)
        with sqlite3.connect(self._database_path) as conn:
            return self._get_resumable_checkpoints_with_conn(conn, project_id)

    def _get_resumable_checkpoints_with_conn(
        self, conn: sqlite3.Connection, project_id: str
    ) -> list[SearchRunCheckpoint]:
        cursor = conn.execute(
            """SELECT search_run_id, project_id, job_id, provider, cursor,
                      pages_fetched, fetched_count, canonical_accepted_count,
                      canonical_rejected_count, canonical_indeterminate_count,
                      deduplicated_count, status, resumable, plan_metadata,
                      warnings, created_at, updated_at
               FROM search_run_checkpoints
               WHERE project_id = ? AND resumable = 1 AND status IN ('pending', 'running', 'partial', 'cancelled', 'failed')
               ORDER BY updated_at DESC, provider ASC""",
            (project_id,),
        )
        return [self._map_row(row) for row in cursor.fetchall()]

    def delete_for_project(
        self, project_id: str, *, connection: sqlite3.Connection | None = None
    ) -> None:
        if connection is not None:
            connection.execute(
                "DELETE FROM search_run_checkpoints WHERE project_id = ?",
                (project_id,),
            )
        else:
            with sqlite3.connect(self._database_path) as conn:
                conn.execute(
                    "DELETE FROM search_run_checkpoints WHERE project_id = ?",
                    (project_id,),
                )

    def _map_row(self, row: tuple[Any, ...]) -> SearchRunCheckpoint:
        return SearchRunCheckpoint(
            search_run_id=UUID(row[0]),
            project_id=row[1],
            job_id=UUID(row[2]),
            provider=row[3],
            cursor=row[4],
            pages_fetched=row[5],
            fetched_count=row[6],
            canonical_accepted_count=row[7],
            canonical_rejected_count=row[8],
            canonical_indeterminate_count=row[9],
            deduplicated_count=row[10],
            status=row[11],
            resumable=bool(row[12]),
            plan_metadata=json.loads(row[13]) if row[13] is not None else None,
            warnings=tuple(json.loads(row[14])) if row[14] is not None else (),
            created_at=datetime.fromisoformat(row[15]),
            updated_at=datetime.fromisoformat(row[16]),
        )

    def _apply_migrations(self) -> None:
        migration_directory = Path(__file__).parents[2] / "migrations"
        with sqlite3.connect(self._database_path) as connection:
            connection.execute(
                """CREATE TABLE IF NOT EXISTS schema_migrations (
                    version TEXT PRIMARY KEY,
                    applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )"""
            )
            applied = {row[0] for row in connection.execute("SELECT version FROM schema_migrations")}
            for migration in sorted(migration_directory.glob("*.sql")):
                if migration.name not in applied:
                    connection.executescript(migration.read_text(encoding="utf-8"))
                    connection.execute(
                        "INSERT INTO schema_migrations(version) VALUES (?)",
                        (migration.name,),
                    )


def default_search_run_checkpoint_repository() -> SqliteSearchRunCheckpointRepository:
    return SqliteSearchRunCheckpointRepository()
