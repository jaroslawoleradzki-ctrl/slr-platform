from __future__ import annotations

import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Protocol, runtime_checkable
from uuid import UUID

from app.domain.corpus_finalization import (
    CorpusFinalization,
    CorpusFinalizationMember,
    CorpusRecordDisposition,
)


@runtime_checkable
class CorpusFinalizationRepository(Protocol):
    """Abstract repository contract for corpus finalization snapshots."""

    def save_finalization(
        self,
        finalization: CorpusFinalization,
        members: list[CorpusFinalizationMember],
        *,
        connection: sqlite3.Connection | None = None,
    ) -> None:
        """Persist a finalization event and all its member records atomically."""
        ...

    def get_latest_finalization(
        self,
        project_id: str,
        *,
        connection: sqlite3.Connection | None = None,
    ) -> CorpusFinalization | None:
        """Retrieve the most recent finalization event for a project."""
        ...

    def get_finalization(
        self,
        project_id: str,
        finalization_id: UUID,
        *,
        connection: sqlite3.Connection | None = None,
    ) -> CorpusFinalization | None:
        """Retrieve a specific finalization event by ID."""
        ...

    def get_finalization_members(
        self,
        finalization_id: UUID,
        *,
        connection: sqlite3.Connection | None = None,
    ) -> list[CorpusFinalizationMember]:
        """List all members captured in a finalization event."""
        ...

    def get_admitted_record_ids(
        self,
        project_id: str,
        *,
        connection: sqlite3.Connection | None = None,
    ) -> set[UUID]:
        """Return canonical record IDs admitted to formal Screening by latest finalization."""
        ...


class SqliteCorpusFinalizationRepository:
    """Durable SQLite storage for corpus finalization snapshots."""

    def __init__(self, database_path: str | Path) -> None:
        self._database_path = Path(database_path)
        self._database_path.parent.mkdir(parents=True, exist_ok=True)
        self._apply_migrations()

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
            applied = {row[0] for row in connection.execute("SELECT version FROM schema_migrations").fetchall()}
            for migration in sorted(migration_directory.glob("*.sql")):
                if migration.name in applied:
                    continue
                connection.executescript(migration.read_text(encoding="utf-8"))
                connection.execute(
                    "INSERT INTO schema_migrations(version) VALUES (?)",
                    (migration.name,),
                )

    def save_finalization(
        self,
        finalization: CorpusFinalization,
        members: list[CorpusFinalizationMember],
        *,
        connection: sqlite3.Connection | None = None,
    ) -> None:
        def execute(conn: sqlite3.Connection) -> None:
            conn.execute(
                """
                INSERT INTO corpus_finalizations (
                    finalization_id, project_id, finalized_by, created_at,
                    source_records_count, duplicates_removed_count,
                    prescreening_removed_count, retained_count, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(finalization.finalization_id),
                    finalization.project_id,
                    finalization.finalized_by,
                    finalization.created_at.isoformat(),
                    finalization.source_records_count,
                    finalization.duplicates_removed_count,
                    finalization.prescreening_removed_count,
                    finalization.retained_count,
                    finalization.status,
                ),
            )
            for m in members:
                conn.execute(
                    """
                    INSERT INTO corpus_finalization_members (
                        finalization_id, record_id, disposition,
                        removal_reason, admitted_to_screening, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(m.finalization_id),
                        str(m.record_id),
                        m.disposition.value,
                        m.removal_reason,
                        1 if m.admitted_to_screening else 0,
                        finalization.created_at.isoformat(),
                    ),
                )

        if connection is not None:
            execute(connection)
        else:
            with self._connect() as conn:
                execute(conn)

    def get_latest_finalization(
        self,
        project_id: str,
        *,
        connection: sqlite3.Connection | None = None,
    ) -> CorpusFinalization | None:
        def query(conn: sqlite3.Connection) -> CorpusFinalization | None:
            row = conn.execute(
                """
                SELECT
                    finalization_id, project_id, finalized_by, created_at,
                    source_records_count, duplicates_removed_count,
                    prescreening_removed_count, retained_count, status
                FROM corpus_finalizations
                WHERE project_id = ?
                ORDER BY created_at DESC, rowid DESC
                LIMIT 1
                """,
                (project_id,),
            ).fetchone()
            if row is None:
                return None
            return CorpusFinalization(
                finalization_id=UUID(row[0]),
                project_id=row[1],
                finalized_by=row[2],
                created_at=datetime.fromisoformat(row[3]),
                source_records_count=int(row[4]),
                duplicates_removed_count=int(row[5]),
                prescreening_removed_count=int(row[6]),
                retained_count=int(row[7]),
                status=row[8],
            )

        if connection is not None:
            return query(connection)
        with self._connect() as conn:
            return query(conn)

    def get_finalization(
        self,
        project_id: str,
        finalization_id: UUID,
        *,
        connection: sqlite3.Connection | None = None,
    ) -> CorpusFinalization | None:
        def query(conn: sqlite3.Connection) -> CorpusFinalization | None:
            row = conn.execute(
                """
                SELECT
                    finalization_id, project_id, finalized_by, created_at,
                    source_records_count, duplicates_removed_count,
                    prescreening_removed_count, retained_count, status
                FROM corpus_finalizations
                WHERE project_id = ? AND finalization_id = ?
                LIMIT 1
                """,
                (project_id, str(finalization_id)),
            ).fetchone()
            if row is None:
                return None
            return CorpusFinalization(
                finalization_id=UUID(row[0]),
                project_id=row[1],
                finalized_by=row[2],
                created_at=datetime.fromisoformat(row[3]),
                source_records_count=int(row[4]),
                duplicates_removed_count=int(row[5]),
                prescreening_removed_count=int(row[6]),
                retained_count=int(row[7]),
                status=row[8],
            )

        if connection is not None:
            return query(connection)
        with self._connect() as conn:
            return query(conn)

    def get_finalization_members(
        self,
        finalization_id: UUID,
        *,
        connection: sqlite3.Connection | None = None,
    ) -> list[CorpusFinalizationMember]:
        def query(conn: sqlite3.Connection) -> list[CorpusFinalizationMember]:
            rows = conn.execute(
                """
                SELECT
                    finalization_id, record_id, disposition,
                    removal_reason, admitted_to_screening
                FROM corpus_finalization_members
                WHERE finalization_id = ?
                ORDER BY rowid ASC
                """,
                (str(finalization_id),),
            ).fetchall()
            return [
                CorpusFinalizationMember(
                    finalization_id=UUID(r[0]),
                    record_id=UUID(r[1]),
                    disposition=CorpusRecordDisposition(r[2]),
                    removal_reason=r[3],
                    admitted_to_screening=bool(r[4]),
                )
                for r in rows
            ]

        if connection is not None:
            return query(connection)
        with self._connect() as conn:
            return query(conn)

    def get_admitted_record_ids(
        self,
        project_id: str,
        *,
        connection: sqlite3.Connection | None = None,
    ) -> set[UUID]:
        def query(conn: sqlite3.Connection) -> set[UUID]:
            latest = self.get_latest_finalization(project_id, connection=conn)
            if latest is None:
                return set()
            rows = conn.execute(
                """
                SELECT record_id
                FROM corpus_finalization_members
                WHERE finalization_id = ? AND admitted_to_screening = 1
                """,
                (str(latest.finalization_id),),
            ).fetchall()
            return {UUID(r[0]) for r in rows}

        if connection is not None:
            return query(connection)
        with self._connect() as conn:
            return query(conn)


