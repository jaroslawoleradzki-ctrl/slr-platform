"""Phase 10: SQLite Repository for Mechanism Synthesis Persistence (Task 10.4)."""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

from app.domain.synthesis import (
    AnalyticalMechanismCategory,
    ClassificationApprovalState,
    MechanismPathway,
)


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


class SqliteSynthesisMechanismRepository:
    """SQLite implementation for persisting mechanism categories and pathways."""

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
    # Mechanism Category Operations
    # ==========================================

    def create_category(
        self, category: AnalyticalMechanismCategory, connection: Any = None
    ) -> AnalyticalMechanismCategory:
        conn = self._get_connection(connection)
        close_conn = connection is None
        try:
            conn.execute(
                """
                INSERT INTO synthesis_mechanism_categories (
                    project_id, category_id, name, description, display_order, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    category.project_id,
                    category.category_id,
                    category.name,
                    category.description,
                    category.display_order,
                    category.created_at.isoformat(),
                    category.updated_at.isoformat(),
                ),
            )
            if close_conn:
                conn.commit()
            return category
        finally:
            if close_conn:
                conn.close()

    def get_category(
        self, project_id: str, category_id: str, connection: Any = None
    ) -> AnalyticalMechanismCategory | None:
        conn = self._get_connection(connection)
        close_conn = connection is None
        try:
            cursor = conn.execute(
                """
                SELECT category_id, name, project_id, description, display_order, created_at, updated_at
                FROM synthesis_mechanism_categories
                WHERE project_id = ? AND category_id = ?;
                """,
                (project_id, category_id),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            return AnalyticalMechanismCategory(
                category_id=row[0],
                name=row[1],
                project_id=row[2],
                description=row[3],
                display_order=row[4],
                created_at=_as_datetime(row[5]) or datetime.now(timezone.utc),
                updated_at=_as_datetime(row[6]) or datetime.now(timezone.utc),
            )
        finally:
            if close_conn:
                conn.close()

    def list_categories(self, project_id: str, connection: Any = None) -> list[AnalyticalMechanismCategory]:
        conn = self._get_connection(connection)
        close_conn = connection is None
        try:
            cursor = conn.execute(
                """
                SELECT category_id, name, project_id, description, display_order, created_at, updated_at
                FROM synthesis_mechanism_categories
                WHERE project_id = ?
                ORDER BY display_order ASC, name ASC;
                """,
                (project_id,),
            )
            return [
                AnalyticalMechanismCategory(
                    category_id=row[0],
                    name=row[1],
                    project_id=row[2],
                    description=row[3],
                    display_order=row[4],
                    created_at=_as_datetime(row[5]) or datetime.now(timezone.utc),
                    updated_at=_as_datetime(row[6]) or datetime.now(timezone.utc),
                )
                for row in cursor.fetchall()
            ]
        finally:
            if close_conn:
                conn.close()

    def update_category(
        self, category: AnalyticalMechanismCategory, connection: Any = None
    ) -> AnalyticalMechanismCategory:
        conn = self._get_connection(connection)
        close_conn = connection is None
        try:
            conn.execute(
                """
                UPDATE synthesis_mechanism_categories
                SET name = ?, description = ?, display_order = ?, updated_at = ?
                WHERE project_id = ? AND category_id = ?;
                """,
                (
                    category.name,
                    category.description,
                    category.display_order,
                    category.updated_at.isoformat(),
                    category.project_id,
                    category.category_id,
                ),
            )
            if close_conn:
                conn.commit()
            return category
        finally:
            if close_conn:
                conn.close()

    def delete_category(self, project_id: str, category_id: str, connection: Any = None) -> bool:
        conn = self._get_connection(connection)
        close_conn = connection is None
        try:
            conn.execute(
                """
                UPDATE synthesis_mechanism_pathways
                SET analytical_mechanism_category_id = NULL, updated_at = CURRENT_TIMESTAMP
                WHERE project_id = ? AND analytical_mechanism_category_id = ?;
                """,
                (project_id, category_id),
            )
            cursor = conn.execute(
                "DELETE FROM synthesis_mechanism_categories WHERE project_id = ? AND category_id = ?;",
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
    # Mechanism Pathway Operations
    # ==========================================

    def _row_to_pathway(self, row: Any) -> MechanismPathway:
        return MechanismPathway(
            pathway_id=UUID(row[0]),
            project_id=row[1],
            analytical_relation_id=UUID(row[2]),
            group_item_id=UUID(row[3]),
            publication_id=UUID(row[4]),
            latest_revision_id=UUID(row[5]),
            source_mechanism_text=row[6],
            analytical_mechanism_category_id=row[7],
            is_review_synthesized=bool(row[8]),
            approval_state=ClassificationApprovalState(row[9]),
            approved_by=row[10],
            approved_at=_as_datetime(row[11]),
            notes=row[12],
            created_at=_as_datetime(row[13]) or datetime.now(timezone.utc),
            updated_at=_as_datetime(row[14]) or datetime.now(timezone.utc),
        )

    def save_pathway(self, pathway: MechanismPathway, connection: Any = None) -> MechanismPathway:
        conn = self._get_connection(connection)
        close_conn = connection is None
        try:
            conn.execute(
                """
                INSERT INTO synthesis_mechanism_pathways (
                    pathway_id, project_id, analytical_relation_id, group_item_id,
                    publication_id, latest_revision_id, source_mechanism_text,
                    analytical_mechanism_category_id, is_review_synthesized,
                    approval_state, approved_by, approved_at, notes, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(project_id, analytical_relation_id) DO UPDATE SET
                    group_item_id = excluded.group_item_id,
                    publication_id = excluded.publication_id,
                    latest_revision_id = excluded.latest_revision_id,
                    source_mechanism_text = excluded.source_mechanism_text,
                    analytical_mechanism_category_id = excluded.analytical_mechanism_category_id,
                    is_review_synthesized = excluded.is_review_synthesized,
                    approval_state = excluded.approval_state,
                    approved_by = excluded.approved_by,
                    approved_at = excluded.approved_at,
                    notes = excluded.notes,
                    updated_at = excluded.updated_at;
                """,
                (
                    str(pathway.pathway_id),
                    pathway.project_id,
                    str(pathway.analytical_relation_id),
                    str(pathway.group_item_id),
                    str(pathway.publication_id),
                    str(pathway.latest_revision_id),
                    pathway.source_mechanism_text,
                    pathway.analytical_mechanism_category_id,
                    1 if pathway.is_review_synthesized else 0,
                    pathway.approval_state.value,
                    pathway.approved_by,
                    pathway.approved_at.isoformat() if pathway.approved_at else None,
                    pathway.notes,
                    pathway.created_at.isoformat(),
                    pathway.updated_at.isoformat(),
                ),
            )
            if close_conn:
                conn.commit()
            return pathway
        finally:
            if close_conn:
                conn.close()

    def save_pathways(self, pathways: list[MechanismPathway], connection: Any = None) -> list[MechanismPathway]:
        conn = self._get_connection(connection)
        close_conn = connection is None
        try:
            for p in pathways:
                self.save_pathway(p, connection=conn)
            if close_conn:
                conn.commit()
            return pathways
        finally:
            if close_conn:
                conn.close()

    def get_pathway(self, project_id: str, pathway_id: UUID, connection: Any = None) -> MechanismPathway | None:
        conn = self._get_connection(connection)
        close_conn = connection is None
        try:
            cursor = conn.execute(
                """
                SELECT pathway_id, project_id, analytical_relation_id, group_item_id,
                       publication_id, latest_revision_id, source_mechanism_text,
                       analytical_mechanism_category_id, is_review_synthesized,
                       approval_state, approved_by, approved_at, notes,
                       created_at, updated_at
                FROM synthesis_mechanism_pathways
                WHERE project_id = ? AND pathway_id = ?;
                """,
                (project_id, str(pathway_id)),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            return self._row_to_pathway(row)
        finally:
            if close_conn:
                conn.close()

    def get_pathway_by_relation(
        self, project_id: str, analytical_relation_id: UUID, connection: Any = None
    ) -> MechanismPathway | None:
        conn = self._get_connection(connection)
        close_conn = connection is None
        try:
            cursor = conn.execute(
                """
                SELECT pathway_id, project_id, analytical_relation_id, group_item_id,
                       publication_id, latest_revision_id, source_mechanism_text,
                       analytical_mechanism_category_id, is_review_synthesized,
                       approval_state, approved_by, approved_at, notes,
                       created_at, updated_at
                FROM synthesis_mechanism_pathways
                WHERE project_id = ? AND analytical_relation_id = ?;
                """,
                (project_id, str(analytical_relation_id)),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            return self._row_to_pathway(row)
        finally:
            if close_conn:
                conn.close()

    def get_pathway_by_group_item(
        self, project_id: str, group_item_id: UUID, connection: Any = None
    ) -> MechanismPathway | None:
        conn = self._get_connection(connection)
        close_conn = connection is None
        try:
            cursor = conn.execute(
                """
                SELECT pathway_id, project_id, analytical_relation_id, group_item_id,
                       publication_id, latest_revision_id, source_mechanism_text,
                       analytical_mechanism_category_id, is_review_synthesized,
                       approval_state, approved_by, approved_at, notes,
                       created_at, updated_at
                FROM synthesis_mechanism_pathways
                WHERE project_id = ? AND group_item_id = ?;
                """,
                (project_id, str(group_item_id)),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            return self._row_to_pathway(row)
        finally:
            if close_conn:
                conn.close()

    def list_pathways(self, project_id: str, connection: Any = None) -> list[MechanismPathway]:
        conn = self._get_connection(connection)
        close_conn = connection is None
        try:
            cursor = conn.execute(
                """
                SELECT pathway_id, project_id, analytical_relation_id, group_item_id,
                       publication_id, latest_revision_id, source_mechanism_text,
                       analytical_mechanism_category_id, is_review_synthesized,
                       approval_state, approved_by, approved_at, notes,
                       created_at, updated_at
                FROM synthesis_mechanism_pathways
                WHERE project_id = ?
                ORDER BY created_at ASC;
                """,
                (project_id,),
            )
            return [self._row_to_pathway(row) for row in cursor.fetchall()]
        finally:
            if close_conn:
                conn.close()

    def list_pathways_for_category(
        self, project_id: str, category_id: str, connection: Any = None
    ) -> list[MechanismPathway]:
        conn = self._get_connection(connection)
        close_conn = connection is None
        try:
            cursor = conn.execute(
                """
                SELECT pathway_id, project_id, analytical_relation_id, group_item_id,
                       publication_id, latest_revision_id, source_mechanism_text,
                       analytical_mechanism_category_id, is_review_synthesized,
                       approval_state, approved_by, approved_at, notes,
                       created_at, updated_at
                FROM synthesis_mechanism_pathways
                WHERE project_id = ? AND analytical_mechanism_category_id = ?
                ORDER BY created_at ASC;
                """,
                (project_id, category_id),
            )
            return [self._row_to_pathway(row) for row in cursor.fetchall()]
        finally:
            if close_conn:
                conn.close()

    def delete_pathway(self, project_id: str, pathway_id: UUID, connection: Any = None) -> bool:
        conn = self._get_connection(connection)
        close_conn = connection is None
        try:
            cursor = conn.execute(
                "DELETE FROM synthesis_mechanism_pathways WHERE project_id = ? AND pathway_id = ?;",
                (project_id, str(pathway_id)),
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
                "DELETE FROM synthesis_mechanism_pathways WHERE project_id = ?;",
                (project_id,),
            )
            conn.execute(
                "DELETE FROM synthesis_mechanism_categories WHERE project_id = ?;",
                (project_id,),
            )
            if close_conn:
                conn.commit()
        finally:
            if close_conn:
                conn.close()


def default_synthesis_mechanism_repository() -> SqliteSynthesisMechanismRepository:
    return SqliteSynthesisMechanismRepository()
