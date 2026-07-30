from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Protocol

from app.domain.search import SearchStrategy


class SearchStrategyNotFoundError(Exception):
    def __init__(self, project_id: str) -> None:
        self.project_id = project_id
        super().__init__(f"Search strategy for project '{project_id}' not found.")


class SearchStrategyRepository(Protocol):
    def get(self, project_id: str) -> SearchStrategy: ...

    def save(self, strategy: SearchStrategy) -> SearchStrategy: ...


class SqliteSearchStrategyRepository:
    """SQLite adapter storing the complete versioned domain document atomically."""

    def __init__(self, database_path: str | Path) -> None:
        self._database_path = Path(database_path)
        self._database_path.parent.mkdir(parents=True, exist_ok=True)
        self._apply_migrations()

    def get(self, project_id: str) -> SearchStrategy:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT document FROM search_strategies WHERE project_id = ?",
                (project_id,),
            ).fetchone()
        if row is None:
            raise SearchStrategyNotFoundError(project_id)
        return SearchStrategy.model_validate_json(row[0])

    def save(self, strategy: SearchStrategy) -> SearchStrategy:
        project_id = str(strategy.project_id)
        if strategy.project_id is None:
            raise ValueError("persisted search strategy requires project_id")
        document = strategy.model_dump_json()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO search_strategies (
                    project_id, strategy_id, version, document, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(project_id) DO UPDATE SET
                    strategy_id = excluded.strategy_id,
                    version = excluded.version,
                    document = excluded.document,
                    updated_at = excluded.updated_at
                """,
                (
                    project_id,
                    str(strategy.strategy_id),
                    strategy.version,
                    document,
                    strategy.created_at.isoformat(),
                    strategy.updated_at.isoformat(),
                ),
            )
        return strategy

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


def default_search_strategy_repository() -> SqliteSearchStrategyRepository:
    path = os.environ.get("SLR_DATABASE_PATH", "data/slr-platform.db")
    return SqliteSearchStrategyRepository(path)
