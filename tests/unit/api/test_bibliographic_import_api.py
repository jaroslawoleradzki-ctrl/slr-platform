from pathlib import Path

from fastapi.testclient import TestClient

from app.api.main import app
from app.api.routers.search_strategy import (
    get_import_history_repository,
    get_project_publication_repository,
)
from app.repositories.project_publication_repository import DemoProjectPublicationRepository
from app.repositories.import_history_repository import SqliteImportHistoryRepository


def _client(
    repository: DemoProjectPublicationRepository,
    history_path: Path,
) -> TestClient:
    app.dependency_overrides[get_project_publication_repository] = lambda: repository
    app.dependency_overrides[get_import_history_repository] = lambda: SqliteImportHistoryRepository(history_path)
    return TestClient(app)


def setup_function() -> None:
    app.dependency_overrides.clear()


def teardown_function() -> None:
    app.dependency_overrides.clear()


def test_uploads_ris_and_persists_publications(tmp_path: Path) -> None:
    repository = DemoProjectPublicationRepository()
    response = _client(repository, tmp_path / "ris.db").post(
        "/projects/ai_architecture/imports",
        files={
            "file": (
                "records.ris",
                "TY  - JOUR\nTI  - RIS record\nPY  - 2024\nER  - \n",
                "application/x-research-info-systems",
            )
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["records_count"] == 1
    assert body["warnings"] == []
    assert body["status"] == "success"
    assert len(repository.get_publications("ai_architecture")) == 1


def test_uploads_bibtex_and_persists_publications(tmp_path: Path) -> None:
    repository = DemoProjectPublicationRepository()
    response = _client(repository, tmp_path / "bib.db").post(
        "/projects/ai_architecture/imports",
        files={
            "file": (
                "records.bib",
                "@article{one, title={BibTeX record}, year={2023}}",
                "application/x-bibtex",
            )
        },
    )

    assert response.status_code == 201
    assert response.json()["records_count"] == 1
    assert repository.get_publications("ai_architecture")[0].title == "BibTeX record"


def test_rejects_unsupported_extension_empty_file_and_invalid_content(tmp_path: Path) -> None:
    repository = DemoProjectPublicationRepository()
    client = _client(repository, tmp_path / "invalid.db")

    unsupported = client.post(
        "/projects/ai_architecture/imports",
        files={"file": ("records.txt", "content", "text/plain")},
    )
    empty = client.post(
        "/projects/ai_architecture/imports",
        files={"file": ("empty.ris", "   ", "text/plain")},
    )
    invalid = client.post(
        "/projects/ai_architecture/imports",
        files={"file": ("invalid.bib", "@article{x, year={2024}}", "text/plain")},
    )

    assert unsupported.status_code == 415
    assert "Unsupported file extension" in unsupported.json()["detail"]
    assert empty.status_code == 422
    assert "empty" in empty.json()["detail"]
    assert invalid.status_code == 422
    assert "missing a title" in invalid.json()["detail"]
    assert repository.get_publications("ai_architecture") == []


def test_missing_file_and_project_scope_are_validated(tmp_path: Path) -> None:
    repository = DemoProjectPublicationRepository()
    client = _client(repository, tmp_path / "scope.db")

    missing = client.post("/projects/ai_architecture/imports")
    unknown_project = client.post(
        "/projects/missing/imports",
        files={"file": ("records.ris", "TY  - JOUR\nTI  - x\nER  - \n", "text/plain")},
    )

    assert missing.status_code == 422
    assert "required" in missing.json()["detail"]
    assert unknown_project.status_code == 404


def test_history_is_project_scoped_sorted_and_persistent(tmp_path: Path) -> None:
    database = tmp_path / "history.db"
    repository = DemoProjectPublicationRepository()
    client = _client(repository, database)
    for filename in ("first.ris", "second.bib"):
        content = (
            "TY  - JOUR\nTI  - First\nER  - \n"
            if filename.endswith(".ris")
            else "@article{second, title={Second}}"
        )
        assert client.post(
            "/projects/ai_architecture/imports",
            files={"file": (filename, content, "text/plain")},
        ).status_code == 201

    history = client.get("/projects/ai_architecture/imports")
    other_project = client.get("/projects/lean_energy/imports")
    persisted = SqliteImportHistoryRepository(database).list_for_project(
        "ai_architecture"
    )

    assert history.status_code == 200
    assert [item["filename"] for item in history.json()] == ["second.bib", "first.ris"]
    assert other_project.json() == []
    assert [item.filename for item in persisted] == ["second.bib", "first.ris"]
