from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from app.domain.screening import ScreeningStage


@dataclass(frozen=True, slots=True)
class ScreeningReviewerAssignment:
    project_id: str
    stage: ScreeningStage
    reviewer_id: str
    is_active: bool


class SqliteScreeningReviewerAssignmentRepository:
    def __init__(self, database_path: str | Path) -> None:
        self._database_path = Path(database_path)
        self._apply_migrations()

    def list(
        self, project_id: str, stage: ScreeningStage, *, active_only: bool = False
    ) -> Sequence[ScreeningReviewerAssignment]:
        query = "SELECT project_id, stage, reviewer_id, is_active FROM screening_reviewer_assignments WHERE project_id = ? AND stage = ?"
        params: list[object] = [project_id, stage.value]
        if active_only:
            query += " AND is_active = 1"
        query += " ORDER BY reviewer_id"
        with self._connect() as conn:
            return [
                ScreeningReviewerAssignment(row[0], ScreeningStage(row[1]), row[2], bool(row[3]))
                for row in conn.execute(query, params)
            ]

    def replace_active(
        self, project_id: str, stage: ScreeningStage, reviewer_ids: Sequence[str]
    ) -> Sequence[ScreeningReviewerAssignment]:
        normalized = sorted({item.strip() for item in reviewer_ids if item.strip()})
        with self._connect() as conn:
            conn.execute(
                "UPDATE screening_reviewer_assignments SET is_active = 0, updated_at = CURRENT_TIMESTAMP WHERE project_id = ? AND stage = ?",
                (project_id, stage.value),
            )
            for reviewer_id in normalized:
                conn.execute(
                    """INSERT INTO screening_reviewer_assignments (project_id, stage, reviewer_id, is_active)
                    VALUES (?, ?, ?, 1)
                    ON CONFLICT(project_id, stage, reviewer_id) DO UPDATE SET is_active = 1, updated_at = CURRENT_TIMESTAMP""",
                    (project_id, stage.value, reviewer_id),
                )
        return self.list(project_id, stage)

    def delete_for_project(self, project_id: str, *, connection: sqlite3.Connection | None = None) -> None:
        if connection is not None:
            connection.execute("DELETE FROM screening_reviewer_assignments WHERE project_id = ?", (project_id,))
        else:
            with self._connect() as conn:
                conn.execute("DELETE FROM screening_reviewer_assignments WHERE project_id = ?", (project_id,))

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._database_path)

    def _apply_migrations(self) -> None:
        from app.repositories.screening_decision_repository import SqliteScreeningDecisionRepository

        SqliteScreeningDecisionRepository(self._database_path)


def default_screening_reviewer_assignment_repository() -> SqliteScreeningReviewerAssignmentRepository:
    return SqliteScreeningReviewerAssignmentRepository(os.environ.get("SLR_DATABASE_PATH", "data/slr-platform.db"))