class InMemoryCorpusFinalizationRepository:
    """In-memory implementation for unit tests."""

    def __init__(self) -> None:
        self._finalizations: dict[str, list[CorpusFinalization]] = {}
        self._members: dict[UUID, list[CorpusFinalizationMember]] = {}

    def save_finalization(
        self,
        finalization: CorpusFinalization,
        members: list[CorpusFinalizationMember],
        *,
        connection: sqlite3.Connection | None = None,
    ) -> None:
        self._finalizations.setdefault(finalization.project_id, []).append(finalization)
        self._members[finalization.finalization_id] = list(members)

    def get_latest_finalization(
        self,
        project_id: str,
        *,
        connection: sqlite3.Connection | None = None,
    ) -> CorpusFinalization | None:
        events = self._finalizations.get(project_id, [])
        return events[-1] if events else None

    def get_finalization(
        self,
        project_id: str,
        finalization_id: UUID,
        *,
        connection: sqlite3.Connection | None = None,
    ) -> CorpusFinalization | None:
        for ev in self._finalizations.get(project_id, []):
            if ev.finalization_id == finalization_id:
                return ev
        return None

    def get_finalization_members(
        self,
        finalization_id: UUID,
        *,
        connection: sqlite3.Connection | None = None,
    ) -> list[CorpusFinalizationMember]:
        return list(self._members.get(finalization_id, []))

    def get_admitted_record_ids(
        self,
        project_id: str,
        *,
        connection: sqlite3.Connection | None = None,
    ) -> set[UUID]:
        latest = self.get_latest_finalization(project_id)
        if latest is None:
            return set()
        members = self._members.get(latest.finalization_id, [])
        return {m.record_id for m in members if m.admitted_to_screening}


def default_corpus_finalization_repository() -> SqliteCorpusFinalizationRepository:
    path = os.environ.get("SLR_DATABASE_PATH", "data/slr-platform.db")
    return SqliteCorpusFinalizationRepository(path)
