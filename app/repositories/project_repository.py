from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol, runtime_checkable

from app.domain.project import Project, ProjectStatus


class ProjectNotFoundError(Exception):
    """Raised when a requested project is not found."""

    def __init__(self, project_id: str) -> None:
        self.project_id = project_id
        super().__init__(f"Project '{project_id}' not found.")


class ProjectAlreadyExistsError(Exception):
    """Raised when creating a project with an existing project_id."""

    def __init__(self, project_id: str) -> None:
        self.project_id = project_id
        super().__init__(f"Project '{project_id}' already exists.")


@runtime_checkable
class ProjectRepository(Protocol):
    """Abstract contract for project persistence."""

    def create(self, project: Project) -> Project: ...

    def get(self, project_id: str) -> Project: ...

    def list_all(self, *, include_archived: bool = False) -> list[Project]: ...

    def update(
        self,
        project_id: str,
        *,
        title: str | None = None,
        description: str | None = None,
        protocol_version: str | None = None,
    ) -> Project: ...

    def archive(self, project_id: str) -> Project: ...

    def restore(self, project_id: str) -> Project: ...
    def delete(self, project_id: str, *, connection: sqlite3.Connection | None = None) -> None: ...


class SqliteProjectRepository:
    """Durable SQLite storage for SLR projects."""

    def __init__(self, database_path: str | Path) -> None:
        self._database_path = Path(database_path)
        self._database_path.parent.mkdir(parents=True, exist_ok=True)
        self._apply_migrations()

    def create(
        self, project: Project, *, connection: sqlite3.Connection | None = None
    ) -> Project:
        if connection is not None:
            self._create_with_conn(connection, project)
        else:
            with self._connect() as conn:
                self._create_with_conn(conn, project)
        return project

    def get(
        self, project_id: str, *, connection: sqlite3.Connection | None = None
    ) -> Project:
        if connection is not None:
            return self._get_with_conn(connection, project_id)
        with self._connect() as conn:
            return self._get_with_conn(conn, project_id)

    def list_all(
        self,
        *,
        include_archived: bool = False,
        connection: sqlite3.Connection | None = None,
    ) -> list[Project]:
        if connection is not None:
            return self._list_all_with_conn(connection, include_archived=include_archived)
        with self._connect() as conn:
            return self._list_all_with_conn(conn, include_archived=include_archived)

    def update(
        self,
        project_id: str,
        *,
        title: str | None = None,
        description: str | None = None,
        protocol_version: str | None = None,
        connection: sqlite3.Connection | None = None,
    ) -> Project:
        if connection is not None:
            return self._update_with_conn(
                connection,
                project_id,
                title=title,
                description=description,
                protocol_version=protocol_version,
            )
        with self._connect() as conn:
            return self._update_with_conn(
                conn,
                project_id,
                title=title,
                description=description,
                protocol_version=protocol_version,
            )

    def archive(
        self, project_id: str, *, connection: sqlite3.Connection | None = None
    ) -> Project:
        if connection is not None:
            return self._set_status_with_conn(connection, project_id, ProjectStatus.ARCHIVED)
        with self._connect() as conn:
            return self._set_status_with_conn(conn, project_id, ProjectStatus.ARCHIVED)

    def restore(
        self, project_id: str, *, connection: sqlite3.Connection | None = None
    ) -> Project:
        if connection is not None:
            return self._set_status_with_conn(connection, project_id, ProjectStatus.ACTIVE)
        with self._connect() as conn:
            return self._set_status_with_conn(conn, project_id, ProjectStatus.ACTIVE)

    def delete(
        self, project_id: str, *, connection: sqlite3.Connection | None = None
    ) -> None:
        if connection is not None:
            self._delete_with_conn(connection, project_id)
        else:
            with self._connect() as conn:
                self._delete_with_conn(conn, project_id)

    def _delete_with_conn(self, connection: sqlite3.Connection, project_id: str) -> None:
        # Ensure project exists before deletion
        self._get_with_conn(connection, project_id)  # raise if not found
        connection.execute("DELETE FROM projects WHERE project_id = ?", (project_id,))

    def _create_with_conn(self, connection: sqlite3.Connection, project: Project) -> None:
        try:
            connection.execute(
                """
                INSERT INTO projects (
                    project_id, title, description, protocol_version, status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    project.project_id,
                    project.title,
                    project.description,
                    project.protocol_version,
                    project.status.value,
                    project.created_at.isoformat(),
                    project.updated_at.isoformat(),
                ),
            )
        except sqlite3.IntegrityError as exc:
            raise ProjectAlreadyExistsError(project.project_id) from exc

    def _get_with_conn(self, connection: sqlite3.Connection, project_id: str) -> Project:
        row = connection.execute(
            """
            SELECT project_id, title, description, protocol_version, status, created_at, updated_at
            FROM projects
            WHERE project_id = ?
            """,
            (project_id,),
        ).fetchone()

        if row is None:
            raise ProjectNotFoundError(project_id)

        return self._row_to_project(row)

    def _list_all_with_conn(
        self, connection: sqlite3.Connection, *, include_archived: bool
    ) -> list[Project]:
        query = """
            SELECT project_id, title, description, protocol_version, status, created_at, updated_at
            FROM projects
        """
        if not include_archived:
            query += " WHERE status = 'active'"
        query += " ORDER BY created_at DESC, project_id ASC"

        rows = connection.execute(query).fetchall()
        return [self._row_to_project(row) for row in rows]

    def _update_with_conn(
        self,
        connection: sqlite3.Connection,
        project_id: str,
        *,
        title: str | None,
        description: str | None,
        protocol_version: str | None,
    ) -> Project:
        existing = self._get_with_conn(connection, project_id)

        new_title = title.strip() if title is not None else existing.title
        if not new_title:
            raise ValueError("title must not be blank")

        new_desc = description.strip() if description is not None else existing.description
        if new_desc == "":
            new_desc = None

        new_proto = (
            protocol_version.strip() if protocol_version is not None else existing.protocol_version
        )
        if not new_proto:
            raise ValueError("protocol_version must not be blank")

        now = datetime.now(timezone.utc)
        connection.execute(
            """
            UPDATE projects
            SET title = ?, description = ?, protocol_version = ?, updated_at = ?
            WHERE project_id = ?
            """,
            (new_title, new_desc, new_proto, now.isoformat(), project_id),
        )

        return self._get_with_conn(connection, project_id)

    def _set_status_with_conn(
        self, connection: sqlite3.Connection, project_id: str, status: ProjectStatus
    ) -> Project:
        self._get_with_conn(connection, project_id)
        now = datetime.now(timezone.utc)
        connection.execute(
            """
            UPDATE projects
            SET status = ?, updated_at = ?
            WHERE project_id = ?
            """,
            (status.value, now.isoformat(), project_id),
        )
        return self._get_with_conn(connection, project_id)

    def _row_to_project(self, row: tuple) -> Project:
        project_id, title, description, protocol_version, status_str, created_at_str, updated_at_str = (
            row
        )
        created_at = datetime.fromisoformat(created_at_str)
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)

        updated_at = datetime.fromisoformat(updated_at_str)
        if updated_at.tzinfo is None:
            updated_at = updated_at.replace(tzinfo=timezone.utc)

        return Project(
            project_id=project_id,
            title=title,
            description=description,
            protocol_version=protocol_version,
            status=ProjectStatus(status_str),
            created_at=created_at,
            updated_at=updated_at,
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


def default_project_repository() -> SqliteProjectRepository:
    path = os.environ.get("SLR_DATABASE_PATH", "data/slr-platform.db")
    return SqliteProjectRepository(path)
