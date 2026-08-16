"""Repository for Phase 10: Research Gap Synthesis Persistence (Task 10.6)."""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _as_datetime(val: str | None) -> datetime | None:
    """Converts a database string or datetime to a timezone-aware datetime."""
    if not val:
        return None
    try:
        dt = datetime.fromisoformat(val)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


class SqliteSynthesisGapRepository:
    """SQLite implementation for persisting research gaps and their evidence links."""

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
    # Research Gap Operations
    # ==========================================

    def create_gap(
        self,
        gap_id: str,
        project_id: str,
        gap_type: str,
        title: str,
        rationale: str,
        researcher_id: str,
        connection: Any = None,
    ) -> dict:
        conn = self._get_connection(connection)
        close_conn = connection is None
        now = datetime.now(timezone.utc).isoformat()
        try:
            conn.execute(
                """
                INSERT INTO synthesis_research_gaps (
                    project_id, gap_id, gap_type, title, rationale, researcher_id, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (project_id, gap_id, gap_type, title, rationale, researcher_id, now, now),
            )
            if close_conn:
                conn.commit()
            return {
                "gap_id": gap_id,
                "project_id": project_id,
                "gap_type": gap_type,
                "title": title,
                "rationale": rationale,
                "researcher_id": researcher_id,
                "created_at": _as_datetime(now) or datetime.now(timezone.utc),
                "updated_at": _as_datetime(now) or datetime.now(timezone.utc),
            }
        finally:
            if close_conn:
                conn.close()

    def get_gap(self, project_id: str, gap_id: str, connection: Any = None) -> dict | None:
        conn = self._get_connection(connection)
        close_conn = connection is None
        try:
            cursor = conn.execute(
                """
                SELECT project_id, gap_id, gap_type, title, rationale, researcher_id, created_at, updated_at
                FROM synthesis_research_gaps
                WHERE project_id = ? AND gap_id = ?;
                """,
                (project_id, gap_id),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            return {
                "gap_id": row[1],
                "project_id": row[0],
                "gap_type": row[2],
                "title": row[3],
                "rationale": row[4],
                "researcher_id": row[5],
                "created_at": _as_datetime(row[6]) or datetime.now(timezone.utc),
                "updated_at": _as_datetime(row[7]) or datetime.now(timezone.utc),
            }
        finally:
            if close_conn:
                conn.close()

    def list_gaps(self, project_id: str, connection: Any = None) -> list[dict]:
        conn = self._get_connection(connection)
        close_conn = connection is None
        try:
            cursor = conn.execute(
                """
                SELECT project_id, gap_id, gap_type, title, rationale, researcher_id, created_at, updated_at
                FROM synthesis_research_gaps
                WHERE project_id = ?
                ORDER BY created_at ASC, gap_id ASC;
                """,
                (project_id,),
            )
            return [
                {
                    "gap_id": row[1],
                    "project_id": row[0],
                    "gap_type": row[2],
                    "title": row[3],
                    "rationale": row[4],
                    "researcher_id": row[5],
                    "created_at": _as_datetime(row[6]) or datetime.now(timezone.utc),
                    "updated_at": _as_datetime(row[7]) or datetime.now(timezone.utc),
                }
                for row in cursor.fetchall()
            ]
        finally:
            if close_conn:
                conn.close()

    def list_gaps_by_type(self, project_id: str, gap_type: str, connection: Any = None) -> list[dict]:
        conn = self._get_connection(connection)
        close_conn = connection is None
        try:
            cursor = conn.execute(
                """
                SELECT project_id, gap_id, gap_type, title, rationale, researcher_id, created_at, updated_at
                FROM synthesis_research_gaps
                WHERE project_id = ? AND gap_type = ?
                ORDER BY created_at ASC, gap_id ASC;
                """,
                (project_id, gap_type),
            )
            return [
                {
                    "gap_id": row[1],
                    "project_id": row[0],
                    "gap_type": row[2],
                    "title": row[3],
                    "rationale": row[4],
                    "researcher_id": row[5],
                    "created_at": _as_datetime(row[6]) or datetime.now(timezone.utc),
                    "updated_at": _as_datetime(row[7]) or datetime.now(timezone.utc),
                }
                for row in cursor.fetchall()
            ]
        finally:
            if close_conn:
                conn.close()

    def update_gap(
        self,
        project_id: str,
        gap_id: str,
        gap_type: str | None = None,
        title: str | None = None,
        rationale: str | None = None,
        connection: Any = None,
    ) -> dict | None:
        conn = self._get_connection(connection)
        close_conn = connection is None
        try:
            sets: list[str] = []
            params: list[Any] = []

            if gap_type is not None:
                sets.append("gap_type = ?")
                params.append(gap_type)
            if title is not None:
                sets.append("title = ?")
                params.append(title)
            if rationale is not None:
                sets.append("rationale = ?")
                params.append(rationale)
            sets.append("updated_at = ?")
            params.append(datetime.now(timezone.utc).isoformat())
            params.append(project_id)
            params.append(gap_id)

            query = f"""
                UPDATE synthesis_research_gaps
                SET {", ".join(sets)}
                WHERE project_id = ? AND gap_id = ?;
            """
            conn.execute(query, params)
            if close_conn:
                conn.commit()

            return self.get_gap(project_id, gap_id, connection=conn)
        finally:
            if close_conn:
                conn.close()

    def delete_gap(self, project_id: str, gap_id: str, connection: Any = None) -> bool:
        conn = self._get_connection(connection)
        close_conn = connection is None
        try:
            conn.execute(
                "DELETE FROM synthesis_research_gap_links WHERE project_id = ? AND gap_id = ?;",
                (project_id, gap_id),
            )
            cursor = conn.execute(
                "DELETE FROM synthesis_research_gaps WHERE project_id = ? AND gap_id = ?;",
                (project_id, gap_id),
            )
            deleted = cursor.rowcount > 0
            if close_conn:
                conn.commit()
            return deleted
        finally:
            if close_conn:
                conn.close()

    def delete_for_project(self, project_id: str, connection: Any = None) -> None:
        conn = self._get_connection(connection)
        close_conn = connection is None
        try:
            conn.execute(
                "DELETE FROM synthesis_research_gap_links WHERE project_id = ?;",
                (project_id,),
            )
            conn.execute(
                "DELETE FROM synthesis_research_gaps WHERE project_id = ?;",
                (project_id,),
            )
            if close_conn:
                conn.commit()
        finally:
            if close_conn:
                conn.close()

    def count_by_type(self, project_id: str, connection: Any = None) -> dict[str, int]:
        conn = self._get_connection(connection)
        close_conn = connection is None
        try:
            cursor = conn.execute(
                """
                SELECT gap_type, COUNT(*) FROM synthesis_research_gaps
                WHERE project_id = ?
                GROUP BY gap_type;
                """,
                (project_id,),
            )
            counts: dict[str, int] = {}
            for row in cursor.fetchall():
                counts[row[0]] = row[1]
            return counts
        finally:
            if close_conn:
                conn.close()

    # ==========================================
    # Research Gap Link Operations
    # ==========================================

    def _row_to_link(self, row: tuple) -> dict:
        return {
            "link_id": row[0],
            "project_id": row[1],
            "gap_id": row[2],
            "link_type": row[3],
            "target_id": row[4],
            "group_item_id": row[5],
            "publication_id": row[6],
            "latest_revision_id": row[7],
            "created_at": _as_datetime(row[8]) or datetime.now(timezone.utc),
        }

    def add_link(
        self,
        link_id: str,
        project_id: str,
        gap_id: str,
        link_type: str,
        target_id: str,
        group_item_id: str,
        publication_id: str,
        latest_revision_id: str,
        connection: Any = None,
    ) -> dict:
        conn = self._get_connection(connection)
        close_conn = connection is None
        now = datetime.now(timezone.utc).isoformat()
        try:
            conn.execute(
                """
                INSERT INTO synthesis_research_gap_links (
                    link_id, project_id, gap_id, link_type, target_id,
                    group_item_id, publication_id, latest_revision_id, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(project_id, gap_id, link_type, target_id) DO NOTHING;
                """,
                (
                    link_id,
                    project_id,
                    gap_id,
                    link_type,
                    target_id,
                    group_item_id,
                    publication_id,
                    latest_revision_id,
                    now,
                ),
            )
            if close_conn:
                conn.commit()
            existing = self.get_link_by_gap_target(project_id, gap_id, link_type, target_id, connection=conn)
            if existing is None:
                return {
                    "link_id": link_id,
                    "project_id": project_id,
                    "gap_id": gap_id,
                    "link_type": link_type,
                    "target_id": target_id,
                    "group_item_id": group_item_id,
                    "publication_id": publication_id,
                    "latest_revision_id": latest_revision_id,
                    "created_at": _as_datetime(now) or datetime.now(timezone.utc),
                }
            return existing
        finally:
            if close_conn:
                conn.close()

    def get_link(self, link_id: str, connection: Any = None) -> dict | None:
        conn = self._get_connection(connection)
        close_conn = connection is None
        try:
            cursor = conn.execute(
                """
                SELECT link_id, project_id, gap_id, link_type, target_id,
                       group_item_id, publication_id, latest_revision_id, created_at
                FROM synthesis_research_gap_links
                WHERE link_id = ?;
                """,
                (link_id,),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            return self._row_to_link(row)
        finally:
            if close_conn:
                conn.close()

    def get_link_by_gap_target(
        self, project_id: str, gap_id: str, link_type: str, target_id: str, connection: Any = None
    ) -> dict | None:
        conn = self._get_connection(connection)
        close_conn = connection is None
        try:
            cursor = conn.execute(
                """
                SELECT link_id, project_id, gap_id, link_type, target_id,
                       group_item_id, publication_id, latest_revision_id, created_at
                FROM synthesis_research_gap_links
                WHERE project_id = ? AND gap_id = ? AND link_type = ? AND target_id = ?;
                """,
                (project_id, gap_id, link_type, target_id),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            return self._row_to_link(row)
        finally:
            if close_conn:
                conn.close()

    def list_links_for_gap(self, project_id: str, gap_id: str, connection: Any = None) -> list[dict]:
        conn = self._get_connection(connection)
        close_conn = connection is None
        try:
            cursor = conn.execute(
                """
                SELECT link_id, project_id, gap_id, link_type, target_id,
                       group_item_id, publication_id, latest_revision_id, created_at
                FROM synthesis_research_gap_links
                WHERE project_id = ? AND gap_id = ?
                ORDER BY created_at ASC, link_id ASC;
                """,
                (project_id, gap_id),
            )
            return [self._row_to_link(row) for row in cursor.fetchall()]
        finally:
            if close_conn:
                conn.close()

    def list_links_for_target(
        self, project_id: str, link_type: str, target_id: str, connection: Any = None
    ) -> list[dict]:
        conn = self._get_connection(connection)
        close_conn = connection is None
        try:
            cursor = conn.execute(
                """
                SELECT link_id, project_id, gap_id, link_type, target_id,
                       group_item_id, publication_id, latest_revision_id, created_at
                FROM synthesis_research_gap_links
                WHERE project_id = ? AND link_type = ? AND target_id = ?
                ORDER BY created_at ASC, link_id ASC;
                """,
                (project_id, link_type, target_id),
            )
            return [self._row_to_link(row) for row in cursor.fetchall()]
        finally:
            if close_conn:
                conn.close()

    def remove_link(self, link_id: str, connection: Any = None) -> bool:
        conn = self._get_connection(connection)
        close_conn = connection is None
        try:
            cursor = conn.execute(
                "DELETE FROM synthesis_research_gap_links WHERE link_id = ?;",
                (link_id,),
            )
            deleted = cursor.rowcount > 0
            if close_conn:
                conn.commit()
            return deleted
        finally:
            if close_conn:
                conn.close()

    def update_link_latest_revision(
        self, link_id: str, latest_revision_id: str, connection: Any = None
    ) -> dict | None:
        """Advances an existing evidence link to a newer eligible COMPLETE revision.

        The link's logical identity (project/gap/link_type/target) is preserved;
        only the resolved latest COMPLETE revision is updated. Returns the updated
        link row or None when the link does not exist.
        """
        conn = self._get_connection(connection)
        close_conn = connection is None
        try:
            cursor = conn.execute(
                "UPDATE synthesis_research_gap_links SET latest_revision_id = ? WHERE link_id = ?;",
                (latest_revision_id, link_id),
            )
            if close_conn:
                conn.commit()
            if cursor.rowcount == 0:
                return None
            return self.get_link(link_id, connection=conn)
        finally:
            if close_conn:
                conn.close()


def default_synthesis_gap_repository() -> SqliteSynthesisGapRepository:
    return SqliteSynthesisGapRepository()
