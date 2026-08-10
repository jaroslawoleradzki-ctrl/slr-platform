from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Protocol, runtime_checkable
from uuid import UUID

from app.domain.screening import (
    ScreeningCriterion,
    ScreeningCriterionStage,
    ScreeningCriterionType,
)


class CriterionNotFoundError(Exception):
    """Raised when a screening criterion is not found for a given project."""

    def __init__(self, criterion_id: UUID | str, project_id: str) -> None:
        self.criterion_id = str(criterion_id)
        self.project_id = project_id
        super().__init__(
            f"Screening criterion '{self.criterion_id}' not found in project '{self.project_id}'."
        )


@runtime_checkable
class ScreeningCriterionRepository(Protocol):
    """Abstract contract for persisting and managing project-scoped screening criteria.

    Responsibilities:
    - Persisting configurable ScreeningCriterion domain objects per project.
    - Retrieving a specific criterion by project_id and criterion_id.
    - Listing all criteria for a project in deterministic display order.
    - Updating existing criteria without altering criterion_id or project_id.
    - Deactivating criteria (soft lifecycle) to preserve historical decision references.
    """

    def create(self, criterion: ScreeningCriterion) -> ScreeningCriterion:
        """Persist a new screening criterion."""
        ...

    def get(self, project_id: str, criterion_id: UUID) -> ScreeningCriterion:
        """Retrieve a screening criterion by project_id and criterion_id, or raise CriterionNotFoundError."""
        ...

    def list_by_project(
        self, project_id: str, *, active_only: bool = False
    ) -> list[ScreeningCriterion]:
        """List all screening criteria for a project in deterministic order (display_order, criterion_id)."""
        ...

    def update(self, criterion: ScreeningCriterion) -> ScreeningCriterion:
        """Update an existing screening criterion within its project."""
        ...

    def deactivate(self, project_id: str, criterion_id: UUID) -> ScreeningCriterion:
        """Deactivate a screening criterion (setting is_active=False) for a project."""
        ...


