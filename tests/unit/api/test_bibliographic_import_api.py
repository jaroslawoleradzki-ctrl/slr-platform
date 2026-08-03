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


def test_selected_provider_imports_create_durable_history_records(
    tmp_path: Path,
) -> None:
    database = tmp_path / "provider.db"
    repository = DemoProjectPublicationRepository()
    client = _client(repository, database)

    openalex_rec1 = {
        "id": "00000000-0000-0000-0000-000000000901",
        "title": "OpenAlex record 1",
        "authors": ["Ada Author"],
        "year": 2024,
        "provider": "openalex",
        "source_id": "https://openalex.org/W901",
        "doi": None,
    }
    openalex_payload1 = {
        "records": [openalex_rec1],
        "provider": "openalex",
        "query": '("lean manufacturing")',
        "total_available": 3560,
    }

    openalex_rec2 = {
        "id": "00000000-0000-0000-0000-000000000902",
        "title": "OpenAlex record 2",
        "authors": ["Bob Builder"],
        "year": 2024,
        "provider": "openalex",
        "source_id": "https://openalex.org/W902",
        "doi": None,
    }
    openalex_payload2 = {
        "records": [openalex_rec2],
        "provider": "openalex",
        "query": '("lean manufacturing")',
        "total_available": 3560,
    }

    # 1. Pierwszy import (1 rekord)
    res1 = client.post("/projects/ai_architecture/search-results/imports", json=openalex_payload1)
    assert res1.status_code == 200
    assert res1.json()["imported_count"] == 1

    h1 = client.get("/projects/ai_architecture/imports").json()
    assert len(h1) == 1
    assert h1[0]["records_count"] == 1
    assert h1[0]["provider"] == "openalex"

    # 2. Drugi import (kolejny 1 rekord)
    res2 = client.post("/projects/ai_architecture/search-results/imports", json=openalex_payload2)
    assert res2.status_code == 200
    assert res2.json()["imported_count"] == 1

    h2 = client.get("/projects/ai_architecture/imports").json()
    assert len(h2) == 2
    assert h2[0]["records_count"] == 1  # najnowszy
    assert h2[1]["records_count"] == 1  # poprzedni

    # 3. Trzeci import – częściowo idempotentny (rekord 1 + powtórzony rekord 2)
    res3 = client.post("/projects/ai_architecture/search-results/imports", json=openalex_payload2)
    assert res3.status_code == 200
    assert res3.json()["imported_count"] == 0  # pominięty przez idempotencję
    assert res3.json()["skipped_count"] == 1

    h3 = client.get("/projects/ai_architecture/imports").json()
    assert len(h3) == 3
    assert h3[0]["records_count"] == 0  # historia odzwierciedla nowo dodane rekordy (0)

    # 4. Potwierdzenie trwałości po ponownym otwarciu SQLite
    reopened = SqliteImportHistoryRepository(database).list_for_project("ai_architecture")
    assert len(reopened) == 3
    assert [r.records_count for r in reopened] == [0, 1, 1]


def test_multi_provider_mixed_import_creates_separate_history_entries(
    tmp_path: Path,
) -> None:
    database = tmp_path / "mixed.db"
    repository = DemoProjectPublicationRepository()
    client = _client(repository, database)

    # Przygotowanie 2 rekordów OpenAlex oraz 2 rekordów Crossref
    oa_existing = {
        "id": "00000000-0000-0000-0000-000000000911",
        "title": "Existing OpenAlex Record",
        "authors": ["Ada"],
        "year": 2024,
        "provider": "openalex",
        "source_id": "W911",
        "doi": "10.1000/oa911",
    }
    oa_new = {
        "id": "00000000-0000-0000-0000-000000000912",
        "title": "New OpenAlex Record",
        "authors": ["Alice"],
        "year": 2024,
        "provider": "openalex",
        "source_id": "W912",
        "doi": "10.1000/oa912",
    }

    cr_existing = {
        "id": "00000000-0000-0000-0000-000000000921",
        "title": "Existing Crossref Record",
        "authors": ["Charles"],
        "year": 2025,
        "provider": "crossref",
        "source_id": "10.1000/cr921",
        "doi": "10.1000/cr921",
    }
    cr_new = {
        "id": "00000000-0000-0000-0000-000000000922",
        "title": "New Crossref Record",
        "authors": ["Clara"],
        "year": 2025,
        "provider": "crossref",
        "source_id": "10.1000/cr922",
        "doi": "10.1000/cr922",
    }

    # Wcześniej importujemy 1 z OpenAlex i 1 z Crossref (tak by 2 rekordy już istniały)
    client.post(
        "/projects/ai_architecture/search-results/imports",
        json={"records": [oa_existing], "provider": "openalex", "query": "init"},
    )
    client.post(
        "/projects/ai_architecture/search-results/imports",
        json={"records": [cr_existing], "provider": "crossref", "query": "init"},
    )

    # Wykonujemy mieszany import łączny (2 OpenAlex + 2 Crossref)
    mixed_payload = {
        "records": [oa_existing, oa_new, cr_existing, cr_new],
        "query": "mixed search run",
        "total_available": 400,
    }

    response = client.post("/projects/ai_architecture/search-results/imports", json=mixed_payload)

    assert response.status_code == 200
    res_data = response.json()
    assert res_data["imported_count"] == 2
    assert res_data["skipped_count"] == 2
    assert res_data["total_requested"] == 4
    assert res_data["working_collection_count"] == 4

    # Weryfikacja wpisów w historii przez GET /projects/{id}/imports
    history = client.get("/projects/ai_architecture/imports").json()
    # Wynik ma 4 wpisy w historii (2 z inicjalizacji + 2 z grupy mixed importu)
    latest_entries = history[:2]
    history_by_provider = {item["provider"]: item for item in latest_entries}

    assert "openalex" in history_by_provider
    assert "crossref" in history_by_provider
    assert history_by_provider["openalex"]["records_count"] == 1
    assert history_by_provider["crossref"]["records_count"] == 1

    # Weryfikacja trwałości po utworzeniu repozytorium na tej samej bazie SQLite
    reopened = SqliteImportHistoryRepository(database).list_for_project("ai_architecture")
    assert len(reopened) == 4
