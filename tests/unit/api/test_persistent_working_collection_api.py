from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

from app.api.main import app
from app.api.routers.normalization import get_normalization_execution_repository
from app.api.routers.search_strategy import (
    get_import_history_repository,
    get_project_publication_repository,
)
from app.domain.provenance import ProvenanceEntry
from app.domain.publication import Publication
from app.repositories.import_history_repository import SqliteImportHistoryRepository
from app.repositories.normalization_execution_repository import (
    SqliteNormalizationExecutionRepository,
)
from app.repositories.project_publication_repository import (
    SqliteProjectPublicationRepository,
)
from app.repositories.search_result_snapshot_repository import (
    SearchResultSnapshot,
    SqliteSearchResultSnapshotRepository,
)


def setup_function() -> None:
    app.dependency_overrides.clear()


def teardown_function() -> None:
    app.dependency_overrides.clear()


def _client(database: Path) -> TestClient:
    app.dependency_overrides[get_project_publication_repository] = lambda: SqliteProjectPublicationRepository(database)
    app.dependency_overrides[get_import_history_repository] = lambda: SqliteImportHistoryRepository(database)
    app.dependency_overrides[get_normalization_execution_repository] = lambda: SqliteNormalizationExecutionRepository(
        database
    )
    return TestClient(app)


def test_file_import_and_normalization_use_same_durable_collection(tmp_path: Path) -> None:
    database = tmp_path / "project.db"
    client = _client(database)

    imported = client.post(
        "/projects/ai_architecture/imports",
        files={
            "file": (
                "record.ris",
                "TY  - JOUR\nTI  - Imported record\nPY  - 2024\nER  - \n",
                "text/plain",
            )
        },
    )
    assert imported.status_code == 201

    normalized = client.post("/projects/ai_architecture/normalization")
    assert normalized.status_code == 200
    assert normalized.json()["processed_records"] == 1

    reopened = SqliteProjectPublicationRepository(database)
    assert len(reopened.get_publications("ai_architecture")) == 1
    assert client.get("/projects/lean_energy/normalization").status_code == 404


def test_selected_openalex_import_is_written_to_working_collection(tmp_path: Path) -> None:
    database = tmp_path / "project.db"
    client = _client(database)
    run_id = uuid4()
    snapshot = SqliteSearchResultSnapshotRepository(database).save(
        SearchResultSnapshot.create(
            project_id="ai_architecture",
            search_run_id=run_id,
            provider="openalex",
            source_id="W901",
            publication=Publication(
                title="OpenAlex imported record",
                publication_year=2024,
                provenance=[ProvenanceEntry(source="openalex", source_record_id="W901", run_id=run_id)],
            ),
        )
    )
    payload = {
        "provider": "openalex",
        "query": '"lean manufacturing"',
        "total_available": 100,
        "records": [
            {
                "id": str(snapshot.snapshot_id),
                "title": "OpenAlex imported record",
                "authors": ["Author"],
                "year": 2024,
                "provider": "openalex",
                "source_id": "W901",
                "doi": None,
            }
        ],
    }

    imported = client.post("/projects/ai_architecture/search-results/imports", json=payload)
    assert imported.status_code == 200
    assert imported.json()["imported_count"] == 1
    normalized = client.post("/projects/ai_architecture/normalization")
    assert normalized.json()["processed_records"] == 1

    reopened = SqliteProjectPublicationRepository(database)
    assert reopened.get_publications("ai_architecture")[0].title == "OpenAlex imported record"


def test_new_import_invalidates_previous_normalization_result(tmp_path: Path) -> None:
    database = tmp_path / "project.db"
    client = _client(database)
    first = client.post(
        "/projects/ai_architecture/imports",
        files={"file": ("one.ris", "TY  - JOUR\nTI  - One\nER  - \n", "text/plain")},
    )
    assert first.status_code == 201
    assert client.post("/projects/ai_architecture/normalization").status_code == 200

    second = client.post(
        "/projects/ai_architecture/imports",
        files={"file": ("two.ris", "TY  - JOUR\nTI  - Two\nER  - \n", "text/plain")},
    )
    assert second.status_code == 201
    assert client.get("/projects/ai_architecture/normalization").status_code == 404


def test_one_hundred_records_survive_normalization_and_repository_restart(tmp_path: Path) -> None:
    database = tmp_path / "project.db"
    repository = SqliteProjectPublicationRepository(database)
    from app.domain.provenance import ProvenanceEntry
    from app.domain.publication import Publication

    records = [
        Publication(
            title=f"Record {index}",
            publication_year=2024,
            provenance=[ProvenanceEntry(source="openalex", source_record_id=f"W{index}")],
        )
        for index in range(100)
    ]
    result = repository.import_source_publications("ai_architecture", records)
    assert result.working_collection_count == 100

    client = _client(database)
    normalized = client.post("/projects/ai_architecture/normalization")
    assert normalized.json()["processed_records"] == 100

    reopened = SqliteProjectPublicationRepository(database)
    assert len(reopened.get_publications("ai_architecture")) == 100
    assert client.get("/projects/ai_architecture/normalization").json()["processed_records"] == 100
