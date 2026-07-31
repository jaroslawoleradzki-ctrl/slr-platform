import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from app.domain.duplicate_review import DuplicateDecision, DuplicateGroupReviewDecision


class GroupNotFoundError(Exception):
    """Raised when a specified duplicate group_id is not found for a project."""

    def __init__(self, group_id: str, project_id: str | None = None) -> None:
        self.group_id = group_id
        self.project_id = project_id
        msg = (
            f"Duplicate group '{group_id}' not found in project '{project_id}'."
            if project_id
            else f"Duplicate group '{group_id}' not found."
        )
        super().__init__(msg)


class DuplicateReviewDecisionRepository(Protocol):
    """Interface for storing and retrieving duplicate review decisions keyed by (project_id, group_id)."""

    def save_decision(
        self, project_id: str, group_id: str, decision: DuplicateGroupReviewDecision
    ) -> None:
        """Store or update a decision for a duplicate group within a specific project."""
        ...

    def get_decision(
        self, project_id: str, group_id: str
    ) -> DuplicateGroupReviewDecision | None:
        """Retrieve the stored decision for a (project_id, group_id), or None if undecided."""
        ...


class InMemoryDuplicateReviewDecisionRepository:
    """In-memory repository for human duplicate review decisions, keyed by composite (project_id, group_id).

    Boundary Note:
    This in-memory implementation stores reviewer decisions in runtime memory using (project_id, group_id) composite keys.
    It guarantees decision isolation between different projects even if they happen to share a group_id.
    """

    def __init__(self) -> None:
        self._decisions: dict[tuple[str, str], DuplicateGroupReviewDecision] = {}

    def save_decision(
        self, project_id: str, group_id: str, decision: DuplicateGroupReviewDecision
    ) -> None:
        self._decisions[(project_id, group_id)] = decision

    def get_decision(
        self, project_id: str, group_id: str
    ) -> DuplicateGroupReviewDecision | None:
        return self._decisions.get((project_id, group_id))

    def clear(self) -> None:
        """Helper for resetting state between tests."""
        self._decisions.clear()


in_memory_duplicate_review_decision_repository = (
    InMemoryDuplicateReviewDecisionRepository()
)


class SqliteDuplicateReviewDecisionRepository:
    """Durable SQLite storage for human duplicate review decisions, keyed by (project_id, group_id)."""

    def __init__(self, database_path: str | Path) -> None:
        self._database_path = Path(database_path)
        self._database_path.parent.mkdir(parents=True, exist_ok=True)
        self._apply_migrations()

    def save_decision(
        self, project_id: str, group_id: str, decision: DuplicateGroupReviewDecision
    ) -> None:
        now_str = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO duplicate_review_decisions (
                    project_id, group_id, decision, rationale, updated_at
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(project_id, group_id) DO UPDATE SET
                    decision = excluded.decision,
                    rationale = excluded.rationale,
                    updated_at = excluded.updated_at
                """,
                (
                    project_id,
                    group_id,
                    decision.decision.value,
                    decision.rationale,
                    now_str,
                ),
            )

    def get_decision(
        self, project_id: str, group_id: str
    ) -> DuplicateGroupReviewDecision | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT decision, rationale
                FROM duplicate_review_decisions
                WHERE project_id = ? AND group_id = ?
                """,
                (project_id, group_id),
            ).fetchone()
        if row is None:
            return None
        return DuplicateGroupReviewDecision(
            decision=DuplicateDecision(str(row[0])),
            rationale=str(row[1]) if row[1] is not None else None,
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
                str(row[0])
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


def default_duplicate_review_decision_repository() -> SqliteDuplicateReviewDecisionRepository:
    path = os.environ.get("SLR_DATABASE_PATH", "data/slr-platform.db")
    return SqliteDuplicateReviewDecisionRepository(path)
