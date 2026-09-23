from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Protocol, runtime_checkable
from uuid import UUID

from app.domain.author import Author
from app.domain.identifiers import Identifier
from app.domain.pre_screening import (
    PreScreeningArchivedRecord,
    PreScreeningRemovalReason,
)
from app.domain.provenance import ProvenanceEntry


@runtime_checkable
class PreScreeningArchiveRepository(Protocol):
    """Abstraction for persisting and retrieving archived publications removed during Pre-Screening."""

    def archive_record(
        self, record: PreScreeningArchivedRecord, *, connection: sqlite3.Connection | None = None
    ) -> PreScreeningArchivedRecord: ...

    def get_archived_record(
        self, project_id: str, record_id: UUID, *, connection: sqlite3.Connection | None = None
    ) -> PreScreeningArchivedRecord | None: ...

    def list_archived_for_project(
        self,
        project_id: str,
        *,
        import_id: UUID | None = None,
        search: str | None = None,
        offset: int = 0,
        limit: int = 50,
        connection: sqlite3.Connection | None = None,
    ) -> list[PreScreeningArchivedRecord]: ...

    def count_archived_for_project(
        self,
        project_id: str,
        *,
        import_id: UUID | None = None,
        search: str | None = None,
        connection: sqlite3.Connection | None = None,
    ) -> int: ...

    def delete_archived_record(
        self, project_id: str, record_id: UUID, *, connection: sqlite3.Connection | None = None
    ) -> bool: ...

    def delete_for_project(
        self, project_id: str, *, connection: sqlite3.Connection | None = None
    ) -> None: ...


class InMemoryPreScreeningArchiveRepository:
    """In-memory implementation of PreScreeningArchiveRepository for demo and unit tests."""

    def __init__(self) -> None:
        self._records: dict[tuple[str, UUID], PreScreeningArchivedRecord] = {}

    def archive_record(
        self, record: PreScreeningArchivedRecord, *, connection: sqlite3.Connection | None = None
    ) -> PreScreeningArchivedRecord:
        self._records[(record.project_id, record.record_id)] = record
        return record

    def get_archived_record(
        self, project_id: str, record_id: UUID, *, connection: sqlite3.Connection | None = None
    ) -> PreScreeningArchivedRecord | None:
        return self._records.get((project_id, record_id))

    def list_archived_for_project(
        self,
        project_id: str,
        *,
        import_id: UUID | None = None,
        search: str | None = None,
        offset: int = 0,
        limit: int = 50,
        connection: sqlite3.Connection | None = None,
    ) -> list[PreScreeningArchivedRecord]:
        matching: list[PreScreeningArchivedRecord] = []
        for (p_id, _), rec in sorted(
            self._records.items(), key=lambda item: (item[1].removed_at, item[1].record_id), reverse=True
        ):
            if p_id != project_id:
                continue
            if import_id is not None and rec.import_id != import_id:
                continue
            if search and search.strip():
                term = search.strip().casefold()
                text = f"{rec.title} {' '.join(a.display_name for a in rec.authors)}".casefold()
                if term not in text:
                    continue
            matching.append(rec)
        return matching[offset : offset + limit]

    def count_archived_for_project(
        self,
        project_id: str,
        *,
        import_id: UUID | None = None,
        search: str | None = None,
        connection: sqlite3.Connection | None = None,
    ) -> int:
        count = 0
        for (p_id, _), rec in self._records.items():
            if p_id != project_id:
                continue
            if import_id is not None and rec.import_id != import_id:
                continue
            if search and search.strip():
                term = search.strip().casefold()
                text = f"{rec.title} {' '.join(a.display_name for a in rec.authors)}".casefold()
                if term not in text:
                    continue
            count += 1
        return count

    def delete_archived_record(
        self, project_id: str, record_id: UUID, *, connection: sqlite3.Connection | None = None
    ) -> bool:
        return self._records.pop((project_id, record_id), None) is not None

    def delete_for_project(
        self, project_id: str, *, connection: sqlite3.Connection | None = None
    ) -> None:
        self._records = {k: v for k, v in self._records.items() if k[0] != project_id}


