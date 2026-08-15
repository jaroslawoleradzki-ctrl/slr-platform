"""Repository for Phase 10: Context Synthesis Persistence (Task 10.5)."""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID


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


class SqliteSynthesisContextRepository:
    """SQLite implementation for persisting context categories and relation context links."""

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
    # Context Category Operations
    # ==========================================

    def create_category(
        self, category_id: str, name: str, project_id: str, description: str | None = None,
        display_order: int = 0, connection: Any = None
    ) -> dict:
        conn = self._get_connection(connection)
        close_conn = connection is None
        try:
            conn.execute(
                """
                INSERT INTO synthesis_context_categories (
                    project_id, category_id, name, description, display_order, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    project_id,
                    category_id,
                    name,
                    description,
                    display_order,
                    datetime.now(timezone.utc).isoformat(),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            if close_conn:
                conn.commit()
            return {
                "category_id": category_id,
                "name": name,
                "project_id": project_id,
                "description": description,
                "display_order": display_order,
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            }
        finally:
            if close_conn:
                conn.close()

    def get_category(
        self, project_id: str, category_id: str, connection: Any = None
    ) -> dict | None:
        conn = self._get_connection(connection)
        close_conn = connection is None
        try:
            cursor = conn.execute(
                """
                SELECT category_id, name, project_id, description, display_order, created_at, updated_at
                FROM synthesis_context_categories
                WHERE project_id = ? AND category_id = ?;
                """,
                (project_id, category_id),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            return {
                "category_id": row[0],
                "name": row[1],
                "project_id": row[2],
                "description": row[3],
                "display_order": row[4],
                "created_at": _as_datetime(row[5]) or datetime.now(timezone.utc),
                "updated_at": _as_datetime(row[6]) or datetime.now(timezone.utc),
            }
        finally:
            if close_conn:
                conn.close()

    def list_categories(self, project_id: str, connection: Any = None) -> list[dict]:
        conn = self._get_connection(connection)
        close_conn = connection is None
        try:
            cursor = conn.execute(
                """
                SELECT category_id, name, project_id, description, display_order, created_at, updated_at
                FROM synthesis_context_categories
                WHERE project_id = ?
                ORDER BY display_order ASC, name ASC;
                """,
                (project_id,),
            )
            return [
                {
                    "category_id": row[0],
                    "name": row[1],
                    "project_id": row[2],
                    "description": row[3],
                    "display_order": row[4],
                    "created_at": _as_datetime(row[5]) or datetime.now(timezone.utc),
                    "updated_at": _as_datetime(row[6]) or datetime.now(timezone.utc),
                }
                for row in cursor.fetchall()
            ]
        finally:
            if close_conn:
                conn.close()

    def update_category(
        self, project_id: str, category_id: str, name: str | None = None,
        description: str | None = None,
        display_order: int | None = None, connection: Any = None
    ) -> dict | None:
        conn = self._get_connection(connection)
        close_conn = connection is None
        try:
            # Build dynamic update
            sets: list[str] = []
            params: list[Any] = []

            if description is not None:
                sets.append("description = ?")
                params.append(description)
            if name is not None:
                sets.append("name = ?")
                params.append(name)
            if display_order is not None:
                sets.append("display_order = ?")
                params.append(display_order)
            sets.append("updated_at = ?")
            params.append(datetime.now(timezone.utc).isoformat())
            params.append(project_id)
            params.append(category_id)

            query = f"""
                UPDATE synthesis_context_categories
                SET {", ".join(sets)}
                WHERE project_id = ? AND category_id = ?;
            """
            conn.execute(query, params)
            if close_conn:
                conn.commit()

            # Return updated category
            return self.get_category(project_id, category_id, connection=conn)
        finally:
            if close_conn:
                conn.close()

    def delete_category(
        self, project_id: str, category_id: str, connection: Any = None
    ) -> bool:
        conn = self._get_connection(connection)
        close_conn = connection is None
        try:
            # First, unlink any context links referencing this category
            conn.execute(
                """
                UPDATE synthesis_relation_context_links
                SET analytical_context_category_id = NULL, updated_at = CURRENT_TIMESTAMP
                WHERE project_id = ? AND analytical_context_category_id = ?;
                """,
                (project_id, category_id),
            )
            cursor = conn.execute(
                "DELETE FROM synthesis_context_categories WHERE project_id = ? AND category_id = ?;",
                (project_id, category_id),
            )
            deleted = cursor.rowcount > 0
            if close_conn:
                conn.commit()
            return deleted
        finally:
            if close_conn:
                conn.close()

    # ==========================================
    # Context Relation Link Operations
    # ==========================================

    def _row_to_link(self, row: tuple) -> dict:
        return {
            "link_id": row[0],
            "project_id": row[1],
            "analytical_relation_id": row[2],
            "group_item_id": row[3],
            "publication_id": row[4],
            "latest_revision_id": row[5],
            "source_context_text": row[6],
            "analytical_context_category_id": row[7],
            "context_impact": row[8],
            "approval_state": row[9],
            "approved_by": row[10],
            "approved_at": _as_datetime(row[11]),
            "notes": row[12],
            "created_at": _as_datetime(row[13]) or datetime.now(timezone.utc),
            "updated_at": _as_datetime(row[14]) or datetime.now(timezone.utc),
        }

    def create_link(
        self,
        link_id: str,
        project_id: str,
        analytical_relation_id: str,
        group_item_id: str,
        publication_id: str,
        latest_revision_id: str,
        source_context_text: str,
        analytical_context_category_id: str | None = None,
        context_impact: str = "ENABLE",
        approval_state: str = "pending",
        approved_by: str | None = None,
        approved_at: datetime | str | None = None,
        notes: str | None = None,
        connection: Any = None,
    ) -> dict | None:
        conn = self._get_connection(connection)
        close_conn = connection is None
        try:
            if approved_at is None and approved_by is not None and approval_state == "approved":
                formatted_approved_at: str | None = datetime.now(timezone.utc).isoformat()
            elif isinstance(approved_at, datetime):
                formatted_approved_at = approved_at.isoformat()
            elif isinstance(approved_at, str):
                formatted_approved_at = approved_at
            else:
                formatted_approved_at = None

            conn.execute(
                """
                INSERT INTO synthesis_relation_context_links (
                    link_id, project_id, analytical_relation_id, group_item_id,
                    publication_id, latest_revision_id, source_context_text,
                    analytical_context_category_id, context_impact, approval_state, approved_by, approved_at, notes, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(project_id, analytical_relation_id) DO UPDATE SET
                    group_item_id = excluded.group_item_id,
                    publication_id = excluded.publication_id,
                    latest_revision_id = excluded.latest_revision_id,
                    source_context_text = excluded.source_context_text,
                    analytical_context_category_id = excluded.analytical_context_category_id,
                    context_impact = excluded.context_impact,
                    approval_state = excluded.approval_state,
                    approved_by = excluded.approved_by,
                    approved_at = excluded.approved_at,
                    notes = excluded.notes,
                    updated_at = excluded.updated_at;
                """,
                (
                    link_id,
                    project_id,
                    analytical_relation_id,
                    group_item_id,
                    publication_id,
                    latest_revision_id,
                    source_context_text,
                    analytical_context_category_id,
                    context_impact,
                    approval_state,
                    approved_by,
                    formatted_approved_at,
                    notes,
                    datetime.now(timezone.utc).isoformat(),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            if close_conn:
                conn.commit()
            return self.get_link_by_relation(project_id, analytical_relation_id, connection=conn)
        finally:
            if close_conn:
                conn.close()

    def get_link(self, link_id: str, connection: Any = None) -> dict | None:
        conn = self._get_connection(connection)
        close_conn = connection is None
        try:
            cursor = conn.execute(
                """
                SELECT link_id, project_id, analytical_relation_id, group_item_id,
                       publication_id, latest_revision_id, source_context_text,
                       analytical_context_category_id, context_impact, approval_state, approved_by, approved_at, notes,
                       created_at, updated_at
                FROM synthesis_relation_context_links
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

    def get_link_by_relation(
        self, project_id: str, analytical_relation_id: str, connection: Any = None
    ) -> dict | None:
        conn = self._get_connection(connection)
        close_conn = connection is None
        try:
            cursor = conn.execute(
                """
                SELECT link_id, project_id, analytical_relation_id, group_item_id,
                       publication_id, latest_revision_id, source_context_text,
                       analytical_context_category_id, context_impact, approval_state, approved_by, approved_at, notes,
                       created_at, updated_at
                FROM synthesis_relation_context_links
                WHERE project_id = ? AND analytical_relation_id = ?;
                """,
                (project_id, analytical_relation_id),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            return self._row_to_link(row)
        finally:
            if close_conn:
                conn.close()

    def get_link_by_group_item(
        self, project_id: str, group_item_id: UUID, connection: Any = None
    ) -> dict | None:
        conn = self._get_connection(connection)
        close_conn = connection is None
        try:
            cursor = conn.execute(
                """
                SELECT link_id, project_id, analytical_relation_id, group_item_id,
                       publication_id, latest_revision_id, source_context_text,
                       analytical_context_category_id, context_impact, approval_state, approved_by, approved_at, notes,
                       created_at, updated_at
                FROM synthesis_relation_context_links
                WHERE project_id = ? AND group_item_id = ?;
                """,
                (project_id, str(group_item_id)),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            return self._row_to_link(row)
        finally:
            if close_conn:
                conn.close()

    def list_links(self, project_id: str, connection: Any = None) -> list[dict]:
        conn = self._get_connection(connection)
        close_conn = connection is None
        try:
            cursor = conn.execute(
                """
                SELECT link_id, project_id, analytical_relation_id, group_item_id,
                       publication_id, latest_revision_id, source_context_text,
                       analytical_context_category_id, context_impact, approval_state, approved_by, approved_at, notes,
                       created_at, updated_at
                FROM synthesis_relation_context_links
                WHERE project_id = ?
                ORDER BY created_at ASC;
                """,
                (project_id,),
            )
            return [self._row_to_link(row) for row in cursor.fetchall()]
        finally:
            if close_conn:
                conn.close()

    def list_links_by_category(
        self, project_id: str, category_id: str, connection: Any = None
    ) -> list[dict]:
        conn = self._get_connection(connection)
        close_conn = connection is None
        try:
            cursor = conn.execute(
                """
                SELECT link_id, project_id, analytical_relation_id, group_item_id,
                       publication_id, latest_revision_id, source_context_text,
                       analytical_context_category_id, context_impact, approval_state, approved_by, approved_at, notes,
                       created_at, updated_at
                FROM synthesis_relation_context_links
                WHERE project_id = ? AND analytical_context_category_id = ?
                ORDER BY created_at ASC;
                """,
                (project_id, category_id),
            )
            return [self._row_to_link(row) for row in cursor.fetchall()]
        finally:
            if close_conn:
                conn.close()

    def update_link(
        self,
        link_id: str,
        context_impact: str | None = None,
        analytical_context_category_id: str | None = None,
        approval_state: str | None = None,
        approved_by: str | None = None,
        notes: str | None = None,
        connection: Any = None,
    ) -> dict | None:
        conn = self._get_connection(connection)
        close_conn = connection is None
        try:
            sets: list[str] = []
            params: list[Any] = []

            if context_impact is not None:
                sets.append("context_impact = ?")
                params.append(context_impact)
            if analytical_context_category_id is not None:
                sets.append("analytical_context_category_id = ?")
                params.append(analytical_context_category_id)
            if approval_state is not None:
                sets.append("approval_state = ?")
                params.append(approval_state)
            if approved_by is not None:
                sets.append("approved_by = ?")
                params.append(approved_by)
            if notes is not None:
                sets.append("notes = ?")
                params.append(notes)
            sets.append("updated_at = ?")
            params.append(datetime.now(timezone.utc).isoformat())
            params.append(link_id)

            query = f"""
                UPDATE synthesis_relation_context_links
                SET {", ".join(sets)}
                WHERE link_id = ?;
            """
            conn.execute(query, params)
            if close_conn:
                conn.commit()

            return self.get_link(link_id, connection=conn)
        finally:
            if close_conn:
                conn.close()

    def delete_link(self, link_id: str, connection: Any = None) -> bool:
        conn = self._get_connection(connection)
        close_conn = connection is None
        try:
            cursor = conn.execute(
                "DELETE FROM synthesis_relation_context_links WHERE link_id = ?;",
                (link_id,),
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
                "DELETE FROM synthesis_relation_context_links WHERE project_id = ?;",
                (project_id,),
            )
            conn.execute(
                "DELETE FROM synthesis_context_categories WHERE project_id = ?;",
                (project_id,),
            )
            if close_conn:
                conn.commit()
        finally:
            if close_conn:
                conn.close()


def default_synthesis_context_repository() -> SqliteSynthesisContextRepository:
    return SqliteSynthesisContextRepository()
