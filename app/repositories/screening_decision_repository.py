from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol, runtime_checkable
from uuid import UUID

from app.domain.screening import (
    CriterionAssessment,
    CriterionAssessmentValue,
    ScreeningCriterionStage,
    ScreeningCriterionType,
    ScreeningDecision,
    ScreeningOutcome,
    ScreeningStage,
)


class DecisionNotFoundError(Exception):
    """Raised when a screening decision is not found for a given project."""

    def __init__(self, decision_id: UUID | str, project_id: str) -> None:
        self.decision_id = str(decision_id)
        self.project_id = project_id
        super().__init__(
            f"Screening decision '{self.decision_id}' not found in project '{self.project_id}'."
        )


@runtime_checkable
class ScreeningDecisionRepository(Protocol):
    """Abstract contract for persisting and managing project-scoped screening decisions.

    Responsibilities:
    - Persisting immutable ScreeningDecision records (append-only history).
    - Retrieving a specific decision by project_id and decision_id.
    - Retrieving the latest decision for a (project_id, publication_id, stage, reviewer_id) tuple.
    - Listing full decision history for a publication and stage.
    - Listing all decisions for a project, optionally filtered by stage.
    """

    def save(self, decision: ScreeningDecision) -> ScreeningDecision:
        """Persist a new screening decision record."""
        ...

    def get(self, project_id: str, decision_id: UUID) -> ScreeningDecision:
        """Retrieve a screening decision by project_id and decision_id, or raise DecisionNotFoundError."""
        ...

    def get_latest_decision(
        self, project_id: str, publication_id: UUID, stage: ScreeningStage, reviewer_id: str
    ) -> ScreeningDecision | None:
        """Retrieve the most recent decision for a publication, stage, and reviewer in a project."""
        ...

    def list_history(
        self, project_id: str, publication_id: UUID, stage: ScreeningStage, reviewer_id: str | None = None
    ) -> list[ScreeningDecision]:
        """List decision history for a publication and stage, ordered by decided_at DESC, decision_id DESC."""
        ...

    def list_by_project(
        self, project_id: str, stage: ScreeningStage | None = None
    ) -> list[ScreeningDecision]:
        """List all screening decisions for a project, optionally filtered by screening stage."""
        ...