class SqliteScreeningCriterionRepository:
    """Durable SQLite storage for project-scoped screening criteria."""

    def __init__(self, database_path: str | Path) -> None:
        self._database_path = Path(database_path)
        self._database_path.parent.mkdir(parents=True, exist_ok=True)
        self._apply_migrations()

    def create(
        self,
        criterion: ScreeningCriterion,
        *,
        connection: sqlite3.Connection | None = None,
    ) -> ScreeningCriterion:
        if connection is not None:
            self._create_with_conn(connection, criterion)
        else:
            with self._connect() as conn:
                self._create_with_conn(conn, criterion)
        return criterion

    def get(
        self,
        project_id: str,
        criterion_id: UUID,
        *,
        connection: sqlite3.Connection | None = None,
    ) -> ScreeningCriterion:
        if connection is not None:
            return self._get_with_conn(connection, project_id, criterion_id)
        with self._connect() as conn:
            return self._get_with_conn(conn, project_id, criterion_id)

    def list_by_project(
        self,
        project_id: str,
        *,
        active_only: bool = False,
        connection: sqlite3.Connection | None = None,
    ) -> list[ScreeningCriterion]:
        if connection is not None:
            return self._list_with_conn(connection, project_id, active_only)
        with self._connect() as conn:
            return self._list_with_conn(conn, project_id, active_only)

    def update(
        self,
        criterion: ScreeningCriterion,
        *,
        connection: sqlite3.Connection | None = None,
    ) -> ScreeningCriterion:
        if connection is not None:
            return self._update_with_conn(connection, criterion)
        with self._connect() as conn:
            return self._update_with_conn(conn, criterion)

    def deactivate(
        self,
        project_id: str,
        criterion_id: UUID,
        *,
        connection: sqlite3.Connection | None = None,
    ) -> ScreeningCriterion:
        if connection is not None:
            return self._deactivate_with_conn(connection, project_id, criterion_id)
        with self._connect() as conn:
            return self._deactivate_with_conn(conn, project_id, criterion_id)

    # Internal database operations

    def _create_with_conn(
        self, connection: sqlite3.Connection, criterion: ScreeningCriterion
    ) -> None:
        connection.execute(
            """
            INSERT INTO screening_criteria (
                criterion_id, project_id, name, description,
                criterion_type, screening_stage, display_order, is_active, is_required
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(criterion.criterion_id),
                criterion.project_id,
                criterion.name,
                criterion.description,
                criterion.criterion_type.value,
                criterion.screening_stage.value,
                criterion.display_order,
                1 if criterion.is_active else 0,
                1 if criterion.is_required else 0,
            ),
        )

    def _get_with_conn(
        self,
        connection: sqlite3.Connection,
        project_id: str,
        criterion_id: UUID,
    ) -> ScreeningCriterion:
        row = connection.execute(
            """
            SELECT criterion_id, project_id, name, description,
                   criterion_type, screening_stage, display_order, is_active, is_required
            FROM screening_criteria
            WHERE project_id = ? AND criterion_id = ?
            """,
            (project_id, str(criterion_id)),
        ).fetchone()

        if row is None:
            raise CriterionNotFoundError(criterion_id, project_id)

        return self._row_to_criterion(row)

    def _list_with_conn(
        self,
        connection: sqlite3.Connection,
        project_id: str,
        active_only: bool,
    ) -> list[ScreeningCriterion]:
        query = """
            SELECT criterion_id, project_id, name, description,
                   criterion_type, screening_stage, display_order, is_active, is_required
            FROM screening_criteria
            WHERE project_id = ?
        """
        params: list[object] = [project_id]

        if active_only:
            query += " AND is_active = 1"

        query += " ORDER BY display_order ASC, criterion_id ASC"

        rows = connection.execute(query, params).fetchall()
        return [self._row_to_criterion(row) for row in rows]

    def _update_with_conn(
        self, connection: sqlite3.Connection, criterion: ScreeningCriterion
    ) -> ScreeningCriterion:

        cursor = connection.execute(
            """
            UPDATE screening_criteria
            SET name = ?,
                description = ?,
                criterion_type = ?,
                screening_stage = ?,
                display_order = ?,
                is_active = ?,
                is_required = ?
            WHERE project_id = ? AND criterion_id = ?
            """,
            (
                criterion.name,
                criterion.description,
                criterion.criterion_type.value,
                criterion.screening_stage.value,
                criterion.display_order,
                1 if criterion.is_active else 0,
                1 if criterion.is_required else 0,
                criterion.project_id,
                str(criterion.criterion_id),
            ),
        )

        if cursor.rowcount == 0:
            raise CriterionNotFoundError(criterion.criterion_id, criterion.project_id)

        return criterion

    def _deactivate_with_conn(
        self,
        connection: sqlite3.Connection,
        project_id: str,
        criterion_id: UUID,
    ) -> ScreeningCriterion:
        existing = self._get_with_conn(connection, project_id, criterion_id)
        if not existing.is_active:
            return existing

        updated = ScreeningCriterion(
            criterion_id=existing.criterion_id,
            project_id=existing.project_id,
            name=existing.name,
            description=existing.description,
            criterion_type=existing.criterion_type,
            screening_stage=existing.screening_stage,
            display_order=existing.display_order,
            is_active=False,
            is_required=existing.is_required,
        )
        return self._update_with_conn(connection, updated)

    def _row_to_criterion(self, row: tuple) -> ScreeningCriterion:
        (
            criterion_id_str,
            project_id,
            name,
            description,
            criterion_type_str,
            screening_stage_str,
            display_order,
            is_active_int,
            is_required_int,
        ) = row

        return ScreeningCriterion(
            criterion_id=UUID(criterion_id_str),
            project_id=project_id,
            name=name,
            description=description,
            criterion_type=ScreeningCriterionType(criterion_type_str),
            screening_stage=ScreeningCriterionStage(screening_stage_str),
            display_order=display_order,
            is_active=bool(is_active_int),
            is_required=bool(is_required_int),
        )

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
            applied = {
                row[0]
                for row in connection.execute(
                    "SELECT version FROM schema_migrations"
                ).fetchall()
            }
            for migration in sorted(migration_directory.glob("*.sql")):
                if migration.name in applied:
                    continue
                connection.executescript(migration.read_text(encoding="utf-8"))
                connection.execute(
                    "INSERT INTO schema_migrations(version) VALUES (?)",
                    (migration.name,),
                )


def default_screening_criterion_repository() -> SqliteScreeningCriterionRepository:
    path = os.environ.get("SLR_DATABASE_PATH", "data/slr-platform.db")
    return SqliteScreeningCriterionRepository(path)
