"""Repository for Phase 10: Synthesis Snapshot Persistence (Task 10.7).

Snapshots are immutable, append-only artifacts: the repository exposes insert
and read operations only. There is deliberately no update method, and no
application-level delete path (snapshots are removed only by project
hard-delete through the ``ON DELETE CASCADE`` foreign key).
"""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.domain.synthesis import SynthesisSnapshot, SynthesisSnapshotContent


def _as_datetime(val: str | None) -> datetime | None:
    if not val:
        return None
    try:
        dt = datetime.fromisoformat(val)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


class SqliteSynthesisSnapshotRepository:
    """SQLite implementation for persisting and reading synthesis snapshots."""

    def __init__(self, db_path: Path | str | None = None) -> None:
        self.db_path = (
            Path(db_path) if db_path is not None else Path(os.environ.get("SLR_DATABASE_PATH", "data/slr-platform.db"))
        )

    def _get_connection(self, connection: Any = None) -> sqlite3.Connection:
        if connection is not None:
            return connection  # type: ignore[no-any-return]
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    # ==========================================
    # Snapshot Operations (append-only)
    # ==========================================

    def save_snapshot(self, snapshot: SynthesisSnapshot, connection: Any = None) -> SynthesisSnapshot:
        """Persists a snapshot. Raises sqlite3.IntegrityError on version conflict.

        The stored content is the serialized, immutable ``content`` payload (not
        a reference to any live synthesis state).
        """
        conn = self._get_connection(connection)
        close_conn = connection is None
        try:
            conn.execute(
                """
                INSERT INTO synthesis_snapshots (
                    snapshot_id, project_id, version, actor,
                    extraction_dataset_hash, classification_version,
                    content_hash, content_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    str(snapshot.snapshot_id),
                    snapshot.project_id,
                    snapshot.version,
                    snapshot.actor,
                    snapshot.extraction_dataset_hash,
                    snapshot.classification_version,
                    snapshot.content_hash,
                    snapshot.content.model_dump_json(),
                    snapshot.created_at.isoformat(),
                ),
            )
            if close_conn:
                conn.commit()
            return snapshot
        finally:
            if close_conn:
                conn.close()

    def get_snapshot(self, project_id: str, snapshot_id: str, connection: Any = None) -> SynthesisSnapshot | None:
        """Retrieves a snapshot by its snapshot_id within a project."""
        conn = self._get_connection(connection)
        close_conn = connection is None
        try:
            cursor = conn.execute(
                """
                SELECT snapshot_id, project_id, version, actor,
                       extraction_dataset_hash, classification_version,
                       content_hash, content_json, created_at
                FROM synthesis_snapshots
                WHERE project_id = ? AND snapshot_id = ?;
                """,
                (project_id, snapshot_id),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            return self._row_to_snapshot(row)
        finally:
            if close_conn:
                conn.close()

    def get_snapshot_by_version(self, project_id: str, version: int, connection: Any = None) -> SynthesisSnapshot | None:
        """Retrieves a snapshot by its project-scoped version number."""
        conn = self._get_connection(connection)
        close_conn = connection is None
        try:
            cursor = conn.execute(
                """
                SELECT snapshot_id, project_id, version, actor,
                       extraction_dataset_hash, classification_version,
                       content_hash, content_json, created_at
                FROM synthesis_snapshots
                WHERE project_id = ? AND version = ?;
                """,
                (project_id, version),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            return self._row_to_snapshot(row)
        finally:
            if close_conn:
                conn.close()

    def list_snapshots(self, project_id: str, connection: Any = None) -> list[SynthesisSnapshot]:
        """Lists snapshots for a project ordered by version ascending."""
        conn = self._get_connection(connection)
        close_conn = connection is None
        try:
            cursor = conn.execute(
                """
                SELECT snapshot_id, project_id, version, actor,
                       extraction_dataset_hash, classification_version,
                       content_hash, content_json, created_at
                FROM synthesis_snapshots
                WHERE project_id = ?
                ORDER BY version ASC;
                """,
                (project_id,),
            )
            return [self._row_to_snapshot(row) for row in cursor.fetchall()]
        finally:
            if close_conn:
                conn.close()

    def delete_for_project(self, project_id: str, connection: Any = None) -> None:
        """Deletes all snapshots for a project (project lifecycle cleanup)."""
        conn = self._get_connection(connection)
        close_conn = connection is None
        try:
            conn.execute("DELETE FROM synthesis_snapshots WHERE project_id = ?;", (project_id,))
            if close_conn:
                conn.commit()
        finally:
            if close_conn:
                conn.close()

    @staticmethod
    def _row_to_snapshot(row: tuple) -> SynthesisSnapshot:
        content_json = row[7]
        content_dict = json.loads(content_json)
        return SynthesisSnapshot(
            snapshot_id=row[0],
            project_id=row[1],
            version=row[2],
            actor=row[3],
            extraction_dataset_hash=row[4],
            classification_version=row[5],
            content_hash=row[6],
            content=SynthesisSnapshotContent.model_validate(content_dict),
            created_at=_as_datetime(row[8]) or datetime.now(timezone.utc),
        )


def default_synthesis_snapshot_repository() -> SqliteSynthesisSnapshotRepository:
    """Returns the default project-scoped snapshot repository singleton."""
    return SqliteSynthesisSnapshotRepository()
