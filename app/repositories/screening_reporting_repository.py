from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from app.domain.screening import (
    CriterionAssessment,
    CriterionAssessmentValue,
    ScreeningCriterionEvaluationMode,
    ScreeningCriterionStage,
    ScreeningCriterionType,
    ScreeningDecision,
    ScreeningOutcome,
    ScreeningStage,
)


@dataclass(frozen=True, slots=True)
class AuditRow:
    decision: ScreeningDecision
    revision_index: int
    previous_outcome: ScreeningOutcome | None
    is_latest_for_reviewer: bool


class ScreeningReportingRepository:
    """Batch read adapter for audit/reporting; never uses decision N+1 hydration."""

    def __init__(self, database_path: str | Path) -> None:
        self._database_path = Path(database_path)

    def latest_decisions(self, project_id: str, reviewer_id: str) -> list[ScreeningDecision]:
        query = """
        WITH ranked AS (
          SELECT *, ROW_NUMBER() OVER (
            PARTITION BY publication_id, stage, reviewer_id ORDER BY decided_at DESC, decision_id DESC
          ) AS rn
          FROM screening_decisions WHERE project_id = ? AND reviewer_id = ?
        ) SELECT decision_id, project_id, publication_id, stage, outcome, reviewer_id, rationale,
                 decided_at, criterion_snapshot_schema_version
          FROM ranked WHERE rn = 1
        """
        with self._connect() as conn:
            rows = conn.execute(query, (project_id, reviewer_id)).fetchall()
            return self._hydrate(conn, rows)

    def latest_decisions_for_stage_all_reviewers(
        self, project_id: str, stage: ScreeningStage
    ) -> list[ScreeningDecision]:
        """Return one latest decision per publication/reviewer in a single batch read."""
        query = """
        WITH ranked AS (
          SELECT *, ROW_NUMBER() OVER (
            PARTITION BY publication_id, reviewer_id ORDER BY decided_at DESC, decision_id DESC
          ) AS rn
          FROM screening_decisions WHERE project_id = ? AND stage = ?
        ) SELECT decision_id, project_id, publication_id, stage, outcome, reviewer_id, rationale,
                 decided_at, criterion_snapshot_schema_version
          FROM ranked WHERE rn = 1
        """
        with self._connect() as conn:
            rows = conn.execute(query, (project_id, stage.value)).fetchall()
            return self._hydrate(conn, rows)

    def decisions_for_stage_outcome(
        self,
        project_id: str,
        reviewer_id: str,
        stage: ScreeningStage,
        outcome: ScreeningOutcome,
    ) -> list[ScreeningDecision]:
        query = """
            SELECT decision_id, project_id, publication_id, stage, outcome, reviewer_id,
                   rationale, decided_at, criterion_snapshot_schema_version
            FROM screening_decisions
            WHERE project_id = ? AND reviewer_id = ? AND stage = ? AND outcome = ?
            ORDER BY decided_at DESC, decision_id DESC
        """
        with self._connect() as conn:
            rows = conn.execute(query, (project_id, reviewer_id, stage.value, outcome.value)).fetchall()
            return self._hydrate(conn, rows)

    def audit_page(
        self,
        project_id: str,
        *,
        reviewer_id: str | None = None,
        publication_id: UUID | None = None,
        stage: ScreeningStage | None = None,
        outcome: ScreeningOutcome | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[AuditRow], int]:
        where: list[str] = []
        params: list[object] = []
        for column, value in (
            ("reviewer_id", reviewer_id),
            ("publication_id", str(publication_id) if publication_id else None),
            ("stage", stage.value if stage else None),
            ("outcome", outcome.value if outcome else None),
        ):
            if value is not None:
                where.append(f"{column} = ?")
                params.append(value)
        clause = " AND ".join(where) if where else "1 = 1"
        base = """
          WITH sequenced AS (
          SELECT decision_id, project_id, publication_id, stage, outcome, reviewer_id, rationale, decided_at,
                 criterion_snapshot_schema_version,
                 ROW_NUMBER() OVER (PARTITION BY publication_id, stage, reviewer_id ORDER BY decided_at ASC, decision_id ASC) AS revision_index,
                 LAG(outcome) OVER (PARTITION BY publication_id, stage, reviewer_id ORDER BY decided_at ASC, decision_id ASC) AS previous_outcome,
                 ROW_NUMBER() OVER (PARTITION BY publication_id, stage, reviewer_id ORDER BY decided_at DESC, decision_id DESC) AS latest_rank
            FROM screening_decisions WHERE project_id = ?
          )
        """
        with self._connect() as conn:
            total = conn.execute(
                base + f" SELECT COUNT(*) FROM sequenced WHERE {clause}",
                [project_id, *params],
            ).fetchone()[0]
            rows = conn.execute(
                base + f" SELECT * FROM sequenced WHERE {clause} "
                "ORDER BY decided_at DESC, decision_id DESC LIMIT ? OFFSET ?",
                [project_id, *params, limit, offset],
            ).fetchall()
            decisions = self._hydrate(conn, [row[:9] for row in rows])
        return [
            AuditRow(decision, int(row[9]), ScreeningOutcome(row[10]) if row[10] else None, row[11] == 1)
            for decision, row in zip(decisions, rows, strict=True)
        ], total

    def _hydrate(self, conn: sqlite3.Connection, rows: list[tuple]) -> list[ScreeningDecision]:
        if not rows:
            return []
        ids = [row[0] for row in rows]
        placeholders = ",".join("?" for _ in ids)
        assessments_by: dict[str, list[CriterionAssessment]] = {item: [] for item in ids}
        for item in conn.execute(
            f"""SELECT decision_id, criterion_id, criterion_name, criterion_description,
            criterion_type, criterion_stage, criterion_is_required, assessment_value, notes,
            evaluation_mode, metadata_rule, evaluated_metadata_value
            FROM screening_criterion_assessments WHERE decision_id IN ({placeholders}) ORDER BY criterion_id""",
            ids,
        ):
            assessments_by[item[0]].append(
                CriterionAssessment(
                    criterion_id=UUID(item[1]),
                    criterion_name=item[2],
                    criterion_description=item[3],
                    criterion_type=ScreeningCriterionType(item[4]),
                    criterion_stage=ScreeningCriterionStage(item[5]),
                    criterion_is_required=bool(item[6]),
                    assessment_value=CriterionAssessmentValue(item[7]),
                    notes=item[8],
                    evaluation_mode=ScreeningCriterionEvaluationMode(item[9]),
                    metadata_rule=json.loads(item[10]) if item[10] else None,
                    evaluated_metadata_value=json.loads(item[11]) if item[11] else None,
                )
            )
        reasons_by: dict[str, list[UUID]] = {item: [] for item in ids}
        for item in conn.execute(
            f"SELECT decision_id, criterion_id FROM screening_decision_exclusion_reasons WHERE decision_id IN ({placeholders}) ORDER BY criterion_id",
            ids,
        ):
            reasons_by[item[0]].append(UUID(item[1]))
        result = []
        for row in rows:
            timestamp = datetime.fromisoformat(row[7])
            result.append(
                ScreeningDecision(
                    decision_id=UUID(row[0]),
                    project_id=row[1],
                    publication_id=UUID(row[2]),
                    stage=ScreeningStage(row[3]),
                    outcome=ScreeningOutcome(row[4]),
                    reviewer_id=row[5],
                    rationale=row[6],
                    decided_at=timestamp if timestamp.tzinfo else timestamp.replace(tzinfo=timezone.utc),
                    criterion_snapshot_schema_version=int(row[8]),
                    criterion_assessments=assessments_by[row[0]],
                    exclusion_reason_criterion_ids=reasons_by[row[0]],
                )
            )
        return result

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._database_path)


def default_screening_reporting_repository() -> ScreeningReportingRepository:
    return ScreeningReportingRepository(os.environ.get("SLR_DATABASE_PATH", "data/slr-platform.db"))
