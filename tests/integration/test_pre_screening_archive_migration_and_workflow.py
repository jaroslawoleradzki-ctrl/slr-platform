import sqlite3
from pathlib import Path
from uuid import uuid4

from app.domain.pre_screening import (
    PreScreeningRemovalReason,
    PreScreeningStatus,
)
from app.domain.project import Project
from app.repositories.pre_screening_archive_repository import (
    SqlitePreScreeningArchiveRepository,
)
from app.repositories.pre_screening_decision_repository import (
    SqlitePreScreeningDecisionRepository,
)
from app.repositories.project_publication_repository import (
    SqliteProjectPublicationRepository,
)
from app.repositories.project_repository import SqliteProjectRepository
from app.services.active_publication_filter import (
    count_active_project_publications,
    get_active_project_publications,
)
from app.services.pre_screening_review_service import PreScreeningReviewService
from tests.fixtures.factories import make_publication


def test_migration_upgrade_on_fresh_db(tmp_path: Path):
    """Verify that all migrations (0001 to 0032) apply cleanly on a fresh database."""
    db_path = tmp_path / "fresh.db"
    _ = SqlitePreScreeningArchiveRepository(db_path)

    with sqlite3.connect(db_path) as conn:
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        assert "pre_screening_archive" in tables
        assert "project_publications" in tables
        assert "pre_screening_decisions" in tables
        assert "schema_migrations" in tables

        applied = {row[0] for row in conn.execute("SELECT version FROM schema_migrations").fetchall()}
        assert "0032_pre_screening_archive.sql" in applied


def test_migration_upgrade_on_existing_db(tmp_path: Path):
    """Verify that migration 0032 applies cleanly on an existing database initialized up to 0031."""
    db_path = tmp_path / "existing.db"
    migration_dir = Path(__file__).parents[2] / "migrations"

    # Initialize up to 0031
    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE schema_migrations (version TEXT PRIMARY KEY, applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)")
        for migration in sorted(migration_dir.glob("*.sql")):
            if migration.name == "0032_pre_screening_archive.sql":
                continue
            conn.executescript(migration.read_text(encoding="utf-8"))
            conn.execute("INSERT INTO schema_migrations(version) VALUES (?)", (migration.name,))

    # Instantiate archive repo, which should trigger application of 0032
    _ = SqlitePreScreeningArchiveRepository(db_path)

    with sqlite3.connect(db_path) as conn:
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        assert "pre_screening_archive" in tables
        applied = {row[0] for row in conn.execute("SELECT version FROM schema_migrations").fetchall()}
        assert "0032_pre_screening_archive.sql" in applied


def test_archive_and_restore_full_lifecycle(tmp_path: Path):
    """Verify end-to-end archive removal, physical deletion, and subsequent restore."""
    db_path = tmp_path / "lifecycle.db"
    proj_repo = SqliteProjectRepository(db_path)
    proj_repo.create(Project(project_id="life_proj", title="Lifecycle Project"))

    pub_repo = SqliteProjectPublicationRepository(db_path)
    decision_repo = SqlitePreScreeningDecisionRepository(db_path)
    archive_repo = SqlitePreScreeningArchiveRepository(db_path)

    service = PreScreeningReviewService(
        publication_repository=pub_repo,
        decision_repository=decision_repo,
        archive_repository=archive_repo,
    )

    project_id = "life_proj"
    import_id = uuid4()

    p1 = make_publication(index=1, title="Retained 1")
    p2 = make_publication(index=2, title="To Be Archived")
    p3 = make_publication(index=3, title="Retained 2")
    pub_repo.import_source_publications(project_id, [p1, p2, p3], import_id=import_id)

    assert count_active_project_publications(project_id, pub_repo) == 3
    assert pub_repo.count_by_project(project_id) == 3

    # 1. Archive and physically delete p2
    archived = service.archive_pre_screening_removal(
        project_id=project_id,
        import_id=import_id,
        record_id=p2.record_id,
        reason=PreScreeningRemovalReason.RETRIEVAL_ARTEFACT,
        notes="Non-paper artefact",
        reviewer_id="lead_rev",
        physical_delete=True,
    )
    assert archived.record_id == p2.record_id

    assert count_active_project_publications(project_id, pub_repo) == 2
    assert pub_repo.count_by_project(project_id) == 2
    assert archive_repo.count_archived_for_project(project_id) == 1

    # Active publications must contain only p1 and p3
    active_ids = {p.record_id for p in get_active_project_publications(project_id, pub_repo)}
    assert active_ids == {p1.record_id, p3.record_id}

    # 2. Restore p2 from archive
    restored = service.restore_record(
        project_id=project_id,
        import_id=import_id,
        record_id=p2.record_id,
        reviewer_id="lead_rev",
    )

    assert restored.record_id == p2.record_id
    assert restored.pre_screening_status == PreScreeningStatus.RETAINED
    assert count_active_project_publications(project_id, pub_repo) == 3
    assert pub_repo.count_by_project(project_id) == 3
    assert archive_repo.count_archived_for_project(project_id) == 0
