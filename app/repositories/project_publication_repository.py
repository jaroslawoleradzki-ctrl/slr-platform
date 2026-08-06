import json
import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol, runtime_checkable
from uuid import UUID

from app.domain.author import Author
from app.domain.identifiers import Identifier, IdentifierType
from app.domain.provenance import ProvenanceEntry
from app.domain.publication import Publication

_TIME = datetime(2026, 7, 1, 10, 0, tzinfo=timezone.utc)


@dataclass(frozen=True, slots=True)
class PublicationImportResult:
    imported_count: int
    skipped_count: int
    working_collection_count: int


class ProjectNotFoundError(Exception):
    """Raised when a requested project_id does not exist in the repository."""

    def __init__(self, project_id: str) -> None:
        self.project_id = project_id
        super().__init__(f"Project '{project_id}' not found.")


@runtime_checkable
class ProjectPublicationRepository(Protocol):
    """Abstraction for persisting and retrieving publication collections for an SLR project.

    Responsibilities:
    - Single entry point for managing project Working Collections.
    - Preserving record order via publication positions.
    - Idempotent import of provider source records.
    """

    def get_publications(self, project_id: str) -> list[Publication]:
        """Retrieve publications for a project or raise ProjectNotFoundError."""
        ...

    def add_publications(
        self,
        project_id: str,
        publications: list[Publication],
    ) -> int:
        """Append publications to a project's Working Collection and return new total count."""
        ...

    def import_source_publications(
        self,
        project_id: str,
        publications: list[Publication],
    ) -> PublicationImportResult:
        """Atomically import publications unique by provider and source id within a project."""
        ...

    def count_by_project(self, project_id: str) -> int:
        """Return total publication count for a project or raise ProjectNotFoundError."""
        ...

    def replace_publications(
        self,
        project_id: str,
        publications: list[Publication],
    ) -> None:
        """Replace a project's collection after a normalization or cleanup transformation."""
        ...


class DemoProjectPublicationRepository:
    """Temporary in-memory demo repository providing sample SLR project publications.

    Boundary Note:
    This adapter is a temporary demo implementation for Phase 6.3.
    Full project storage and persistence will be introduced in future phases.
    """

    def __init__(self) -> None:
        self._projects_data: dict[str, list[Publication]] = {
            "lean_energy": [
                Publication(
                    record_id=UUID("00000000-0000-0000-0000-000000000101"),
                    title="Energy reduction through lean production in auto manufacturing: A systematic review",
                    authors=[Author(display_name="Smith, J."), Author(display_name="Kowalski, P.")],
                    publication_year=2021,
                    identifiers=[
                        Identifier(type=IdentifierType.DOI, value="10.1016/j.jclepro.2021.102834"),
                        Identifier(type=IdentifierType.OPENALEX, value="W3128349201"),
                    ],
                    provenance=[ProvenanceEntry(source="OpenAlex", source_record_id="W3128349201")],
                    created_at=_TIME,
                ),
                Publication(
                    record_id=UUID("00000000-0000-0000-0000-000000000102"),
                    title="Energy reduction through lean production in automotive manufacturing: Systematic Review",
                    authors=[Author(display_name="Smith, John"), Author(display_name="Kowalski, Piotr")],
                    publication_year=2021,
                    identifiers=[
                        Identifier(type=IdentifierType.DOI, value="10.1016/j.jclepro.2021.102834"),
                        Identifier(type=IdentifierType.OPENALEX, value="W3128349201"),
                    ],
                    provenance=[ProvenanceEntry(source="Crossref", source_record_id="10.1016/j.jclepro.2021.102834")],
                    created_at=_TIME,
                ),
                Publication(
                    record_id=UUID("00000000-0000-0000-0000-000000000201"),
                    title="Applying Kaizen principles to lower electricity consumption in foundry operations",
                    authors=[Author(display_name="Müller, H."), Author(display_name="Schmidt, A.")],
                    publication_year=2019,
                    identifiers=[
                        Identifier(type=IdentifierType.DOI, value="10.1007/s00170-019-04122-z"),
                        Identifier(type=IdentifierType.PMID, value="31204912"),
                    ],
                    provenance=[ProvenanceEntry(source="Semantic Scholar", source_record_id="S2-31204912")],
                    created_at=_TIME,
                ),
                Publication(
                    record_id=UUID("00000000-0000-0000-0000-000000000202"),
                    title="Applying Kaizen principles to lower electricity consumption in foundry operations.",
                    authors=[Author(display_name="Muller, H."), Author(display_name="Schmidt, A.")],
                    publication_year=2019,
                    identifiers=[
                        Identifier(type=IdentifierType.DOI, value="10.1007/s00170-019-04122-z"),
                        Identifier(type=IdentifierType.PMID, value="31204912"),
                    ],
                    provenance=[ProvenanceEntry(source="RIS file (Google Scholar export)", source_record_id="IMP-002")],
                    created_at=_TIME,
                ),
                Publication(
                    record_id=UUID("00000000-0000-0000-0000-000000000301"),
                    title="Unique publication on industrial heat recovery without duplicates",
                    authors=[Author(display_name="Taylor, R.")],
                    publication_year=2024,
                    identifiers=[
                        Identifier(type=IdentifierType.DOI, value="10.1016/j.enercon.2024.109988"),
                    ],
                    provenance=[ProvenanceEntry(source="OpenAlex", source_record_id="W99887766")],
                    created_at=_TIME,
                ),
            ],
            "ai_architecture": [],
        }

    def get_publications(self, project_id: str) -> list[Publication]:
        if project_id not in self._projects_data:
            raise ProjectNotFoundError(project_id)
        return list(self._projects_data[project_id])

    def count_by_project(self, project_id: str) -> int:
        if project_id not in self._projects_data:
            raise ProjectNotFoundError(project_id)
        return len(self._projects_data[project_id])

    def add_publications(
        self,
        project_id: str,
        publications: list[Publication],
    ) -> int:
        if project_id not in self._projects_data:
            raise ProjectNotFoundError(project_id)
        self._projects_data[project_id].extend(publications)
        return len(self._projects_data[project_id])

    def import_source_publications(
        self,
        project_id: str,
        publications: list[Publication],
    ) -> PublicationImportResult:
        if project_id not in self._projects_data:
            raise ProjectNotFoundError(project_id)

        existing_keys = {
            self._source_key(publication)
            for publication in self._projects_data[project_id]
            if publication.provenance
        }
        new_publications: list[Publication] = []
        skipped_count = 0
        for publication in publications:
            key = self._source_key(publication)
            if key in existing_keys:
                skipped_count += 1
                continue
            existing_keys.add(key)
            new_publications.append(publication)

        self._projects_data[project_id].extend(new_publications)
        return PublicationImportResult(
            imported_count=len(new_publications),
            skipped_count=skipped_count,
            working_collection_count=len(self._projects_data[project_id]),
        )

    def replace_publications(
        self,
        project_id: str,
        publications: list[Publication],
    ) -> None:
        if project_id not in self._projects_data:
            raise ProjectNotFoundError(project_id)
        self._projects_data[project_id] = list(publications)

    @staticmethod
    def _source_key(publication: Publication) -> tuple[str, str]:
        if not publication.provenance:
            raise ValueError("source publication requires provenance")
        provenance = publication.provenance[0]
        return (
            provenance.source.strip().casefold(),
            provenance.source_record_id.strip(),
        )


