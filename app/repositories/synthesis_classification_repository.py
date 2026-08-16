"""Repository for Phase 10 Terminology Classification."""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol, runtime_checkable
from uuid import UUID

from app.domain.synthesis import (
    ClassificationApprovalState,
    EnergyEffectCategory,
    LeanPracticeCategory,
    TermMapping,
    TermType,
)


def _as_datetime(value: str | datetime | None) -> datetime | None:
    """Converts a database string or datetime to a timezone-aware datetime."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


@runtime_checkable
class SynthesisClassificationRepository(Protocol):
    """Protocol for terminology classification category and mapping persistence."""

    def create_lean_category(self, category: LeanPracticeCategory, connection: Any = None) -> LeanPracticeCategory: ...

    def update_lean_category(self, category: LeanPracticeCategory, connection: Any = None) -> LeanPracticeCategory: ...

    def delete_lean_category(self, project_id: str, category_id: str, connection: Any = None) -> bool: ...

    def get_lean_category(
        self, project_id: str, category_id: str, connection: Any = None
    ) -> LeanPracticeCategory | None: ...

    def list_lean_categories(self, project_id: str, connection: Any = None) -> list[LeanPracticeCategory]: ...

    def create_energy_category(
        self, category: EnergyEffectCategory, connection: Any = None
    ) -> EnergyEffectCategory: ...

    def update_energy_category(
        self, category: EnergyEffectCategory, connection: Any = None
    ) -> EnergyEffectCategory: ...

    def delete_energy_category(self, project_id: str, category_id: str, connection: Any = None) -> bool: ...

    def get_energy_category(
        self, project_id: str, category_id: str, connection: Any = None
    ) -> EnergyEffectCategory | None: ...

    def list_energy_categories(self, project_id: str, connection: Any = None) -> list[EnergyEffectCategory]: ...

    def save_term_mapping(self, mapping: TermMapping, connection: Any = None) -> TermMapping: ...

    def get_term_mapping(
        self, project_id: str, term_type: TermType, source_value: str, connection: Any = None
    ) -> TermMapping | None: ...

    def list_term_mappings(
        self, project_id: str, term_type: TermType | None = None, connection: Any = None
    ) -> list[TermMapping]: ...

    def delete_term_mapping(
        self, project_id: str, term_type: TermType, source_value: str, connection: Any = None
    ) -> bool: ...

    def delete_for_project(self, project_id: str, connection: Any = None) -> None: ...


class SqliteSynthesisClassificationRepository(SynthesisClassificationRepository):
    """SQLite implementation of terminology classification repository."""

    def __init__(self, database_path: str | Path) -> None:
        self._database_path = Path(database_path)
        self._apply_migrations()

    def _get_connection(self, connection: Any = None) -> sqlite3.Connection:
        if connection is not None:
            return connection
        conn = sqlite3.connect(self._database_path)
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def _apply_migrations(self) -> None:
        migrations_dir = Path(__file__).parents[2] / "migrations"
        conn = self._get_connection()
        try:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS schema_migrations ("
                "version TEXT PRIMARY KEY, "
                "applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP"
                ");"
            )
            applied = {row[0] for row in conn.execute("SELECT version FROM schema_migrations")}
            for sql_file in sorted(migrations_dir.glob("*.sql")):
                if sql_file.name not in applied:
                    conn.executescript(sql_file.read_text(encoding="utf-8"))
                    conn.execute("INSERT INTO schema_migrations (version) VALUES (?);", (sql_file.name,))
            conn.commit()
        finally:
            conn.close()

    def create_lean_category(self, category: LeanPracticeCategory, connection: Any = None) -> LeanPracticeCategory:
        conn = self._get_connection(connection)
        close_conn = connection is None
        try:
            conn.execute(
                """
                INSERT INTO synthesis_lean_categories (
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

    def update_lean_category(self, category: LeanPracticeCategory, connection: Any = None) -> LeanPracticeCategory:
        conn = self._get_connection(connection)
        close_conn = connection is None
        try:
            conn.execute(
                """
                UPDATE synthesis_lean_categories
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

    def delete_lean_category(self, project_id: str, category_id: str, connection: Any = None) -> bool:
        conn = self._get_connection(connection)
        close_conn = connection is None
        try:
            cursor = conn.execute(
                "DELETE FROM synthesis_lean_categories WHERE project_id = ? AND category_id = ?;",
                (project_id, category_id),
            )
            deleted = cursor.rowcount > 0
            if deleted:
                conn.execute(
                    "DELETE FROM synthesis_term_mappings WHERE project_id = ? AND term_type = ? AND analytical_category_id = ?;",
                    (project_id, TermType.LEAN_PRACTICE.value, category_id),
                )
                try:
                    conn.execute(
                        """
                        UPDATE synthesis_analytical_relations
                        SET analytical_lean_category_id = NULL, updated_at = CURRENT_TIMESTAMP
                        WHERE project_id = ? AND analytical_lean_category_id = ?;
                        """,
                        (project_id, category_id),
                    )
                except sqlite3.OperationalError:
                    pass  # Table might not exist yet during historical migration tests
            if close_conn:
                conn.commit()
            return deleted
        finally:
            if close_conn:
                conn.close()

    def get_lean_category(
        self, project_id: str, category_id: str, connection: Any = None
    ) -> LeanPracticeCategory | None:
        conn = self._get_connection(connection)
        close_conn = connection is None
        try:
            cursor = conn.execute(
                """
                SELECT project_id, category_id, name, description, display_order, created_at, updated_at
                FROM synthesis_lean_categories
                WHERE project_id = ? AND category_id = ?;
                """,
                (project_id, category_id),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            return LeanPracticeCategory(
                project_id=row[0],
                category_id=row[1],
                name=row[2],
                description=row[3],
                display_order=row[4],
                created_at=_as_datetime(row[5]) or datetime.now(timezone.utc),
                updated_at=_as_datetime(row[6]) or datetime.now(timezone.utc),
            )
        finally:
            if close_conn:
                conn.close()

    def list_lean_categories(self, project_id: str, connection: Any = None) -> list[LeanPracticeCategory]:
        conn = self._get_connection(connection)
        close_conn = connection is None
        try:
            cursor = conn.execute(
                """
                SELECT project_id, category_id, name, description, display_order, created_at, updated_at
                FROM synthesis_lean_categories
                WHERE project_id = ?
                ORDER BY display_order ASC, name ASC;
                """,
                (project_id,),
            )
            return [
                LeanPracticeCategory(
                    project_id=row[0],
                    category_id=row[1],
                    name=row[2],
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

    def create_energy_category(self, category: EnergyEffectCategory, connection: Any = None) -> EnergyEffectCategory:
        conn = self._get_connection(connection)
        close_conn = connection is None
        try:
            conn.execute(
                """
                INSERT INTO synthesis_energy_categories (
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

    def update_energy_category(self, category: EnergyEffectCategory, connection: Any = None) -> EnergyEffectCategory:
        conn = self._get_connection(connection)
        close_conn = connection is None
        try:
            conn.execute(
                """
                UPDATE synthesis_energy_categories
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

    def delete_energy_category(self, project_id: str, category_id: str, connection: Any = None) -> bool:
        conn = self._get_connection(connection)
        close_conn = connection is None
        try:
            cursor = conn.execute(
                "DELETE FROM synthesis_energy_categories WHERE project_id = ? AND category_id = ?;",
                (project_id, category_id),
            )
            deleted = cursor.rowcount > 0
            if deleted:
                conn.execute(
                    "DELETE FROM synthesis_term_mappings WHERE project_id = ? AND term_type = ? AND analytical_category_id = ?;",
                    (project_id, TermType.ENERGY_EFFECT.value, category_id),
                )
                try:
                    conn.execute(
                        """
                        UPDATE synthesis_analytical_relations
                        SET analytical_energy_category_id = NULL, updated_at = CURRENT_TIMESTAMP
                        WHERE project_id = ? AND analytical_energy_category_id = ?;
                        """,
                        (project_id, category_id),
                    )
                except sqlite3.OperationalError:
                    pass
            if close_conn:
                conn.commit()
            return deleted
        finally:
            if close_conn:
                conn.close()

    def get_energy_category(
        self, project_id: str, category_id: str, connection: Any = None
    ) -> EnergyEffectCategory | None:
        conn = self._get_connection(connection)
        close_conn = connection is None
        try:
            cursor = conn.execute(
                """
                SELECT project_id, category_id, name, description, display_order, created_at, updated_at
                FROM synthesis_energy_categories
                WHERE project_id = ? AND category_id = ?;
                """,
                (project_id, category_id),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            return EnergyEffectCategory(
                project_id=row[0],
                category_id=row[1],
                name=row[2],
                description=row[3],
                display_order=row[4],
                created_at=_as_datetime(row[5]) or datetime.now(timezone.utc),
                updated_at=_as_datetime(row[6]) or datetime.now(timezone.utc),
            )
        finally:
            if close_conn:
                conn.close()

    def list_energy_categories(self, project_id: str, connection: Any = None) -> list[EnergyEffectCategory]:
        conn = self._get_connection(connection)
        close_conn = connection is None
        try:
            cursor = conn.execute(
                """
                SELECT project_id, category_id, name, description, display_order, created_at, updated_at
                FROM synthesis_energy_categories
                WHERE project_id = ?
                ORDER BY display_order ASC, name ASC;
                """,
                (project_id,),
            )
            return [
                EnergyEffectCategory(
                    project_id=row[0],
                    category_id=row[1],
                    name=row[2],
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

    def save_term_mapping(self, mapping: TermMapping, connection: Any = None) -> TermMapping:
        conn = self._get_connection(connection)
        close_conn = connection is None
        try:
            approved_at_iso = mapping.approved_at.isoformat() if mapping.approved_at else None
            conn.execute(
                """
                INSERT INTO synthesis_term_mappings (
                    mapping_id, project_id, term_type, source_value,
                    analytical_category_id, approval_state, approved_by, approved_at,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(project_id, term_type, source_value) DO UPDATE SET
                    analytical_category_id = excluded.analytical_category_id,
                    approval_state = excluded.approval_state,
                    approved_by = excluded.approved_by,
                    approved_at = excluded.approved_at,
                    updated_at = excluded.updated_at;
                """,
                (
                    str(mapping.mapping_id),
                    mapping.project_id,
                    mapping.term_type.value,
                    mapping.source_value,
                    mapping.analytical_category_id,
                    mapping.approval_state.value,
                    mapping.approved_by,
                    approved_at_iso,
                    mapping.created_at.isoformat(),
                    mapping.updated_at.isoformat(),
                ),
            )
            if close_conn:
                conn.commit()
            return mapping
        finally:
            if close_conn:
                conn.close()

    def get_term_mapping(
        self, project_id: str, term_type: TermType, source_value: str, connection: Any = None
    ) -> TermMapping | None:
        conn = self._get_connection(connection)
        close_conn = connection is None
        try:
            cursor = conn.execute(
                """
                SELECT mapping_id, project_id, term_type, source_value,
                       analytical_category_id, approval_state, approved_by, approved_at,
                       created_at, updated_at
                FROM synthesis_term_mappings
                WHERE project_id = ? AND term_type = ? AND source_value = ?;
                """,
                (project_id, term_type.value, source_value),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            return TermMapping(
                mapping_id=UUID(row[0]),
                project_id=row[1],
                term_type=TermType(row[2]),
                source_value=row[3],
                analytical_category_id=row[4],
                approval_state=ClassificationApprovalState(row[5]),
                approved_by=row[6],
                approved_at=_as_datetime(row[7]),
                created_at=_as_datetime(row[8]) or datetime.now(timezone.utc),
                updated_at=_as_datetime(row[9]) or datetime.now(timezone.utc),
            )
        finally:
            if close_conn:
                conn.close()

    def list_term_mappings(
        self, project_id: str, term_type: TermType | None = None, connection: Any = None
    ) -> list[TermMapping]:
        conn = self._get_connection(connection)
        close_conn = connection is None
        try:
            if term_type is not None:
                cursor = conn.execute(
                    """
                    SELECT mapping_id, project_id, term_type, source_value,
                           analytical_category_id, approval_state, approved_by, approved_at,
                           created_at, updated_at
                    FROM synthesis_term_mappings
                    WHERE project_id = ? AND term_type = ?
                    ORDER BY source_value ASC;
                    """,
                    (project_id, term_type.value),
                )
            else:
                cursor = conn.execute(
                    """
                    SELECT mapping_id, project_id, term_type, source_value,
                           analytical_category_id, approval_state, approved_by, approved_at,
                           created_at, updated_at
                    FROM synthesis_term_mappings
                    WHERE project_id = ?
                    ORDER BY term_type ASC, source_value ASC;
                    """,
                    (project_id,),
                )
            return [
                TermMapping(
                    mapping_id=UUID(row[0]),
                    project_id=row[1],
                    term_type=TermType(row[2]),
                    source_value=row[3],
                    analytical_category_id=row[4],
                    approval_state=ClassificationApprovalState(row[5]),
                    approved_by=row[6],
                    approved_at=_as_datetime(row[7]),
                    created_at=_as_datetime(row[8]) or datetime.now(timezone.utc),
                    updated_at=_as_datetime(row[9]) or datetime.now(timezone.utc),
                )
                for row in cursor.fetchall()
            ]
        finally:
            if close_conn:
                conn.close()

    def delete_term_mapping(
        self, project_id: str, term_type: TermType, source_value: str, connection: Any = None
    ) -> bool:
        conn = self._get_connection(connection)
        close_conn = connection is None
        try:
            cursor = conn.execute(
                "DELETE FROM synthesis_term_mappings WHERE project_id = ? AND term_type = ? AND source_value = ?;",
                (project_id, term_type.value, source_value),
            )
            deleted = cursor.rowcount > 0
            if close_conn:
                conn.commit()
            return deleted
        finally:
            if close_conn:
                conn.close()

    def delete_for_project(self, project_id: str, connection: Any = None) -> None:
        """Deletes all classification data for a project (project lifecycle cleanup)."""
        conn = self._get_connection(connection)
        close_conn = connection is None
        try:
            conn.execute("DELETE FROM synthesis_term_mappings WHERE project_id = ?;", (project_id,))
            conn.execute("DELETE FROM synthesis_lean_categories WHERE project_id = ?;", (project_id,))
            conn.execute("DELETE FROM synthesis_energy_categories WHERE project_id = ?;", (project_id,))
            if close_conn:
                conn.commit()
        finally:
            if close_conn:
                conn.close()


def default_synthesis_classification_repository() -> SqliteSynthesisClassificationRepository:
    return SqliteSynthesisClassificationRepository(os.environ.get("SLR_DATABASE_PATH", "data/slr-platform.db"))
