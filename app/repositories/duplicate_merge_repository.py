from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Protocol, runtime_checkable
from uuid import UUID

from app.domain.deduplication import DuplicateGroupMergeRecord


@runtime_checkable
class DuplicateMergeRepository(Protocol):
    def save_merge(
        self, record: DuplicateGroupMergeRecord, *, connection: sqlite3.Connection | None = None
    ) -> None: ...
    def get_merge(
        self, project_id: str, group_id: str, *, connection: sqlite3.Connection | None = None
    ) -> DuplicateGroupMergeRecord | None: ...
    def list_merges_for_project(
        self, project_id: str, *, connection: sqlite3.Connection | None = None
    ) -> dict[str, DuplicateGroupMergeRecord]: ...
    def delete_for_project(self, project_id: str, *, connection: sqlite3.Connection | None = None) -> None: ...


class InMemoryDuplicateMergeRepository:
    def __init__(self) -> None:
        self._records: dict[tuple[str, str], DuplicateGroupMergeRecord] = {}

    def save_merge(self, record: DuplicateGroupMergeRecord, **_: object) -> None:
        self._records[(record.project_id, record.group_id)] = record

    def get_merge(self, project_id: str, group_id: str, **_: object) -> DuplicateGroupMergeRecord | None:
        return self._records.get((project_id, group_id))

    def list_merges_for_project(self, project_id: str, **_: object) -> dict[str, DuplicateGroupMergeRecord]:
        return {g: r for (p, g), r in self._records.items() if p == project_id}

    def delete_for_project(self, project_id: str, **_: object) -> None:
        for key in [key for key in self._records if key[0] == project_id]:
            del self._records[key]


class SqliteDuplicateMergeRepository:
    def __init__(self, database_path: str | Path) -> None:
        self._database_path = Path(database_path)

    def save_merge(self, record: DuplicateGroupMergeRecord, *, connection: sqlite3.Connection | None = None) -> None:
        def save(conn: sqlite3.Connection) -> None:
            conn.execute(
                "INSERT INTO duplicate_group_merges (project_id, group_id, canonical_record_id, merged_publication_ids, merged_at, status, pre_merge_snapshots) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    record.project_id,
                    record.group_id,
                    str(record.canonical_record_id),
                    json.dumps([str(i) for i in record.merged_publication_ids]),
                    record.merged_at.isoformat(),
                    record.status,
                    json.dumps([p.model_dump(mode="json") for p in record.pre_merge_snapshots], ensure_ascii=False),
                ),
            )

        if connection is not None:
            save(connection)
        else:
            with sqlite3.connect(self._database_path) as conn:
                save(conn)

    def get_merge(
        self, project_id: str, group_id: str, *, connection: sqlite3.Connection | None = None
    ) -> DuplicateGroupMergeRecord | None:
        def get(conn: sqlite3.Connection):
            return conn.execute(
                "SELECT canonical_record_id, merged_publication_ids, merged_at, status, pre_merge_snapshots FROM duplicate_group_merges WHERE project_id = ? AND group_id = ?",
                (project_id, group_id),
            ).fetchone()

        if connection is not None:
            row = get(connection)
        else:
            with sqlite3.connect(self._database_path) as conn:
                row = get(conn)
        return self._row(project_id, group_id, row) if row else None

    def list_merges_for_project(
        self, project_id: str, *, connection: sqlite3.Connection | None = None
    ) -> dict[str, DuplicateGroupMergeRecord]:
        def get(conn: sqlite3.Connection):
            return conn.execute(
                "SELECT group_id, canonical_record_id, merged_publication_ids, merged_at, status, pre_merge_snapshots FROM duplicate_group_merges WHERE project_id = ?",
                (project_id,),
            ).fetchall()

        if connection is not None:
            rows = get(connection)
        else:
            with sqlite3.connect(self._database_path) as conn:
                rows = get(conn)
        return {str(row[0]): self._row(project_id, str(row[0]), row[1:]) for row in rows}

    def delete_for_project(self, project_id: str, *, connection: sqlite3.Connection | None = None) -> None:
        if connection is not None:
            connection.execute("DELETE FROM duplicate_group_merges WHERE project_id = ?", (project_id,))
        else:
            with sqlite3.connect(self._database_path) as conn:
                conn.execute("DELETE FROM duplicate_group_merges WHERE project_id = ?", (project_id,))

    @staticmethod
    def _row(project_id: str, group_id: str, row: tuple[object, ...]) -> DuplicateGroupMergeRecord:
        return DuplicateGroupMergeRecord(
            project_id=project_id,
            group_id=group_id,
            canonical_record_id=UUID(str(row[0])),
            merged_publication_ids=tuple(UUID(value) for value in json.loads(str(row[1]))),
            merged_at=datetime.fromisoformat(str(row[2])),
            status=str(row[3]),
            pre_merge_snapshots=tuple(
                __import__("app.domain.publication", fromlist=["Publication"]).Publication.model_validate(value)
                for value in json.loads(str(row[4]))
            ),
        )


def default_duplicate_merge_repository() -> SqliteDuplicateMergeRepository:
    return SqliteDuplicateMergeRepository(os.environ.get("SLR_DATABASE_PATH", "data/slr-platform.db"))
