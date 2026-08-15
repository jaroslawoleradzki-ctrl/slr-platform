import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient

from app.api.main import app
from app.api.routers.normalization import get_normalization_execution_repository
from app.api.routers.search_strategy import get_project_publication_repository
from app.repositories.normalization_execution_repository import SqliteNormalizationExecutionRepository
from app.repositories.project_publication_repository import DemoProjectPublicationRepository


def _client(repository: DemoProjectPublicationRepository, database: Path) -> TestClient:
    app.dependency_overrides[get_project_publication_repository] = lambda: repository
    app.dependency_overrides[get_normalization_execution_repository] = lambda: SqliteNormalizationExecutionRepository(database)
    return TestClient(app)


def setup_function() -> None:
    app.dependency_overrides.clear()


def teardown_function() -> None:
    app.dependency_overrides.clear()


def test_normalization_is_project_scoped_and_returns_real_summary(tmp_path: Path) -> None:
    repository = DemoProjectPublicationRepository()
    client = _client(repository, tmp_path / "normalization.db")

    response = client.post("/api/v1/projects/lean_energy/normalization")

    assert response.status_code == 200
    body = response.json()
    assert body["project_id"] == "lean_energy"
    assert body["status"] == "completed"
    assert body["processed_records"] == 5
    assert body["clean_records"] == 5
    assert body["warnings_count"] == 0
    assert "title canonicalized" in body["rules_applied"]
    assert any("DOI normalized" in entry for entry in body["audit_trail"])
    assert client.get("/api/v1/projects/lean_energy/normalization").json() == body
    assert client.get("/api/v1/projects/ai_architecture/normalization").status_code == 404


def test_empty_project_is_a_real_zero_record_normalization(tmp_path: Path) -> None:
    repository = DemoProjectPublicationRepository()
    client = _client(repository, tmp_path / "normalization.db")

    response = client.post("/api/v1/projects/ai_architecture/normalization")

    assert response.status_code == 200
    assert response.json()["processed_records"] == 0
    assert response.json()["audit_trail"] == []


def test_unknown_project_and_repeat_are_safe(tmp_path: Path) -> None:
    repository = DemoProjectPublicationRepository()
    client = _client(repository, tmp_path / "normalization.db")

    assert client.post("/api/v1/projects/missing/normalization").status_code == 404
    first = client.post("/api/v1/projects/lean_energy/normalization").json()
    second = client.post("/api/v1/projects/lean_energy/normalization").json()
    assert second["processed_records"] == first["processed_records"]
    assert second["status"] == "completed"


def test_saved_result_survives_reopening_sqlite_repository(tmp_path: Path) -> None:
    database = tmp_path / "normalization.db"
    repository = DemoProjectPublicationRepository()
    client = _client(repository, database)
    created = client.post("/api/v1/projects/lean_energy/normalization").json()

    reopened = SqliteNormalizationExecutionRepository(database)
    saved = reopened.get_for_project("lean_energy")
    assert saved is not None
    assert str(saved.run_id) == created["run_id"]
    assert saved.audit_trail == tuple(created["audit_trail"])

    app.dependency_overrides.clear()
    restarted_client = _client(repository, database)
    assert restarted_client.get("/api/v1/projects/lean_energy/normalization").json() == created


def test_second_run_replaces_latest_project_result(tmp_path: Path) -> None:
    database = tmp_path / "normalization.db"
    client = _client(DemoProjectPublicationRepository(), database)
    first = client.post("/api/v1/projects/lean_energy/normalization").json()
    second = client.post("/api/v1/projects/lean_energy/normalization").json()

    assert second["run_id"] != first["run_id"]
    assert client.get("/api/v1/projects/lean_energy/normalization").json() == second
    with SqliteNormalizationExecutionRepository(database)._connect() as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM normalization_executions WHERE project_id = ?",
            ("lean_energy",),
        ).fetchone()[0] == 1


def test_new_migration_applies_after_existing_migrations(tmp_path: Path) -> None:
    database = tmp_path / "legacy.db"
    with sqlite3.connect(database) as connection:
        connection.execute(
            "CREATE TABLE schema_migrations (version TEXT PRIMARY KEY, applied_at TEXT)"
        )
        migration_directory = Path(__file__).parents[3] / "migrations"
        for name in (
            "0001_search_strategies.sql",
            "0002_import_history.sql",
            "0003_import_history_sources.sql",
        ):
            connection.executescript((migration_directory / name).read_text())
            connection.execute("INSERT INTO schema_migrations(version) VALUES (?)", (name,))

    repository = SqliteNormalizationExecutionRepository(database)
    assert repository.get_for_project("lean_energy") is None
    with sqlite3.connect(database) as connection:
        assert connection.execute(
            "SELECT 1 FROM schema_migrations WHERE version = '0004_normalization_execution.sql'"
        ).fetchone() == (1,)
