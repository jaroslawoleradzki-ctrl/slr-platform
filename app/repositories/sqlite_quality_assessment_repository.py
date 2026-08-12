from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

from app.domain.quality_assessment import (
    ProjectQualityAssessmentConfiguration,
    QualityAssessment,
    QualityAssessmentResponse,
    QualityAssessmentResponseValue,
    QualityAssessmentTemplate,
    QualityAssessmentTemplateCriterion,
    QualityAssessmentTool,
)
from app.repositories.quality_assessment_repository import (
    ProjectQualityAssessmentConfigurationRepository,
    QualityAssessmentCatalogRepository,
    QualityAssessmentRepository,
)

# All application repositories use SLR_DATABASE_PATH as their runtime database
# selector. Keep DATABASE_PATH as a backwards-compatible fallback for direct
# repository consumers, but do not let QA state diverge from the application DB.


def _default_db_path() -> Path:
    return Path(os.getenv("SLR_DATABASE_PATH", os.getenv("DATABASE_PATH", "data/slr-platform.db")))


DEFAULT_DB_PATH = _default_db_path()


class ToolNotFoundError(Exception):
    def __init__(self, tool_id: str) -> None:
        self.tool_id = tool_id
        super().__init__(f"Quality assessment tool '{tool_id}' not found.")


class TemplateVersionNotFoundError(Exception):
    def __init__(self, identifier: str) -> None:
        self.identifier = identifier
        super().__init__(f"Quality assessment template '{identifier}' not found.")


