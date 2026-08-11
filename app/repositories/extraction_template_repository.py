from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from app.domain.extraction import ExtractionTemplate, ExtractionTemplateVersion


class ExtractionTemplateNotFoundError(Exception):
    pass


class ExtractionTemplateConflictError(Exception):
    pass


class SqliteExtractionTemplateRepository:
    """Project-independent catalog of immutable extraction-template versions."""

    def __init__(self, database_path: str | Path) -> None:
        self._database_path = Path(database_path)
        self._database_path.parent.mkdir(parents=True, exist_ok=True)
        self._apply_migrations()

    def register_template(self, template: ExtractionTemplate) -> ExtractionTemplate:
        with self._connect() as connection:
            try:
                connection.execute(
                    "INSERT INTO extraction_templates (template_id, name, description, created_at) VALUES (?, ?, ?, ?)",
                    (template.template_id, template.name, template.description, template.created_at.isoformat()),
                )
            except sqlite3.IntegrityError as exc:
                raise ExtractionTemplateConflictError(
                    f"Extraction template '{template.template_id}' already exists."
                ) from exc
        return template

    def register_version(self, version: ExtractionTemplateVersion) -> ExtractionTemplateVersion:
        payload = version.model_dump(mode="json")
        with self._connect() as connection:
            if connection.execute(
                "SELECT 1 FROM extraction_templates WHERE template_id = ?", (version.template_id,)
            ).fetchone() is None:
                raise ExtractionTemplateNotFoundError(f"Extraction template '{version.template_id}' was not found.")
            try:
                connection.execute(
                    """INSERT INTO extraction_template_versions
                    (template_id, version, description, is_active, is_published, schema_json, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        version.template_id,
                        version.version,
                        version.description,
                        int(version.is_active),
                        int(version.is_published),
                        json.dumps(payload, sort_keys=True, separators=(",", ":")),
                        version.created_at.isoformat(),
                    ),
                )
            except sqlite3.IntegrityError as exc:
                raise ExtractionTemplateConflictError(
                    f"Extraction template version '{version.template_id}' v{version.version} already exists and is immutable."
                ) from exc
        return version

    def get_template(self, template_id: str) -> ExtractionTemplate:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT template_id, name, description, created_at FROM extraction_templates WHERE template_id = ?",
                (template_id,),
            ).fetchone()
            if row is None:
                raise ExtractionTemplateNotFoundError(f"Extraction template '{template_id}' was not found.")
            versions = self._versions_with_connection(connection, template_id)
        return ExtractionTemplate(
            template_id=row[0], name=row[1], description=row[2], created_at=_as_datetime(row[3]), versions=versions
        )

    def get_version(self, template_id: str, version: str) -> ExtractionTemplateVersion:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT schema_json FROM extraction_template_versions WHERE template_id = ? AND version = ?",
                (template_id, version),
            ).fetchone()
        if row is None:
            raise ExtractionTemplateNotFoundError(f"Extraction template version '{template_id}' v{version} was not found.")
        return ExtractionTemplateVersion.model_validate_json(row[0])

    def list_active_published_versions(self) -> list[ExtractionTemplateVersion]:
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT schema_json FROM extraction_template_versions
                WHERE is_active = 1 AND is_published = 1
                ORDER BY template_id ASC, version ASC"""
            ).fetchall()
        return [ExtractionTemplateVersion.model_validate_json(row[0]) for row in rows]

    def _versions_with_connection(
        self, connection: sqlite3.Connection, template_id: str
    ) -> list[ExtractionTemplateVersion]:
        rows = connection.execute(
            "SELECT schema_json FROM extraction_template_versions WHERE template_id = ? ORDER BY version ASC",
            (template_id,),
        ).fetchall()
        return [ExtractionTemplateVersion.model_validate_json(row[0]) for row in rows]

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._database_path)
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _apply_migrations(self) -> None:
        migrations = Path(__file__).parents[2] / "migrations"
        with self._connect() as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS schema_migrations (version TEXT PRIMARY KEY, applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"
            )
            applied = {row[0] for row in connection.execute("SELECT version FROM schema_migrations")}
            for migration in sorted(migrations.glob("*.sql")):
                if migration.name not in applied:
                    connection.executescript(migration.read_text(encoding="utf-8"))
                    connection.execute("INSERT INTO schema_migrations(version) VALUES (?)", (migration.name,))


def _as_datetime(value: str) -> datetime:
    result = datetime.fromisoformat(value)
    return result if result.tzinfo is not None else result.replace(tzinfo=timezone.utc)


def default_extraction_template_repository() -> SqliteExtractionTemplateRepository:
    return SqliteExtractionTemplateRepository(os.environ.get("SLR_DATABASE_PATH", "data/slr-platform.db"))
