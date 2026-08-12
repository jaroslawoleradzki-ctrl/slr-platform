from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from app.domain.conflict_resolution import ConflictResolution, ResolvedOutcome
from app.domain.screening import ScreeningStage


class SqliteConflictResolutionRepository:
    def __init__(self, database_path: str | Path) -> None:
        self._database_path = Path(database_path)
        from app.repositories.screening_decision_repository import SqliteScreeningDecisionRepository

        SqliteScreeningDecisionRepository(self._database_path)

    def save(self, value: ConflictResolution, links: list[tuple[UUID, str, ResolvedOutcome]]) -> ConflictResolution:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO screening_conflict_resolutions (resolution_id, project_id, publication_id, stage, decision_set_key, resolved_outcome, resolver_id, rationale, resolved_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    str(value.resolution_id),
                    value.project_id,
                    str(value.publication_id),
                    value.stage.value,
                    value.decision_set_key,
                    value.resolved_outcome.value,
                    value.resolver_id,
                    value.rationale,
                    value.resolved_at.isoformat(),
                ),
            )
            conn.executemany(
                "INSERT INTO screening_conflict_resolution_decisions (resolution_id, decision_id, reviewer_id, outcome) VALUES (?, ?, ?, ?)",
                [(str(value.resolution_id), str(d), r, o.value) for d, r, o in links],
            )
        return value

    def latest_batch(self, project_id: str, stage: ScreeningStage) -> dict[UUID, ConflictResolution]:
        query = """WITH ranked AS (SELECT *, ROW_NUMBER() OVER (PARTITION BY publication_id ORDER BY resolved_at DESC, resolution_id DESC) rank FROM screening_conflict_resolutions WHERE project_id=? AND stage=?) SELECT resolution_id, project_id, publication_id, stage, decision_set_key, resolved_outcome, resolver_id, rationale, resolved_at FROM ranked WHERE rank=1"""
        with self._connect() as conn:
            rows = conn.execute(query, (project_id, stage.value)).fetchall()
        values = self._rows_to_domains(rows)
        return {value.publication_id: value for value in values}

    def history(self, project_id: str, publication_id: UUID, stage: ScreeningStage) -> list[ConflictResolution]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT resolution_id, project_id, publication_id, stage, decision_set_key, resolved_outcome, resolver_id, rationale, resolved_at FROM screening_conflict_resolutions WHERE project_id=? AND publication_id=? AND stage=? ORDER BY resolved_at DESC, resolution_id DESC",
                (project_id, str(publication_id), stage.value),
            ).fetchall()
        return self._rows_to_domains(rows)

    def audit_events(self, project_id: str, stage: ScreeningStage | None = None) -> list[ConflictResolution]:
        query = "SELECT resolution_id, project_id, publication_id, stage, decision_set_key, resolved_outcome, resolver_id, rationale, resolved_at FROM screening_conflict_resolutions WHERE project_id=?"
        params: list[object] = [project_id]
        if stage is not None:
            query += " AND stage=?"
            params.append(stage.value)
        query += " ORDER BY resolved_at DESC, resolution_id DESC"
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return self._rows_to_domains(rows)

    def links_batch(self, resolution_ids: list[UUID]) -> dict[UUID, tuple[tuple[UUID, str, ResolvedOutcome], ...]]:
        if not resolution_ids:
            return {}
        placeholders = ",".join("?" for _ in resolution_ids)
        result: dict[UUID, list[tuple[UUID, str, ResolvedOutcome]]] = {
            resolution_id: [] for resolution_id in resolution_ids
        }
        with self._connect() as conn:
            rows = conn.execute(
                f"""SELECT resolution_id, decision_id, reviewer_id, outcome
                FROM screening_conflict_resolution_decisions
                WHERE resolution_id IN ({placeholders})
                ORDER BY resolution_id, reviewer_id, decision_id""",
                [str(item) for item in resolution_ids],
            ).fetchall()
        for row in rows:
            result[UUID(row[0])].append((UUID(row[1]), row[2], ResolvedOutcome(row[3])))
        return {key: tuple(value) for key, value in result.items()}

    def links(self, resolution_id: UUID) -> list[tuple[UUID, str, ResolvedOutcome]]:
        with self._connect() as conn:
            return [
                (UUID(row[0]), row[1], ResolvedOutcome(row[2]))
                for row in conn.execute(
                    "SELECT decision_id, reviewer_id, outcome FROM screening_conflict_resolution_decisions WHERE resolution_id=? ORDER BY reviewer_id",
                    (str(resolution_id),),
                )
            ]

    def delete_for_project(self, project_id: str, *, connection: sqlite3.Connection | None = None) -> None:
        def delete(conn: sqlite3.Connection) -> None:
            conn.execute(
                """DELETE FROM screening_conflict_resolution_decisions
                WHERE resolution_id IN (
                    SELECT resolution_id FROM screening_conflict_resolutions WHERE project_id = ?
                )""",
                (project_id,),
            )
            conn.execute("DELETE FROM screening_conflict_resolutions WHERE project_id=?", (project_id,))

        if connection is not None:
            delete(connection)
        else:
            with self._connect() as conn:
                delete(conn)

    def _rows_to_domains(self, rows: list[tuple]) -> list[ConflictResolution]:
        links = self.links_batch([UUID(row[0]) for row in rows])
        values: list[ConflictResolution] = []
        for row in rows:
            resolution_id = UUID(row[0])
            time = datetime.fromisoformat(row[8])
            time = time if time.tzinfo else time.replace(tzinfo=timezone.utc)
            values.append(
                ConflictResolution(
                    resolution_id,
                    row[1],
                    UUID(row[2]),
                    ScreeningStage(row[3]),
                    row[4],
                    ResolvedOutcome(row[5]),
                    row[6],
                    row[7],
                    time,
                    tuple(item[0] for item in links.get(resolution_id, ())),
                )
            )
        return values

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._database_path)


def default_conflict_resolution_repository() -> SqliteConflictResolutionRepository:
    return SqliteConflictResolutionRepository(os.environ.get("SLR_DATABASE_PATH", "data/slr-platform.db"))
