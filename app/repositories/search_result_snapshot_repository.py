from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol, runtime_checkable
from uuid import UUID, uuid4

from app.domain.publication import Publication


class SearchResultSnapshotNotFoundError(LookupError):
    """Raised when a project-scoped snapshot does not exist."""


class DuplicateSearchResultSnapshotError(ValueError):
    """Raised when one publication is snapshotted twice in the same search run."""


@dataclass(frozen=True, slots=True)
class SearchResultSnapshot:
    snapshot_id: UUID
    project_id: str
    search_run_id: UUID
    provider: str
    source_id: str
    publication: Publication
    created_at: datetime

    @classmethod
    def create(
        cls,
        *,
        project_id: str,
        search_run_id: UUID,
        provider: str,
        source_id: str,
        publication: Publication,
    ) -> "SearchResultSnapshot":
        matching = any(
            entry.source.casefold() == provider.casefold()
            and entry.source_record_id == source_id
            and entry.run_id == search_run_id
            for entry in publication.provenance
        )
        if not matching:
            raise ValueError("publication lacks provenance matching snapshot search run")
        return cls(
            uuid4(),
            project_id,
            search_run_id,
            provider,
            source_id,
            publication,
            datetime.now(timezone.utc),
        )


@runtime_checkable
class SearchResultSnapshotRepository(Protocol):
    def save(self, snapshot: SearchResultSnapshot) -> SearchResultSnapshot: ...
    def get(self, project_id: str, snapshot_id: UUID) -> SearchResultSnapshot: ...
    def delete_for_project(
        self, project_id: str, *, connection: sqlite3.Connection | None = None
    ) -> None: ...


class SqliteSearchResultSnapshotRepository:
    def __init__(self, database_path: str | Path) -> None:
        self._database_path = Path(database_path)
        self._database_path.parent.mkdir(parents=True, exist_ok=True)
        self._apply_migrations()

    def save(self, snapshot: SearchResultSnapshot) -> SearchResultSnapshot:
        try:
            with sqlite3.connect(self._database_path) as connection:
                connection.execute(
                    """INSERT INTO search_result_snapshots
                    (snapshot_id, project_id, search_run_id, publication_id, provider,
                     source_id, publication_document, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        str(snapshot.snapshot_id),
                        snapshot.project_id,
                        str(snapshot.search_run_id),
                        str(snapshot.publication.record_id),
                        snapshot.provider,
                        snapshot.source_id,
                        json.dumps(snapshot.publication.model_dump(mode="json")),
                        snapshot.created_at.isoformat(),
                    ),
                )
        except sqlite3.IntegrityError as exc:
            raise DuplicateSearchResultSnapshotError(
                "publication already has a snapshot in this project search run"
            ) from exc
        return snapshot

    def get(self, project_id: str, snapshot_id: UUID) -> SearchResultSnapshot:
        with sqlite3.connect(self._database_path) as connection:
            row = connection.execute(
                """SELECT search_run_id, provider, source_id, publication_document,
                          created_at FROM search_result_snapshots
                   WHERE project_id = ? AND snapshot_id = ?""",
                (project_id, str(snapshot_id)),
            ).fetchone()
        if row is None:
            raise SearchResultSnapshotNotFoundError(str(snapshot_id))
        return SearchResultSnapshot(
            snapshot_id,
            project_id,
            UUID(row[0]),
            row[1],
            row[2],
            Publication.model_validate(json.loads(row[3])),
            datetime.fromisoformat(row[4]),
        )

    def delete_for_project(
        self, project_id: str, *, connection: sqlite3.Connection | None = None
    ) -> None:
        if connection is not None:
            connection.execute(
                "DELETE FROM search_result_snapshots WHERE project_id = ?",
                (project_id,),
            )
        else:
            with sqlite3.connect(self._database_path) as conn:
                conn.execute(
                    "DELETE FROM search_result_snapshots WHERE project_id = ?",
                    (project_id,),
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


def default_search_result_snapshot_repository() -> SqliteSearchResultSnapshotRepository:
    return SqliteSearchResultSnapshotRepository(os.environ.get("SLR_DATABASE_PATH", "data/slr-platform.db"))