class SqliteQualityAssessmentCatalogRepository(QualityAssessmentCatalogRepository):
    """SQLite implementation for Quality Assessment tool and versioned template catalog."""

    def __init__(self, db_path: Path | str | None = None) -> None:
        self._db_path = Path(db_path) if db_path is not None else _default_db_path()
        self._apply_migrations()

    def _get_connection(self, explicit_conn: sqlite3.Connection | None = None) -> sqlite3.Connection:
        if explicit_conn is not None:
            return explicit_conn
        conn = sqlite3.connect(str(self._db_path))
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.row_factory = sqlite3.Row
        return conn

    def _apply_migrations(self) -> None:
        migration_directory = Path(__file__).parents[2] / "migrations"
        if not migration_directory.exists():
            return

        with self._get_connection() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version TEXT PRIMARY KEY,
                    applied_at TEXT NOT NULL
                )
                """
            )

            applied_versions = {
                row[0] for row in connection.execute("SELECT version FROM schema_migrations")
            }

            for sql_file in sorted(migration_directory.glob("*.sql")):
                if sql_file.name in applied_versions:
                    continue

                connection.executescript(sql_file.read_text(encoding="utf-8"))
                connection.execute(
                    "INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?)",
                    (sql_file.name, datetime.now(timezone.utc).isoformat()),
                )

    def create_tool(self, tool: QualityAssessmentTool, connection: Any = None) -> QualityAssessmentTool:
        conn = self._get_connection(connection)
        close_conn = connection is None
        try:
            conn.execute(
                """
                INSERT INTO quality_assessment_tools (tool_id, name, description, is_active, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (tool.tool_id, tool.name, tool.description, 1 if tool.is_active else 0, tool.created_at.isoformat()),
            )
            if close_conn:
                conn.commit()
            return tool
        finally:
            if close_conn:
                conn.close()

    def get_tool(self, tool_id: str, connection: Any = None) -> QualityAssessmentTool | None:
        conn = self._get_connection(connection)
        close_conn = connection is None
        try:
            row = conn.execute(
                "SELECT tool_id, name, description, is_active, created_at FROM quality_assessment_tools WHERE tool_id = ?",
                (tool_id,),
            ).fetchone()
            if not row:
                return None
            return QualityAssessmentTool(
                tool_id=row["tool_id"],
                name=row["name"],
                description=row["description"],
                is_active=bool(row["is_active"]),
                created_at=datetime.fromisoformat(row["created_at"]),
            )
        finally:
            if close_conn:
                conn.close()

    def list_tools(self, connection: Any = None) -> list[QualityAssessmentTool]:
        conn = self._get_connection(connection)
        close_conn = connection is None
        try:
            rows = conn.execute(
                "SELECT tool_id, name, description, is_active, created_at FROM quality_assessment_tools ORDER BY name ASC"
            ).fetchall()
            return [
                QualityAssessmentTool(
                    tool_id=row["tool_id"],
                    name=row["name"],
                    description=row["description"],
                    is_active=bool(row["is_active"]),
                    created_at=datetime.fromisoformat(row["created_at"]),
                )
                for row in rows
            ]
        finally:
            if close_conn:
                conn.close()

    def create_template_version(
        self, template: QualityAssessmentTemplate, connection: Any = None
    ) -> QualityAssessmentTemplate:
        conn = self._get_connection(connection)
        close_conn = connection is None
        try:
            conn.execute(
                """
                INSERT INTO quality_assessment_templates
                (template_id, tool_id, template_key, name, version, description, is_active, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(template.template_id),
                    template.tool_id,
                    template.template_key,
                    template.name,
                    template.version,
                    template.description,
                    1 if template.is_active else 0,
                    template.created_at.isoformat(),
                ),
            )
            for criterion in template.criteria:
                conn.execute(
                    """
                    INSERT INTO quality_assessment_template_criteria
                    (criterion_id, template_id, display_order, question, guidance, is_required, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(criterion.criterion_id),
                        str(template.template_id),
                        criterion.display_order,
                        criterion.question,
                        criterion.guidance,
                        1 if criterion.is_required else 0,
                        criterion.created_at.isoformat(),
                    ),
                )
            if close_conn:
                conn.commit()
            return template
        finally:
            if close_conn:
                conn.close()

    def _fetch_criteria_for_template(
        self, conn: sqlite3.Connection, template_id: UUID
    ) -> list[QualityAssessmentTemplateCriterion]:
        rows = conn.execute(
            """
            SELECT criterion_id, template_id, display_order, question, guidance, is_required, created_at
            FROM quality_assessment_template_criteria
            WHERE template_id = ?
            ORDER BY display_order ASC
            """,
            (str(template_id),),
        ).fetchall()
        return [
            QualityAssessmentTemplateCriterion(
                criterion_id=UUID(row["criterion_id"]),
                template_id=UUID(row["template_id"]),
                display_order=row["display_order"],
                question=row["question"],
                guidance=row["guidance"],
                is_required=bool(row["is_required"]),
                created_at=datetime.fromisoformat(row["created_at"]),
            )
            for row in rows
        ]

    def get_template_version(
        self, template_id: UUID, connection: Any = None
    ) -> QualityAssessmentTemplate | None:
        conn = self._get_connection(connection)
        close_conn = connection is None
        try:
            row = conn.execute(
                """
                SELECT template_id, tool_id, template_key, name, version, description, is_active, created_at
                FROM quality_assessment_templates
                WHERE template_id = ?
                """,
                (str(template_id),),
            ).fetchone()
            if not row:
                return None
            criteria = self._fetch_criteria_for_template(conn, template_id)
            return QualityAssessmentTemplate(
                template_id=UUID(row["template_id"]),
                tool_id=row["tool_id"],
                template_key=row["template_key"],
                name=row["name"],
                version=row["version"],
                description=row["description"],
                is_active=bool(row["is_active"]),
                criteria=criteria,
                created_at=datetime.fromisoformat(row["created_at"]),
            )
        finally:
            if close_conn:
                conn.close()

    def get_template_version_by_key(
        self, tool_id: str, template_key: str, version: int, connection: Any = None
    ) -> QualityAssessmentTemplate | None:
        conn = self._get_connection(connection)
        close_conn = connection is None
        try:
            row = conn.execute(
                """
                SELECT template_id, tool_id, template_key, name, version, description, is_active, created_at
                FROM quality_assessment_templates
                WHERE tool_id = ? AND template_key = ? AND version = ?
                """,
                (tool_id, template_key, version),
            ).fetchone()
            if not row:
                return None
            tid = UUID(row["template_id"])
            criteria = self._fetch_criteria_for_template(conn, tid)
            return QualityAssessmentTemplate(
                template_id=tid,
                tool_id=row["tool_id"],
                template_key=row["template_key"],
                name=row["name"],
                version=row["version"],
                description=row["description"],
                is_active=bool(row["is_active"]),
                criteria=criteria,
                created_at=datetime.fromisoformat(row["created_at"]),
            )
        finally:
            if close_conn:
                conn.close()

    def list_template_versions(
        self,
        tool_id: str | None = None,
        template_key: str | None = None,
        is_active_only: bool = False,
        connection: Any = None,
    ) -> list[QualityAssessmentTemplate]:
        conn = self._get_connection(connection)
        close_conn = connection is None
        try:
            query_parts = ["SELECT template_id, tool_id, template_key, name, version, description, is_active, created_at FROM quality_assessment_templates"]
            params: list[Any] = []
            conditions: list[str] = []

            if tool_id is not None:
                conditions.append("tool_id = ?")
                params.append(tool_id)
            if template_key is not None:
                conditions.append("template_key = ?")
                params.append(template_key)
            if is_active_only:
                conditions.append("is_active = 1")

            if conditions:
                query_parts.append("WHERE " + " AND ".join(conditions))

            query_parts.append("ORDER BY template_key ASC, version DESC")
            rows = conn.execute(" ".join(query_parts), params).fetchall()

            templates: list[QualityAssessmentTemplate] = []
            for row in rows:
                tid = UUID(row["template_id"])
                criteria = self._fetch_criteria_for_template(conn, tid)
                templates.append(
                    QualityAssessmentTemplate(
                        template_id=tid,
                        tool_id=row["tool_id"],
                        template_key=row["template_key"],
                        name=row["name"],
                        version=row["version"],
                        description=row["description"],
                        is_active=bool(row["is_active"]),
                        criteria=criteria,
                        created_at=datetime.fromisoformat(row["created_at"]),
                    )
                )
            return templates
        finally:
            if close_conn:
                conn.close()

    def set_template_version_active(
        self, template_id: UUID, is_active: bool, connection: Any = None
    ) -> None:
        """Mutates ONLY the is_active lifecycle metadata of a template version."""
        conn = self._get_connection(connection)
        close_conn = connection is None
        try:
            cursor = conn.execute(
                "UPDATE quality_assessment_templates SET is_active = ? WHERE template_id = ?",
                (1 if is_active else 0, str(template_id)),
            )
            if cursor.rowcount == 0:
                raise TemplateVersionNotFoundError(str(template_id))
            if close_conn:
                conn.commit()
        finally:
            if close_conn:
                conn.close()