class SqlitePreScreeningArchiveRepository:
    """Durable SQLite-backed repository for archived publications removed during Pre-Screening."""

    def __init__(self, database_path: str | Path) -> None:
        self._database_path = Path(database_path)
        self._database_path.parent.mkdir(parents=True, exist_ok=True)
        self._apply_migrations()

    def archive_record(
        self, record: PreScreeningArchivedRecord, *, connection: sqlite3.Connection | None = None
    ) -> PreScreeningArchivedRecord:
        def query(conn: sqlite3.Connection) -> None:
            conn.execute(
                """
                INSERT INTO pre_screening_archive (
                    archive_id, project_id, record_id, import_id, provider,
                    title, publication_year, authors, identifiers, document_type,
                    language, provenance, document, removal_reason, removal_notes,
                    removed_by, removed_at, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(project_id, record_id) DO UPDATE SET
                    archive_id = excluded.archive_id,
                    import_id = COALESCE(pre_screening_archive.import_id, excluded.import_id),
                    provider = COALESCE(pre_screening_archive.provider, excluded.provider),
                    title = excluded.title,
                    publication_year = excluded.publication_year,
                    authors = excluded.authors,
                    identifiers = excluded.identifiers,
                    document_type = excluded.document_type,
                    language = excluded.language,
                    provenance = excluded.provenance,
                    document = excluded.document,
                    removal_reason = excluded.removal_reason,
                    removal_notes = excluded.removal_notes,
                    removed_by = excluded.removed_by,
                    removed_at = excluded.removed_at
                """,
                (
                    str(record.archive_id),
                    record.project_id,
                    str(record.record_id),
                    str(record.import_id) if record.import_id is not None else None,
                    record.provider,
                    record.title,
                    record.publication_year,
                    json.dumps([a.model_dump(mode="json") for a in record.authors], ensure_ascii=False),
                    json.dumps([i.model_dump(mode="json") for i in record.identifiers], ensure_ascii=False),
                    record.document_type,
                    record.language,
                    json.dumps([p.model_dump(mode="json") for p in record.provenance], ensure_ascii=False),
                    json.dumps(record.document, ensure_ascii=False),
                    record.removal_reason.value,
                    record.removal_notes,
                    record.removed_by,
                    record.removed_at.isoformat(),
                    record.created_at.isoformat(),
                ),
            )

        if connection is not None:
            query(connection)
        else:
            with self._connect() as conn:
                query(conn)
        return record

    def get_archived_record(
        self, project_id: str, record_id: UUID, *, connection: sqlite3.Connection | None = None
    ) -> PreScreeningArchivedRecord | None:
        def query(conn: sqlite3.Connection) -> PreScreeningArchivedRecord | None:
            row = conn.execute(
                """
                SELECT archive_id, project_id, record_id, import_id, provider,
                       title, publication_year, authors, identifiers, document_type,
                       language, provenance, document, removal_reason, removal_notes,
                       removed_by, removed_at, created_at
                FROM pre_screening_archive
                WHERE project_id = ? AND record_id = ?
                LIMIT 1
                """,
                (project_id, str(record_id)),
            ).fetchone()
            if row is None:
                return None
            return self._row_to_record(row)

        if connection is not None:
            return query(connection)
        with self._connect() as conn:
            return query(conn)

    def list_archived_for_project(
        self,
        project_id: str,
        *,
        import_id: UUID | None = None,
        search: str | None = None,
        offset: int = 0,
        limit: int = 50,
        connection: sqlite3.Connection | None = None,
    ) -> list[PreScreeningArchivedRecord]:
        def query(conn: sqlite3.Connection) -> list[PreScreeningArchivedRecord]:
            params: list[object] = [project_id]
            where_clauses = ["project_id = ?"]

            if import_id is not None:
                where_clauses.append("import_id = ?")
                params.append(str(import_id))

            if search and search.strip():
                term = f"%{search.strip().casefold()}%"
                where_clauses.append("(LOWER(title) LIKE ? OR LOWER(authors) LIKE ? OR LOWER(identifiers) LIKE ?)")
                params.extend([term, term, term])

            sql = f"""
                SELECT archive_id, project_id, record_id, import_id, provider,
                       title, publication_year, authors, identifiers, document_type,
                       language, provenance, document, removal_reason, removal_notes,
                       removed_by, removed_at, created_at
                FROM pre_screening_archive
                WHERE {" AND ".join(where_clauses)}
                ORDER BY removed_at DESC, created_at DESC, rowid DESC
                LIMIT ? OFFSET ?
            """
            params.extend([limit, offset])
            rows = conn.execute(sql, params).fetchall()
            return [self._row_to_record(row) for row in rows]

        if connection is not None:
            return query(connection)
        with self._connect() as conn:
            return query(conn)

    def count_archived_for_project(
        self,
        project_id: str,
        *,
        import_id: UUID | None = None,
        search: str | None = None,
        connection: sqlite3.Connection | None = None,
    ) -> int:
        def query(conn: sqlite3.Connection) -> int:
            params: list[object] = [project_id]
            where_clauses = ["project_id = ?"]

            if import_id is not None:
                where_clauses.append("import_id = ?")
                params.append(str(import_id))

            if search and search.strip():
                term = f"%{search.strip().casefold()}%"
                where_clauses.append("(LOWER(title) LIKE ? OR LOWER(authors) LIKE ? OR LOWER(identifiers) LIKE ?)")
                params.extend([term, term, term])

            sql = f"""
                SELECT COUNT(*)
                FROM pre_screening_archive
                WHERE {" AND ".join(where_clauses)}
            """
            row = conn.execute(sql, params).fetchone()
            return int(row[0])

        if connection is not None:
            return query(connection)
        with self._connect() as conn:
            return query(conn)

    def delete_archived_record(
        self, project_id: str, record_id: UUID, *, connection: sqlite3.Connection | None = None
    ) -> bool:
        def query(conn: sqlite3.Connection) -> bool:
            cursor = conn.execute(
                "DELETE FROM pre_screening_archive WHERE project_id = ? AND record_id = ?",
                (project_id, str(record_id)),
            )
            return cursor.rowcount > 0

        if connection is not None:
            return query(connection)
        with self._connect() as conn:
            return query(conn)

    def delete_for_project(
        self, project_id: str, *, connection: sqlite3.Connection | None = None
    ) -> None:
        if connection is not None:
            connection.execute(
                "DELETE FROM pre_screening_archive WHERE project_id = ?", (project_id,)
            )
        else:
            with self._connect() as conn:
                conn.execute(
                    "DELETE FROM pre_screening_archive WHERE project_id = ?", (project_id,)
                )

    @staticmethod
    def _row_to_record(row: tuple[object, ...]) -> PreScreeningArchivedRecord:
        authors_raw = json.loads(str(row[7]))
        identifiers_raw = json.loads(str(row[8]))
        provenance_raw = json.loads(str(row[11]))
        document_raw = json.loads(str(row[12]))

        return PreScreeningArchivedRecord(
            archive_id=UUID(str(row[0])),
            project_id=str(row[1]),
            record_id=UUID(str(row[2])),
            import_id=UUID(str(row[3])) if row[3] is not None else None,
            provider=str(row[4]) if row[4] is not None else None,
            title=str(row[5]),
            publication_year=int(str(row[6])) if row[6] is not None else None,
            authors=[Author.model_validate(a) for a in authors_raw],
            identifiers=[Identifier.model_validate(i) for i in identifiers_raw],
            document_type=str(row[9]) if row[9] is not None else None,
            language=str(row[10]) if row[10] is not None else None,
            provenance=[ProvenanceEntry.model_validate(p) for p in provenance_raw],
            document=document_raw,
            removal_reason=PreScreeningRemovalReason(str(row[13])),
            removal_notes=str(row[14]) if row[14] is not None else None,
            removed_by=str(row[15]),
            removed_at=datetime.fromisoformat(str(row[16])),
            created_at=datetime.fromisoformat(str(row[17])),
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


_default_repo: SqlitePreScreeningArchiveRepository | None = None


def default_pre_screening_archive_repository() -> SqlitePreScreeningArchiveRepository:
    path = os.environ.get("SLR_DATABASE_PATH", "data/slr-platform.db")
    return SqlitePreScreeningArchiveRepository(path)