class SqliteScreeningDecisionRepository:
    """Durable SQLite storage for project-scoped screening decisions and criterion assessments."""

    def __init__(self, database_path: str | Path) -> None:
        self._database_path = Path(database_path)
        self._database_path.parent.mkdir(parents=True, exist_ok=True)
        self._apply_migrations()

    def save(
        self,
        decision: ScreeningDecision,
        *,
        connection: sqlite3.Connection | None = None,
    ) -> ScreeningDecision:
        if connection is not None:
            self._save_with_conn(connection, decision)
        else:
            with self._connect() as conn:
                self._save_with_conn(conn, decision)
        return decision

    def get(
        self,
        project_id: str,
        decision_id: UUID,
        *,
        connection: sqlite3.Connection | None = None,
    ) -> ScreeningDecision:
        if connection is not None:
            return self._get_with_conn(connection, project_id, decision_id)
        with self._connect() as conn:
            return self._get_with_conn(conn, project_id, decision_id)

    def get_latest_decision(
        self,
        project_id: str,
        publication_id: UUID,
        stage: ScreeningStage,
        reviewer_id: str,
        *,
        connection: sqlite3.Connection | None = None,
    ) -> ScreeningDecision | None:
        if connection is not None:
            return self._get_latest_with_conn(
                connection, project_id, publication_id, stage, reviewer_id
            )
        with self._connect() as conn:
            return self._get_latest_with_conn(
                conn, project_id, publication_id, stage, reviewer_id
            )

    def list_history(
        self,
        project_id: str,
        publication_id: UUID,
        stage: ScreeningStage,
        reviewer_id: str | None = None,
        *,
        connection: sqlite3.Connection | None = None,
    ) -> list[ScreeningDecision]:
        if connection is not None:
            return self._list_history_with_conn(
                connection, project_id, publication_id, stage, reviewer_id
            )
        with self._connect() as conn:
            return self._list_history_with_conn(
                conn, project_id, publication_id, stage, reviewer_id
            )

    def list_by_project(
        self,
        project_id: str,
        stage: ScreeningStage | None = None,
        *,
        connection: sqlite3.Connection | None = None,
    ) -> list[ScreeningDecision]:
        if connection is not None:
            return self._list_by_project_with_conn(connection, project_id, stage)
        with self._connect() as conn:
            return self._list_by_project_with_conn(conn, project_id, stage)

    # Internal database operations

    def _save_with_conn(
        self, connection: sqlite3.Connection, decision: ScreeningDecision
    ) -> None:
        decided_at_str = decision.decided_at.isoformat()
        connection.execute(
            """
            INSERT INTO screening_decisions (
                decision_id, project_id, publication_id, stage,
                outcome, reviewer_id, rationale, decided_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(decision.decision_id),
                decision.project_id,
                str(decision.publication_id),
                decision.stage.value,
                decision.outcome.value,
                decision.reviewer_id,
                decision.rationale,
                decided_at_str,
            ),
        )

        for assessment in decision.criterion_assessments:
            connection.execute(
                """
                INSERT INTO screening_criterion_assessments (
                    decision_id, criterion_id, criterion_name, criterion_type,
                    criterion_stage, criterion_is_required, assessment_value, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(decision.decision_id),
                    str(assessment.criterion_id),
                    assessment.criterion_name,
                    assessment.criterion_type.value,
                    assessment.criterion_stage.value,
                    1 if assessment.criterion_is_required else 0,
                    assessment.assessment_value.value,
                    assessment.notes,
                ),
            )

    def _get_with_conn(
        self,
        connection: sqlite3.Connection,
        project_id: str,
        decision_id: UUID,
    ) -> ScreeningDecision:
        row = connection.execute(
            """
            SELECT decision_id, project_id, publication_id, stage,
                   outcome, reviewer_id, rationale, decided_at
            FROM screening_decisions
            WHERE project_id = ? AND decision_id = ?
            """,
            (project_id, str(decision_id)),
        ).fetchone()

        if row is None:
            raise DecisionNotFoundError(decision_id, project_id)

        return self._row_to_decision(connection, row)

    def _get_latest_with_conn(
        self,
        connection: sqlite3.Connection,
        project_id: str,
        publication_id: UUID,
        stage: ScreeningStage,
        reviewer_id: str,
    ) -> ScreeningDecision | None:
        row = connection.execute(
            """
            SELECT decision_id, project_id, publication_id, stage,
                   outcome, reviewer_id, rationale, decided_at
            FROM screening_decisions
            WHERE project_id = ? AND publication_id = ? AND stage = ? AND reviewer_id = ?
            ORDER BY decided_at DESC, decision_id DESC
            LIMIT 1
            """,
            (project_id, str(publication_id), stage.value, reviewer_id),
        ).fetchone()

        if row is None:
            return None

        return self._row_to_decision(connection, row)

    def _list_history_with_conn(
        self,
        connection: sqlite3.Connection,
        project_id: str,
        publication_id: UUID,
        stage: ScreeningStage,
        reviewer_id: str | None,
    ) -> list[ScreeningDecision]:
        query = """
            SELECT decision_id, project_id, publication_id, stage,
                   outcome, reviewer_id, rationale, decided_at
            FROM screening_decisions
            WHERE project_id = ? AND publication_id = ? AND stage = ?
        """
        params: list[object] = [project_id, str(publication_id), stage.value]

        if reviewer_id is not None:
            query += " AND reviewer_id = ?"
            params.append(reviewer_id)

        query += " ORDER BY decided_at DESC, decision_id DESC"

        rows = connection.execute(query, params).fetchall()
        return [self._row_to_decision(connection, row) for row in rows]

    def _list_by_project_with_conn(
        self,
        connection: sqlite3.Connection,
        project_id: str,
        stage: ScreeningStage | None,
    ) -> list[ScreeningDecision]:
        query = """
            SELECT decision_id, project_id, publication_id, stage,
                   outcome, reviewer_id, rationale, decided_at
            FROM screening_decisions
            WHERE project_id = ?
        """
        params: list[object] = [project_id]

        if stage is not None:
            query += " AND stage = ?"
            params.append(stage.value)

        query += " ORDER BY decided_at DESC, decision_id DESC"

        rows = connection.execute(query, params).fetchall()
        return [self._row_to_decision(connection, row) for row in rows]

    def _row_to_decision(
        self, connection: sqlite3.Connection, row: tuple
    ) -> ScreeningDecision:
        (
            decision_id_str,
            project_id,
            publication_id_str,
            stage_str,
            outcome_str,
            reviewer_id,
            rationale,
            decided_at_str,
        ) = row

        assessment_rows = connection.execute(
            """
            SELECT criterion_id, criterion_name, criterion_type, criterion_stage,
                   criterion_is_required, assessment_value, notes
            FROM screening_criterion_assessments
            WHERE decision_id = ?
            ORDER BY criterion_id ASC
            """,
            (decision_id_str,),
        ).fetchall()

        assessments = [
            CriterionAssessment(
                criterion_id=UUID(a_row[0]),
                criterion_name=a_row[1],
                criterion_type=ScreeningCriterionType(a_row[2]),
                criterion_stage=ScreeningCriterionStage(a_row[3]),
                criterion_is_required=bool(a_row[4]),
                assessment_value=CriterionAssessmentValue(a_row[5]),
                notes=a_row[6],
            )
            for a_row in assessment_rows
        ]

        decided_at = datetime.fromisoformat(decided_at_str)
        if decided_at.tzinfo is None:
            decided_at = decided_at.replace(tzinfo=timezone.utc)

        return ScreeningDecision(
            decision_id=UUID(decision_id_str),
            project_id=project_id,
            publication_id=UUID(publication_id_str),
            stage=ScreeningStage(stage_str),
            outcome=ScreeningOutcome(outcome_str),
            reviewer_id=reviewer_id,
            rationale=rationale,
            criterion_assessments=assessments,
            decided_at=decided_at,
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


def default_screening_decision_repository() -> SqliteScreeningDecisionRepository:
    path = os.environ.get("SLR_DATABASE_PATH", "data/slr-platform.db")
    return SqliteScreeningDecisionRepository(path)