demo_project_publication_repository = DemoProjectPublicationRepository()


class SqliteProjectPublicationRepository:
    """Durable project-scoped Working Collection backed by SQLite."""

    _KNOWN_PROJECT_IDS = frozenset({"lean_energy", "ai_architecture"})

    def __init__(self, database_path: str | Path) -> None:
        self._database_path = Path(database_path)
        self._database_path.parent.mkdir(parents=True, exist_ok=True)
        self._apply_migrations()

    def get_publications(
        self, project_id: str, *, connection: sqlite3.Connection | None = None
    ) -> list[Publication]:
        self._ensure_project(project_id, connection=connection)
        if connection is not None:
            return self._get_publications_with_conn(connection, project_id)
        with self._connect() as conn:
            return self._get_publications_with_conn(conn, project_id)

    def _get_publications_with_conn(
        self, connection: sqlite3.Connection, project_id: str
    ) -> list[Publication]:
        rows = connection.execute(
            """
            SELECT document
            FROM project_publications
            WHERE project_id = ?
            ORDER BY position ASC, rowid ASC
            """,
            (project_id,),
        ).fetchall()
        return [Publication.model_validate(json.loads(row[0])) for row in rows]

    def count_by_project(
        self, project_id: str, *, connection: sqlite3.Connection | None = None
    ) -> int:
        self._ensure_project(project_id, connection=connection)
        if connection is not None:
            row = connection.execute(
                "SELECT COUNT(*) FROM project_publications WHERE project_id = ?",
                (project_id,),
            ).fetchone()
            return int(row[0])
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM project_publications WHERE project_id = ?",
                (project_id,),
            ).fetchone()
            return int(row[0])

    def add_publications(
        self,
        project_id: str,
        publications: list[Publication],
        *,
        connection: sqlite3.Connection | None = None,
    ) -> int:
        self._ensure_project(project_id, connection=connection)
        if connection is not None:
            self._add_publications_with_conn(connection, project_id, publications)
            return len(self._get_publications_with_conn(connection, project_id))
        with self._connect() as conn:
            self._add_publications_with_conn(conn, project_id, publications)
            return len(self._get_publications_with_conn(conn, project_id))

    def _add_publications_with_conn(
        self,
        connection: sqlite3.Connection,
        project_id: str,
        publications: list[Publication],
    ) -> None:
        next_position = self._next_position(connection, project_id)
        for offset, publication in enumerate(publications):
            self._insert_or_replace(
                connection, project_id, publication, next_position + offset
            )

    def import_source_publications(
        self,
        project_id: str,
        publications: list[Publication],
        *,
        connection: sqlite3.Connection | None = None,
    ) -> PublicationImportResult:
        self._ensure_project(project_id, connection=connection)
        existing_pubs = self.get_publications(project_id, connection=connection)
        existing_keys = {
            self._source_key(publication)
            for publication in existing_pubs
            if publication.provenance
        }
        new_publications: list[Publication] = []
        for publication in publications:
            key = self._source_key(publication)
            if key in existing_keys:
                continue
            existing_keys.add(key)
            new_publications.append(publication)

        if connection is not None:
            next_position = self._next_position(connection, project_id)
            for offset, publication in enumerate(new_publications):
                self._insert_or_replace(
                    connection, project_id, publication, next_position + offset
                )
            working_count = len(self._get_publications_with_conn(connection, project_id))
        else:
            with self._connect() as conn:
                next_position = self._next_position(conn, project_id)
                for offset, publication in enumerate(new_publications):
                    self._insert_or_replace(
                        conn, project_id, publication, next_position + offset
                    )
                working_count = len(self._get_publications_with_conn(conn, project_id))

        return PublicationImportResult(
            imported_count=len(new_publications),
            skipped_count=len(publications) - len(new_publications),
            working_collection_count=working_count,
        )

    def replace_publications(
        self,
        project_id: str,
        publications: list[Publication],
        *,
        connection: sqlite3.Connection | None = None,
    ) -> None:
        self._ensure_project(project_id, connection=connection)
        if connection is not None:
            self._replace_publications_with_conn(connection, project_id, publications)
        else:
            with self._connect() as conn:
                self._replace_publications_with_conn(conn, project_id, publications)

    def _replace_publications_with_conn(
        self,
        connection: sqlite3.Connection,
        project_id: str,
        publications: list[Publication],
    ) -> None:
        connection.execute(
            "DELETE FROM project_publications WHERE project_id = ?",
            (project_id,),
        )
        for position, publication in enumerate(publications):
            self._insert_or_replace(connection, project_id, publication, position)

    def _ensure_project(
        self, project_id: str, *, connection: sqlite3.Connection | None = None
    ) -> None:
        if project_id in self._KNOWN_PROJECT_IDS:
            return
        if connection is not None:
            exists = connection.execute(
                "SELECT 1 FROM project_publications WHERE project_id = ? LIMIT 1",
                (project_id,),
            ).fetchone()
        else:
            with self._connect() as conn:
                exists = conn.execute(
                    "SELECT 1 FROM project_publications WHERE project_id = ? LIMIT 1",
                    (project_id,),
                ).fetchone()
        if exists is None:
            raise ProjectNotFoundError(project_id)

    @staticmethod
    def _source_key(publication: Publication) -> tuple[str, str]:
        if not publication.provenance:
            raise ValueError("source publication requires provenance")
        provenance = publication.provenance[0]
        return (
            provenance.source.strip().casefold(),
            provenance.source_record_id.strip(),
        )

    @staticmethod
    def _next_position(connection: sqlite3.Connection, project_id: str) -> int:
        row = connection.execute(
            "SELECT COALESCE(MAX(position), -1) + 1 FROM project_publications WHERE project_id = ?",
            (project_id,),
        ).fetchone()
        return int(row[0])

    @staticmethod
    def _insert_or_replace(
        connection: sqlite3.Connection,
        project_id: str,
        publication: Publication,
        position: int,
    ) -> None:
        document = publication.model_dump(mode="json")
        connection.execute(
            """
            INSERT INTO project_publications (
                project_id, record_id, position, title, title_normalized,
                publication_year, authors, identifiers, provenance, created_at,
                document
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(project_id, record_id) DO UPDATE SET
                position = excluded.position,
                title = excluded.title,
                title_normalized = excluded.title_normalized,
                publication_year = excluded.publication_year,
                authors = excluded.authors,
                identifiers = excluded.identifiers,
                provenance = excluded.provenance,
                created_at = excluded.created_at,
                document = excluded.document
            """,
            (
                project_id,
                str(publication.record_id),
                position,
                publication.title,
                publication.title_normalized,
                publication.publication_year,
                json.dumps(document["authors"], ensure_ascii=False),
                json.dumps(document["identifiers"], ensure_ascii=False),
                json.dumps(document["provenance"], ensure_ascii=False),
                publication.created_at.isoformat(),
                json.dumps(document, ensure_ascii=False),
            ),
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


def default_project_publication_repository() -> SqliteProjectPublicationRepository:
    path = os.environ.get("SLR_DATABASE_PATH", "data/slr-platform.db")
    return SqliteProjectPublicationRepository(path)