class SqliteQualityAssessmentRepository(QualityAssessmentRepository):
    """SQLite implementation for append-only publication quality assessment storage."""

    def __init__(self, db_path: Path | str | None = None) -> None:
        self._db_path = Path(db_path) if db_path is not None else _default_db_path()
        self._apply_migrations()

    def _get_connection(self, explicit_conn: sqlite3.Connection | None = None) -> sqlite3.Connection:
        if explicit_conn is not None:
            return explicit_conn
        conn = sqlite3.connect(str(self._db_path))
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.row_factory = sqlite3.Row
        return conn

    def _apply_migrations(self) -> None:
        migration_directory = Path(__file__).parents[2] / "migrations"
        if not migration_directory.exists():
            return

        with self._get_connection() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version TEXT PRIMARY KEY,
                    applied_at TEXT NOT NULL
                )
                """
            )

            applied_versions = {
                row[0] for row in connection.execute("SELECT version FROM schema_migrations")
            }

            for sql_file in sorted(migration_directory.glob("*.sql")):
                if sql_file.name in applied_versions:
                    continue

                connection.executescript(sql_file.read_text(encoding="utf-8"))
                connection.execute(
                    "INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?)",
                    (sql_file.name, datetime.now(timezone.utc).isoformat()),
                )

    def save_assessment(
        self, assessment: QualityAssessment, connection: Any = None
    ) -> QualityAssessment:
        conn = self._get_connection(connection)
        close_conn = connection is None
        try:
            # Authoritative verification: Every response criterion_id MUST belong to assessment.template_id
            for resp in assessment.responses:
                row = conn.execute(
                    "SELECT template_id FROM quality_assessment_template_criteria WHERE criterion_id = ?",
                    (str(resp.criterion_id),),
                ).fetchone()
                if not row:
                    raise sqlite3.IntegrityError(f"Criterion '{resp.criterion_id}' does not exist.")
                if row["template_id"] != str(assessment.template_id):
                    raise sqlite3.IntegrityError(
                        f"Criterion '{resp.criterion_id}' belongs to template '{row['template_id']}', "
                        f"not assessment template '{assessment.template_id}'."
                    )

            conn.execute(
                """
                INSERT INTO quality_assessments
                (assessment_id, project_id, publication_id, reviewer_id, template_id, assessed_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    str(assessment.assessment_id),
                    assessment.project_id,
                    str(assessment.publication_id),
                    assessment.reviewer_id,
                    str(assessment.template_id),
                    assessment.assessed_at.isoformat(),
                ),
            )
            for resp in assessment.responses:
                conn.execute(
                    """
                    INSERT INTO quality_assessment_responses
                    (response_id, assessment_id, criterion_id, question_snapshot, guidance_snapshot,
                     is_required_snapshot, response_value, justification, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(resp.response_id),
                        str(assessment.assessment_id),
                        str(resp.criterion_id),
                        resp.question_snapshot,
                        resp.guidance_snapshot,
                        1 if resp.is_required_snapshot else 0,
                        resp.response_value.value,
                        resp.justification,
                        resp.created_at.isoformat(),
                    ),
                )
            if close_conn:
                conn.commit()
            return assessment
        finally:
            if close_conn:
                conn.close()

    def _fetch_responses_for_assessment(
        self, conn: sqlite3.Connection, assessment_id: UUID
    ) -> list[QualityAssessmentResponse]:
        rows = conn.execute(
            """
            SELECT response_id, assessment_id, criterion_id, question_snapshot, guidance_snapshot,
                   is_required_snapshot, response_value, justification, created_at
            FROM quality_assessment_responses
            WHERE assessment_id = ?
            ORDER BY response_id ASC
            """,
            (str(assessment_id),),
        ).fetchall()
        return [
            QualityAssessmentResponse(
                response_id=UUID(row["response_id"]),
                assessment_id=UUID(row["assessment_id"]),
                criterion_id=UUID(row["criterion_id"]),
                question_snapshot=row["question_snapshot"],
                guidance_snapshot=row["guidance_snapshot"],
                is_required_snapshot=bool(row["is_required_snapshot"]),
                response_value=QualityAssessmentResponseValue(row["response_value"]),
                justification=row["justification"],
                created_at=datetime.fromisoformat(row["created_at"]),
            )
            for row in rows
        ]

    def get_latest_assessment(
        self, project_id: str, publication_id: UUID, reviewer_id: str, connection: Any = None
    ) -> QualityAssessment | None:
        conn = self._get_connection(connection)
        close_conn = connection is None
        try:
            row = conn.execute(
                """
                SELECT assessment_id, project_id, publication_id, reviewer_id, template_id, assessed_at
                FROM quality_assessments
                WHERE project_id = ? AND publication_id = ? AND reviewer_id = ?
                ORDER BY assessed_at DESC
                LIMIT 1
                """,
                (project_id, str(publication_id), reviewer_id),
            ).fetchone()
            if not row:
                return None
            aid = UUID(row["assessment_id"])
            responses = self._fetch_responses_for_assessment(conn, aid)
            return QualityAssessment(
                assessment_id=aid,
                project_id=row["project_id"],
                publication_id=UUID(row["publication_id"]),
                reviewer_id=row["reviewer_id"],
                template_id=UUID(row["template_id"]),
                responses=responses,
                assessed_at=datetime.fromisoformat(row["assessed_at"]),
            )
        finally:
            if close_conn:
                conn.close()

    def list_assessments_for_publication(
        self, project_id: str, publication_id: UUID, reviewer_id: str, connection: Any = None
    ) -> list[QualityAssessment]:
        conn = self._get_connection(connection)
        close_conn = connection is None
        try:
            rows = conn.execute(
                """
                SELECT assessment_id, project_id, publication_id, reviewer_id, template_id, assessed_at
                FROM quality_assessments
                WHERE project_id = ? AND publication_id = ? AND reviewer_id = ?
                ORDER BY assessed_at DESC
                """,
                (project_id, str(publication_id), reviewer_id),
            ).fetchall()
            assessments: list[QualityAssessment] = []
            for row in rows:
                aid = UUID(row["assessment_id"])
                responses = self._fetch_responses_for_assessment(conn, aid)
                assessments.append(
                    QualityAssessment(
                        assessment_id=aid,
                        project_id=row["project_id"],
                        publication_id=UUID(row["publication_id"]),
                        reviewer_id=row["reviewer_id"],
                        template_id=UUID(row["template_id"]),
                        responses=responses,
                        assessed_at=datetime.fromisoformat(row["assessed_at"]),
                    )
                )
            return assessments
        finally:
            if close_conn:
                conn.close()

    def delete_for_project(self, project_id: str, connection: Any = None) -> None:
        """Deletes all project-scoped quality assessments and responses."""
        conn = self._get_connection(connection)
        close_conn = connection is None
        try:
            conn.execute(
                """
                DELETE FROM quality_assessment_responses
                WHERE assessment_id IN (
                    SELECT assessment_id FROM quality_assessments WHERE project_id = ?
                )
                """,
                (project_id,),
            )
            conn.execute("DELETE FROM quality_assessments WHERE project_id = ?", (project_id,))
            if close_conn:
                conn.commit()
        finally:
            if close_conn:
                conn.close()


def default_quality_assessment_catalog_repository() -> SqliteQualityAssessmentCatalogRepository:
    return SqliteQualityAssessmentCatalogRepository()


def default_quality_assessment_repository() -> SqliteQualityAssessmentRepository:
    return SqliteQualityAssessmentRepository()


class SqliteProjectQualityAssessmentConfigurationRepository(ProjectQualityAssessmentConfigurationRepository):
    """SQLite implementation for project-scoped Quality Assessment configuration storage."""

    def __init__(self, db_path: Path | str | None = None) -> None:
        self._db_path = Path(db_path) if db_path is not None else _default_db_path()
        self._apply_migrations()

    def _get_connection(self, explicit_conn: sqlite3.Connection | None = None) -> sqlite3.Connection:
        if explicit_conn is not None:
            return explicit_conn
        conn = sqlite3.connect(str(self._db_path))
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.row_factory = sqlite3.Row
        return conn

    def _apply_migrations(self) -> None:
        migration_directory = Path(__file__).parents[2] / "migrations"
        if not migration_directory.exists():
            return

        with self._get_connection() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version TEXT PRIMARY KEY,
                    applied_at TEXT NOT NULL
                )
                """
            )

            applied_versions = {
                row[0] for row in connection.execute("SELECT version FROM schema_migrations")
            }

            for sql_file in sorted(migration_directory.glob("*.sql")):
                if sql_file.name in applied_versions:
                    continue

                connection.executescript(sql_file.read_text(encoding="utf-8"))
                connection.execute(
                    "INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?)",
                    (sql_file.name, datetime.now(timezone.utc).isoformat()),
                )

    def save_configuration(
        self, config: ProjectQualityAssessmentConfiguration, connection: Any = None
    ) -> ProjectQualityAssessmentConfiguration:
        conn = self._get_connection(connection)
        close_conn = connection is None
        try:
            conn.execute(
                """
                INSERT INTO project_quality_assessment_configurations
                (project_id, tool_id, template_id, configured_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(project_id) DO UPDATE SET
                    tool_id = excluded.tool_id,
                    template_id = excluded.template_id,
                    updated_at = excluded.updated_at
                """,
                (
                    config.project_id,
                    config.tool_id,
                    str(config.template_id),
                    config.configured_at.isoformat(),
                    config.updated_at.isoformat(),
                ),
            )
            if close_conn:
                conn.commit()
            return config
        finally:
            if close_conn:
                conn.close()

    def get_configuration(
        self, project_id: str, connection: Any = None
    ) -> ProjectQualityAssessmentConfiguration | None:
        conn = self._get_connection(connection)
        close_conn = connection is None
        try:
            row = conn.execute(
                """
                SELECT project_id, tool_id, template_id, configured_at, updated_at
                FROM project_quality_assessment_configurations
                WHERE project_id = ?
                """,
                (project_id,),
            ).fetchone()
            if not row:
                return None
            return ProjectQualityAssessmentConfiguration(
                project_id=row["project_id"],
                tool_id=row["tool_id"],
                template_id=UUID(row["template_id"]),
                configured_at=datetime.fromisoformat(row["configured_at"]),
                updated_at=datetime.fromisoformat(row["updated_at"]),
            )
        finally:
            if close_conn:
                conn.close()

    def delete_for_project(self, project_id: str, connection: Any = None) -> None:
        conn = self._get_connection(connection)
        close_conn = connection is None
        try:
            conn.execute(
                "DELETE FROM project_quality_assessment_configurations WHERE project_id = ?",
                (project_id,),
            )
            if close_conn:
                conn.commit()
        finally:
            if close_conn:
                conn.close()


def default_project_quality_assessment_configuration_repository() -> (
    SqliteProjectQualityAssessmentConfigurationRepository
):
    return SqliteProjectQualityAssessmentConfigurationRepository()
