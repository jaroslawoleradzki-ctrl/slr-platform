"""Phase 10: SQLite Repository for Analytical Relations Persistence (Task 10.3)."""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

from app.domain.synthesis import (
    AnalyticalRelation,
    ClassificationApprovalState,
    ConvertedValue,
    EvidenceCharacter,
    RelationDirection,
    TermType,
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


class SqliteSynthesisMatrixRepository:
    """SQLite implementation for persisting and querying analytical relations."""

    def __init__(self, db_path: Path | str | None = None) -> None:
        self.db_path = (
            Path(db_path)
            if db_path is not None
            else Path(os.environ.get("SLR_DATABASE_PATH", "data/slr-platform.db"))
        )

    def _get_connection(self, connection: Any = None) -> sqlite3.Connection:
        if connection is not None:
            return connection  # type: ignore[no-any-return]
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def save_analytical_relation(
        self, relation: AnalyticalRelation, connection: Any = None
    ) -> AnalyticalRelation:
        conn = self._get_connection(connection)
        close_conn = connection is None
        try:
            trans_val = relation.converted_value.transformed_value if relation.converted_value else None
            trans_unit = relation.converted_value.transformed_unit if relation.converted_value else None
            conv_rule = relation.converted_value.conversion_rule if relation.converted_value else None

            conn.execute(
                """
                INSERT INTO synthesis_analytical_relations (
                    relation_id, project_id, publication_id, latest_revision_id,
                    group_item_id, item_index, source_practice, analytical_lean_category_id,
                    source_effect, analytical_energy_category_id, direction,
                    magnitude, original_unit, transformed_value, transformed_unit,
                    conversion_rule, evidence_character, context_summary, approval_state,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(project_id, group_item_id) DO UPDATE SET
                    publication_id = excluded.publication_id,
                    latest_revision_id = excluded.latest_revision_id,
                    item_index = excluded.item_index,
                    source_practice = excluded.source_practice,
                    analytical_lean_category_id = excluded.analytical_lean_category_id,
                    source_effect = excluded.source_effect,
                    analytical_energy_category_id = excluded.analytical_energy_category_id,
                    direction = excluded.direction,
                    magnitude = excluded.magnitude,
                    original_unit = excluded.original_unit,
                    transformed_value = coalesce(excluded.transformed_value, synthesis_analytical_relations.transformed_value),
                    transformed_unit = coalesce(excluded.transformed_unit, synthesis_analytical_relations.transformed_unit),
                    conversion_rule = coalesce(excluded.conversion_rule, synthesis_analytical_relations.conversion_rule),
                    evidence_character = excluded.evidence_character,
                    context_summary = excluded.context_summary,
                    approval_state = excluded.approval_state,
                    updated_at = excluded.updated_at;
                """,
                (
                    str(relation.relation_id),
                    relation.project_id,
                    str(relation.publication_id),
                    str(relation.latest_revision_id),
                    str(relation.group_item_id),
                    relation.item_index,
                    relation.source_practice,
                    relation.analytical_lean_category_id,
                    relation.source_effect,
                    relation.analytical_energy_category_id,
                    relation.direction.value,
                    relation.magnitude,
                    relation.original_unit,
                    trans_val,
                    trans_unit,
                    conv_rule,
                    relation.evidence_character.value,
                    relation.context_summary,
                    relation.approval_state.value,
                    relation.created_at.isoformat(),
                    relation.updated_at.isoformat(),
                ),
            )
            if close_conn:
                conn.commit()
            return relation
        finally:
            if close_conn:
                conn.close()

    def save_analytical_relations(
        self, relations: list[AnalyticalRelation], connection: Any = None
    ) -> list[AnalyticalRelation]:
        conn = self._get_connection(connection)
        close_conn = connection is None
        try:
            for rel in relations:
                self.save_analytical_relation(rel, connection=conn)
            if close_conn:
                conn.commit()
            return relations
        finally:
            if close_conn:
                conn.close()

    def _row_to_relation(self, row: Any) -> AnalyticalRelation:
        converted_val: ConvertedValue | None = None
        if row[13] is not None and row[14] is not None and row[15] is not None:
            converted_val = ConvertedValue(
                transformed_value=float(row[13]),
                transformed_unit=str(row[14]),
                conversion_rule=str(row[15]),
            )

        return AnalyticalRelation(
            relation_id=UUID(row[0]),
            project_id=row[1],
            publication_id=UUID(row[2]),
            latest_revision_id=UUID(row[3]),
            group_item_id=UUID(row[4]),
            item_index=int(row[5]),
            source_practice=row[6],
            analytical_lean_category_id=row[7],
            source_effect=row[8],
            analytical_energy_category_id=row[9],
            direction=RelationDirection(row[10]),
            magnitude=float(row[11]) if row[11] is not None else None,
            original_unit=row[12],
            converted_value=converted_val,
            evidence_character=EvidenceCharacter(row[16]),
            context_summary=row[17],
            approval_state=ClassificationApprovalState(row[18]),
            created_at=_as_datetime(row[19]) or datetime.now(timezone.utc),
            updated_at=_as_datetime(row[20]) or datetime.now(timezone.utc),
        )

    def get_analytical_relation(
        self, project_id: str, relation_id: UUID, connection: Any = None
    ) -> AnalyticalRelation | None:
        conn = self._get_connection(connection)
        close_conn = connection is None
        try:
            cursor = conn.execute(
                """
                SELECT relation_id, project_id, publication_id, latest_revision_id,
                       group_item_id, item_index, source_practice, analytical_lean_category_id,
                       source_effect, analytical_energy_category_id, direction,
                       magnitude, original_unit, transformed_value, transformed_unit,
                       conversion_rule, evidence_character, context_summary, approval_state,
                       created_at, updated_at
                FROM synthesis_analytical_relations
                WHERE project_id = ? AND relation_id = ?;
                """,
                (project_id, str(relation_id)),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            return self._row_to_relation(row)
        finally:
            if close_conn:
                conn.close()

    def get_analytical_relation_by_group_item(
        self, project_id: str, group_item_id: UUID, connection: Any = None
    ) -> AnalyticalRelation | None:
        conn = self._get_connection(connection)
        close_conn = connection is None
        try:
            cursor = conn.execute(
                """
                SELECT relation_id, project_id, publication_id, latest_revision_id,
                       group_item_id, item_index, source_practice, analytical_lean_category_id,
                       source_effect, analytical_energy_category_id, direction,
                       magnitude, original_unit, transformed_value, transformed_unit,
                       conversion_rule, evidence_character, context_summary, approval_state,
                       created_at, updated_at
                FROM synthesis_analytical_relations
                WHERE project_id = ? AND group_item_id = ?;
                """,
                (project_id, str(group_item_id)),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            return self._row_to_relation(row)
        finally:
            if close_conn:
                conn.close()

    def list_analytical_relations(
        self, project_id: str, connection: Any = None
    ) -> list[AnalyticalRelation]:
        conn = self._get_connection(connection)
        close_conn = connection is None
        try:
            cursor = conn.execute(
                """
                SELECT relation_id, project_id, publication_id, latest_revision_id,
                       group_item_id, item_index, source_practice, analytical_lean_category_id,
                       source_effect, analytical_energy_category_id, direction,
                       magnitude, original_unit, transformed_value, transformed_unit,
                       conversion_rule, evidence_character, context_summary, approval_state,
                       created_at, updated_at
                FROM synthesis_analytical_relations
                WHERE project_id = ?
                ORDER BY created_at ASC;
                """,
                (project_id,),
            )
            return [self._row_to_relation(row) for row in cursor.fetchall()]
        finally:
            if close_conn:
                conn.close()

    def list_analytical_relations_for_cell(
        self,
        project_id: str,
        lean_category_id: str,
        energy_category_id: str,
        connection: Any = None,
    ) -> list[AnalyticalRelation]:
        conn = self._get_connection(connection)
        close_conn = connection is None
        try:
            cursor = conn.execute(
                """
                SELECT relation_id, project_id, publication_id, latest_revision_id,
                       group_item_id, item_index, source_practice, analytical_lean_category_id,
                       source_effect, analytical_energy_category_id, direction,
                       magnitude, original_unit, transformed_value, transformed_unit,
                       conversion_rule, evidence_character, context_summary, approval_state,
                       created_at, updated_at
                FROM synthesis_analytical_relations
                WHERE project_id = ?
                  AND analytical_lean_category_id = ?
                  AND analytical_energy_category_id = ?
                  AND approval_state = 'approved'
                ORDER BY created_at ASC;
                """,
                (project_id, lean_category_id, energy_category_id),
            )
            return [self._row_to_relation(row) for row in cursor.fetchall()]
        finally:
            if close_conn:
                conn.close()

    def update_converted_value(
        self,
        project_id: str,
        relation_id: UUID,
        converted_value: ConvertedValue,
        connection: Any = None,
    ) -> bool:
        conn = self._get_connection(connection)
        close_conn = connection is None
        now_iso = datetime.now(timezone.utc).isoformat()
        try:
            cursor = conn.execute(
                """
                UPDATE synthesis_analytical_relations
                SET transformed_value = ?, transformed_unit = ?, conversion_rule = ?, updated_at = ?
                WHERE project_id = ? AND relation_id = ?;
                """,
                (
                    converted_value.transformed_value,
                    converted_value.transformed_unit,
                    converted_value.conversion_rule,
                    now_iso,
                    project_id,
                    str(relation_id),
                ),
            )
            updated = cursor.rowcount > 0
            if close_conn:
                conn.commit()
            return updated
        finally:
            if close_conn:
                conn.close()

    def clear_category_references(
        self,
        project_id: str,
        term_type: TermType,
        category_id: str,
        connection: Any = None,
    ) -> int:
        """Sets category reference to NULL when an analytical category is deleted."""
        conn = self._get_connection(connection)
        close_conn = connection is None
        now_iso = datetime.now(timezone.utc).isoformat()
        try:
            if term_type == TermType.LEAN_PRACTICE:
                cursor = conn.execute(
                    """
                    UPDATE synthesis_analytical_relations
                    SET analytical_lean_category_id = NULL, updated_at = ?
                    WHERE project_id = ? AND analytical_lean_category_id = ?;
                    """,
                    (now_iso, project_id, category_id),
                )
            else:
                cursor = conn.execute(
                    """
                    UPDATE synthesis_analytical_relations
                    SET analytical_energy_category_id = NULL, updated_at = ?
                    WHERE project_id = ? AND analytical_energy_category_id = ?;
                    """,
                    (now_iso, project_id, category_id),
                )
            count = cursor.rowcount
            if close_conn:
                conn.commit()
            return count
        finally:
            if close_conn:
                conn.close()


def default_synthesis_matrix_repository() -> SqliteSynthesisMatrixRepository:
    return SqliteSynthesisMatrixRepository()
