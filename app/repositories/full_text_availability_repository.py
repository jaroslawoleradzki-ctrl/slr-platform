from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Protocol, runtime_checkable
from uuid import UUID

from app.domain.full_text_screening import FullTextAvailability, FullTextAvailabilityStatus


@runtime_checkable
class FullTextAvailabilityRepository(Protocol):
    def get(self, project_id: str, publication_id: UUID) -> FullTextAvailability | None: ...
    def save(self, availability: FullTextAvailability) -> FullTextAvailability: ...
    def list_by_project(self, project_id: str) -> list[FullTextAvailability]: ...
    def delete_for_project(
        self, project_id: str, *, connection: sqlite3.Connection | None = None
    ) -> None: ...


class SqliteFullTextAvailabilityRepository:
    def __init__(self, database_path: str | Path) -> None:
        self._database_path = Path(database_path)
        self._database_path.parent.mkdir(parents=True, exist_ok=True)
        self._apply_migrations()

    def get(self, project_id: str, publication_id: UUID) -> FullTextAvailability | None:
        with self._connect() as conn:
            row = conn.execute(
                """SELECT status, external_url, notes FROM full_text_availability
                   WHERE project_id = ? AND publication_id = ?""",
                (project_id, str(publication_id)),
            ).fetchone()
        if row is None:
            return None
        return FullTextAvailability(
            project_id=project_id,
            publication_id=publication_id,
            status=FullTextAvailabilityStatus(row[0]),
            external_url=row[1],
            notes=row[2],
        )

    def save(self, availability: FullTextAvailability) -> FullTextAvailability:
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO full_text_availability
                    (project_id, publication_id, status, external_url, notes, updated_at)
                   VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                   ON CONFLICT(project_id, publication_id) DO UPDATE SET
                     status = excluded.status,
                     external_url = excluded.external_url,
                     notes = excluded.notes,
                     updated_at = CURRENT_TIMESTAMP""",
                (
                    availability.project_id,
                    str(availability.publication_id),
                    availability.status.value,
                    availability.external_url,
                    availability.notes,
                ),
            )
        return availability

    def list_by_project(self, project_id: str) -> list[FullTextAvailability]:
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT publication_id, status, external_url, notes FROM full_text_availability
                   WHERE project_id = ? ORDER BY publication_id ASC""",
                (project_id,),
            ).fetchall()
        return [
            FullTextAvailability(
                project_id=project_id, publication_id=UUID(row[0]),
                status=FullTextAvailabilityStatus(row[1]), external_url=row[2], notes=row[3],
            )
            for row in rows
        ]

    def delete_for_project(
        self, project_id: str, *, connection: sqlite3.Connection | None = None
    ) -> None:
        if connection is not None:
            connection.execute("DELETE FROM full_text_availability WHERE project_id = ?", (project_id,))
        else:
            with self._connect() as conn:
                conn.execute("DELETE FROM full_text_availability WHERE project_id = ?", (project_id,))

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._database_path)

    def _apply_migrations(self) -> None:
        migrations = Path(__file__).parents[2] / "migrations"
        with self._connect() as conn:
            conn.execute(
                """CREATE TABLE IF NOT EXISTS schema_migrations (
                    version TEXT PRIMARY KEY,
                    applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )"""
            )
            applied = {row[0] for row in conn.execute("SELECT version FROM schema_migrations")}
            for migration in sorted(migrations.glob("*.sql")):
                if migration.name not in applied:
                    conn.executescript(migration.read_text(encoding="utf-8"))
                    conn.execute("INSERT INTO schema_migrations(version) VALUES (?)", (migration.name,))


def default_full_text_availability_repository() -> SqliteFullTextAvailabilityRepository:
    return SqliteFullTextAvailabilityRepository(
        os.environ.get("SLR_DATABASE_PATH", "data/slr-platform.db")
    )
