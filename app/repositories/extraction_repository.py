from __future__ import annotations

import json
import os
import sqlite3
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable
from uuid import UUID

from app.domain.extraction import (
    ExtractedGroupItemState,
    ExtractedValueState,
    ExtractionCompletenessStatus,
    ExtractionRecord,
    ExtractionRevision,
    ValueOrigin,
    ValueStatus,
)


class ExtractionRecordNotFoundError(Exception):
    pass


class ExtractionRecordConflictError(Exception):
    pass


class ExtractionRevisionConflictError(Exception):
    pass


class SqliteExtractionRepository:
    """Durable, append-only extraction snapshots with batched hydration."""

    def __init__(
        self, database_path: str | Path, *, query_observer: Callable[[str], None] | None = None
    ) -> None:
        self._database_path = Path(database_path)
        self._query_observer = query_observer
        self._database_path.parent.mkdir(parents=True, exist_ok=True)
        from app.repositories.extraction_template_repository import SqliteExtractionTemplateRepository

        SqliteExtractionTemplateRepository(self._database_path)

    def create_record(self, record: ExtractionRecord) -> ExtractionRecord:
        with self._connect() as connection:
            try:
                connection.execute(
                    """INSERT INTO extraction_records
                    (record_id, project_id, publication_id, template_id, template_version, current_status, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        str(record.record_id), record.project_id, str(record.publication_id), record.template_id,
                        record.template_version, record.current_status.value, record.created_at.isoformat(),
                        record.updated_at.isoformat(),
                    ),
                )
            except sqlite3.IntegrityError as exc:
                raise ExtractionRecordConflictError(
                    f"An extraction record already exists for project '{record.project_id}' and publication '{record.publication_id}'."
                ) from exc
        return record

    def get_record(self, project_id: str, publication_id: UUID) -> ExtractionRecord:
        with self._connect() as connection:
            row = connection.execute(
                """SELECT record_id, project_id, publication_id, template_id, template_version, current_status, created_at, updated_at
                FROM extraction_records WHERE project_id = ? AND publication_id = ?""",
                (project_id, str(publication_id)),
            ).fetchone()
        if row is None:
            raise ExtractionRecordNotFoundError(
                f"Extraction record for project '{project_id}' and publication '{publication_id}' was not found."
            )
        return _record_from_row(row)

    def list_records(self, project_id: str) -> list[ExtractionRecord]:
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT record_id, project_id, publication_id, template_id, template_version, current_status, created_at, updated_at
                FROM extraction_records WHERE project_id = ? ORDER BY publication_id ASC""",
                (project_id,),
            ).fetchall()
        return [_record_from_row(row) for row in rows]

    def append_revision(self, revision: ExtractionRevision) -> ExtractionRevision:
        with self._connect() as connection:
            record_row = connection.execute(
                "SELECT record_id, project_id, publication_id FROM extraction_records WHERE record_id = ?",
                (str(revision.record_id),),
            ).fetchone()
            if record_row is None:
                raise ExtractionRecordNotFoundError(f"Extraction record '{revision.record_id}' was not found.")
            if record_row[1] != revision.project_id or record_row[2] != str(revision.publication_id):
                raise ExtractionRevisionConflictError("Revision project_id and publication_id must match its extraction record.")
            next_index = connection.execute(
                "SELECT COALESCE(MAX(revision_index), 0) + 1 FROM extraction_revisions WHERE record_id = ?",
                (str(revision.record_id),),
            ).fetchone()[0]
            if revision.revision_index != next_index:
                raise ExtractionRevisionConflictError(
                    f"Revision index must be {next_index} for record '{revision.record_id}', got {revision.revision_index}."
                )
            try:
                connection.execute(
                    """INSERT INTO extraction_revisions
                    (revision_id, record_id, project_id, publication_id, revision_index, reviewer_id, completeness_status, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        str(revision.revision_id), str(revision.record_id), revision.project_id,
                        str(revision.publication_id), revision.revision_index, revision.reviewer_id,
                        revision.completeness_status.value, revision.created_at.isoformat(),
                    ),
                )
                self._insert_values(connection, revision.revision_id, revision.publication_values, None)
                for group_item in revision.group_items:
                    connection.execute(
                        """INSERT INTO extracted_group_items
                        (group_item_id, revision_id, group_key, item_index) VALUES (?, ?, ?, ?)""",
                        (str(group_item.group_item_id), str(revision.revision_id), group_item.group_key, group_item.item_index),
                    )
                    self._insert_values(connection, revision.revision_id, group_item.values, group_item.group_item_id)
                connection.execute(
                    "UPDATE extraction_records SET current_status = ?, updated_at = ? WHERE record_id = ?",
                    (revision.completeness_status.value, revision.created_at.isoformat(), str(revision.record_id)),
                )
            except sqlite3.IntegrityError as exc:
                raise ExtractionRevisionConflictError("Extraction revision could not be appended atomically.") from exc
        return revision

    def get_latest_revision(self, project_id: str, publication_id: UUID) -> ExtractionRevision | None:
        values = self.get_latest_revision_batch(project_id, [publication_id])
        return values.get(publication_id)

    def get_latest_revision_batch(
        self, project_id: str, publication_ids: list[UUID]
    ) -> dict[UUID, ExtractionRevision | None]:
        """Hydrate a page of latest snapshots in three bounded SQL queries."""
        if not publication_ids:
            return {}
        placeholders = ",".join("?" for _ in publication_ids)
        params = [project_id, *(str(value) for value in publication_ids)]
        with self._connect() as connection:
            records = connection.execute(
                f"""SELECT record_id, project_id, publication_id FROM extraction_records
                WHERE project_id = ? AND publication_id IN ({placeholders})""",
                params,
            ).fetchall()
            if not records:
                return {publication_id: None for publication_id in publication_ids}
            record_ids = [row[0] for row in records]
            record_placeholders = ",".join("?" for _ in record_ids)
            revisions = connection.execute(
                f"""WITH ranked AS (
                    SELECT revision_id, record_id, project_id, publication_id, revision_index, reviewer_id,
                           completeness_status, created_at,
                           ROW_NUMBER() OVER (PARTITION BY record_id ORDER BY revision_index DESC) AS rank
                    FROM extraction_revisions WHERE record_id IN ({record_placeholders})
                ) SELECT revision_id, record_id, project_id, publication_id, revision_index, reviewer_id,
                         completeness_status, created_at FROM ranked WHERE rank = 1""",
                record_ids,
            ).fetchall()
            hydrated = self._hydrate_revisions_with_connection(connection, revisions)
        result: dict[UUID, ExtractionRevision | None] = {
            publication_id: None for publication_id in publication_ids
        }
        for revision in hydrated:
            result[revision.publication_id] = revision
        return result

    def list_revision_history(self, project_id: str, publication_id: UUID) -> list[ExtractionRevision]:
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT revision_id, record_id, project_id, publication_id, revision_index, reviewer_id,
                   completeness_status, created_at FROM extraction_revisions
                WHERE project_id = ? AND publication_id = ? ORDER BY revision_index ASC""",
                (project_id, str(publication_id)),
            ).fetchall()
            return self._hydrate_revisions_with_connection(connection, rows)

    def delete_for_project(self, project_id: str, *, connection: sqlite3.Connection | None = None) -> None:
        if connection is not None:
            self._delete_for_project_with_connection(connection, project_id)
            return
        with self._connect() as owned_connection:
            self._delete_for_project_with_connection(owned_connection, project_id)

    def _delete_for_project_with_connection(self, connection: sqlite3.Connection, project_id: str) -> None:
        connection.execute("DELETE FROM project_extraction_configurations WHERE project_id = ?", (project_id,))
        connection.execute(
            """DELETE FROM extracted_values WHERE revision_id IN (
                SELECT revision_id FROM extraction_revisions WHERE project_id = ?
            )""",
            (project_id,),
        )
        connection.execute(
            """DELETE FROM extracted_group_items WHERE revision_id IN (
                SELECT revision_id FROM extraction_revisions WHERE project_id = ?
            )""",
            (project_id,),
        )
        connection.execute("DELETE FROM extraction_revisions WHERE project_id = ?", (project_id,))
        connection.execute("DELETE FROM extraction_records WHERE project_id = ?", (project_id,))

    def _insert_values(
        self,
        connection: sqlite3.Connection,
        revision_id: UUID,
        values: list[ExtractedValueState],
        group_item_id: UUID | None,
    ) -> None:
        connection.executemany(
            """INSERT INTO extracted_values (
            value_id, revision_id, group_item_id, field_key, status, origin,
            text_value, int_value, float_value, bool_value, unit_value, json_value,
            source_page, source_section, source_locator, source_quote, reviewer_note
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                (
                    str(value.value_id), str(revision_id), str(group_item_id) if group_item_id else None,
                    value.field_key, value.status.value, value.origin.value, value.text_value, value.int_value,
                    value.float_value, int(value.bool_value) if value.bool_value is not None else None,
                    value.unit_value, json.dumps(value.json_value) if value.json_value is not None else None,
                    value.source_page, value.source_section, value.source_locator, value.source_quote, value.reviewer_note,
                )
                for value in values
            ],
        )

    def _hydrate_revisions_with_connection(
        self, connection: sqlite3.Connection, rows: list[tuple]) -> list[ExtractionRevision]:
        if not rows:
            return []
        revision_ids = [row[0] for row in rows]
        placeholders = ",".join("?" for _ in revision_ids)
        child_rows = connection.execute(
            f"""SELECT 'group', group_item_id, revision_id, group_key, item_index,
                       NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL
                FROM extracted_group_items WHERE revision_id IN ({placeholders})
                UNION ALL
                SELECT 'value', value_id, revision_id, group_item_id, NULL,
                       field_key, status, origin, text_value, int_value, float_value, bool_value, unit_value, json_value,
                       source_page, source_section, source_locator, source_quote, reviewer_note,
                       NULL, NULL, NULL
                FROM extracted_values WHERE revision_id IN ({placeholders})
                ORDER BY 3, 1, 5, 4, 6""",
            [*revision_ids, *revision_ids],
        ).fetchall()
        publication_values: dict[str, list[ExtractedValueState]] = defaultdict(list)
        group_items: dict[str, dict[str, ExtractedGroupItemState]] = defaultdict(dict)
        group_values: dict[str, list[ExtractedValueState]] = defaultdict(list)
        group_metadata: dict[str, tuple[str, int, str]] = {}
        for child in child_rows:
            if child[0] == "group":
                group_metadata[child[1]] = (child[3], child[4], child[2])
                continue
            value = _value_from_child_row(child)
            group_item_id = child[3]
            if group_item_id is None:
                publication_values[child[2]].append(value)
            else:
                group_values[group_item_id].append(value)
        for group_item_id, (group_key, item_index, revision_id) in group_metadata.items():
            group_items[revision_id][group_item_id] = ExtractedGroupItemState(
                group_item_id=UUID(group_item_id), group_key=group_key, item_index=item_index,
                values=group_values[group_item_id],
            )
        return [
            ExtractionRevision(
                revision_id=UUID(row[0]), record_id=UUID(row[1]), project_id=row[2], publication_id=UUID(row[3]),
                revision_index=row[4], reviewer_id=row[5], completeness_status=ExtractionCompletenessStatus(row[6]),
                created_at=_as_datetime(row[7]), publication_values=publication_values[row[0]],
                group_items=sorted(group_items[row[0]].values(), key=lambda item: (item.group_key, item.item_index)),
            )
            for row in rows
        ]

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._database_path)
        connection.execute("PRAGMA foreign_keys = ON")
        if self._query_observer is not None:
            connection.set_trace_callback(self._query_observer)
        return connection


def _record_from_row(row: tuple) -> ExtractionRecord:
    return ExtractionRecord(
        record_id=UUID(row[0]), project_id=row[1], publication_id=UUID(row[2]), template_id=row[3],
        template_version=row[4], current_status=ExtractionCompletenessStatus(row[5]),
        created_at=_as_datetime(row[6]), updated_at=_as_datetime(row[7]),
    )


def _value_from_child_row(row: tuple) -> ExtractedValueState:
    return ExtractedValueState(
        value_id=UUID(row[1]), field_key=row[5], status=ValueStatus(row[6]), origin=ValueOrigin(row[7]),
        text_value=row[8], int_value=row[9], float_value=row[10],
        bool_value=bool(row[11]) if row[11] is not None else None, unit_value=row[12],
        json_value=json.loads(row[13]) if row[13] is not None else None, source_page=row[14],
        source_section=row[15], source_locator=row[16], source_quote=row[17], reviewer_note=row[18],
    )


def _as_datetime(value: str) -> datetime:
    result = datetime.fromisoformat(value)
    return result if result.tzinfo is not None else result.replace(tzinfo=timezone.utc)


def default_extraction_repository() -> SqliteExtractionRepository:
    return SqliteExtractionRepository(os.environ.get("SLR_DATABASE_PATH", "data/slr-platform.db"))
