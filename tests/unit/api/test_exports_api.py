"""API tests for research export endpoints (v0.6.1 Slice 1: BibTeX + RIS)."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.main import app
from app.api.routers.exports import get_export_dataset_service
from app.domain.project import Project
from app.providers.import_file.bibtex.parser import parse_bibtex
from app.providers.import_file.ris.parser import parse_ris
from app.repositories.project_publication_repository import (
    SqliteProjectPublicationRepository,
)
from app.repositories.project_repository import SqliteProjectRepository
from app.services.export_dataset_service import ExportDatasetService
from tests.fixtures.factories import make_publication

PROJECT_ID = "exports_project"


@pytest.fixture
def environment(tmp_path: Path):
    database = tmp_path / "exports.db"
    project_repo = SqliteProjectRepository(database)
    publications = SqliteProjectPublicationRepository(database)
    project_repo.create(Project(project_id=PROJECT_ID, title="Exports Project"))

    service = ExportDatasetService(publication_repository=publications)
    app.dependency_overrides[get_export_dataset_service] = lambda: service
    yield TestClient(app), publications
    app.dependency_overrides.clear()


class TestBibtexEndpoint:
    def test_returns_attachment_with_bibtex_media_type(self, environment) -> None:
        client, publications = environment
        publications.add_publications(PROJECT_ID, [make_publication(1)])

        response = client.get(f"/api/v1/projects/{PROJECT_ID}/exports/bibtex")

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("application/x-bibtex")
        assert response.headers["content-disposition"] == 'attachment; filename="exports_project_publications.bib"'
        assert "@misc{" in response.text or "@article{" in response.text

    def test_unknown_project_returns_404(self, environment) -> None:
        client, _ = environment
        response = client.get("/api/v1/projects/missing/exports/bibtex")
        assert response.status_code == 404

    def test_empty_project_yields_valid_empty_artifact(self, environment) -> None:
        client, _ = environment
        response = client.get(f"/api/v1/projects/{PROJECT_ID}/exports/bibtex")
        assert response.status_code == 200
        assert response.text == ""
        assert response.headers["content-disposition"] == 'attachment; filename="exports_project_publications.bib"'

    def test_superseded_records_are_never_exported(self, environment) -> None:
        client, publications = environment
        canonical = make_publication(1)
        superseded = make_publication(2)
        publications.add_publications(PROJECT_ID, [canonical, superseded])
        publications.mark_superseded(PROJECT_ID, [superseded.record_id], canonical.record_id)

        response = client.get(f"/api/v1/projects/{PROJECT_ID}/exports/bibtex")

        assert response.status_code == 200
        entries = parse_bibtex(response.text)
        titles = {entry["fields"].get("title") for entry in entries}
        assert titles == {canonical.title}

    def test_two_calls_are_byte_identical(self, environment) -> None:
        client, publications = environment
        publications.add_publications(
            PROJECT_ID,
            [make_publication(1, doi="10.1000/a"), make_publication(2, doi="10.1000/b")],
        )

        first = client.get(f"/api/v1/projects/{PROJECT_ID}/exports/bibtex").content
        second = client.get(f"/api/v1/projects/{PROJECT_ID}/exports/bibtex").content

        assert first == second

    def test_export_does_not_mutate_project_state(self, environment) -> None:
        client, publications = environment
        publications.add_publications(PROJECT_ID, [make_publication(1), make_publication(2)])
        total_before = publications.count_by_project(PROJECT_ID)
        active_before = publications.count_active_by_project(PROJECT_ID)

        client.get(f"/api/v1/projects/{PROJECT_ID}/exports/bibtex")

        assert publications.count_by_project(PROJECT_ID) == total_before
        assert publications.count_active_by_project(PROJECT_ID) == active_before


class TestRisEndpoint:
    def test_returns_attachment_with_ris_media_type(self, environment) -> None:
        client, publications = environment
        publications.add_publications(PROJECT_ID, [make_publication(1)])

        response = client.get(f"/api/v1/projects/{PROJECT_ID}/exports/ris")

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("application/x-research-info-systems")
        assert response.headers["content-disposition"] == 'attachment; filename="exports_project_publications.ris"'
        assert "TY  - " in response.text

    def test_unknown_project_returns_404(self, environment) -> None:
        client, _ = environment
        response = client.get("/api/v1/projects/missing/exports/ris")
        assert response.status_code == 404

    def test_empty_project_yields_valid_empty_artifact(self, environment) -> None:
        client, _ = environment
        response = client.get(f"/api/v1/projects/{PROJECT_ID}/exports/ris")
        assert response.status_code == 200
        assert response.text == ""

    def test_superseded_records_are_never_exported(self, environment) -> None:
        client, publications = environment
        canonical = make_publication(1)
        superseded = make_publication(2)
        publications.add_publications(PROJECT_ID, [canonical, superseded])
        publications.mark_superseded(PROJECT_ID, [superseded.record_id], canonical.record_id)

        response = client.get(f"/api/v1/projects/{PROJECT_ID}/exports/ris")

        records = parse_ris(response.text)
        titles = {record["TI"][0] for record in records}
        assert titles == {canonical.title}

    def test_two_calls_are_byte_identical(self, environment) -> None:
        client, publications = environment
        publications.add_publications(PROJECT_ID, [make_publication(1), make_publication(2)])

        first = client.get(f"/api/v1/projects/{PROJECT_ID}/exports/ris").content
        second = client.get(f"/api/v1/projects/{PROJECT_ID}/exports/ris").content

        assert first == second

    def test_unicode_titles_survive_the_http_boundary(self, environment) -> None:
        client, publications = environment
        unicode_title = "Wpływ zarządzania lean na efektywność energetyczną"
        publications.add_publications(PROJECT_ID, [make_publication(1, title=unicode_title)])

        response = client.get(f"/api/v1/projects/{PROJECT_ID}/exports/ris")

        records = parse_ris(response.text)
        assert records[0]["TI"][0] == unicode_title


class TestRoundTripThroughImporterParsers:
    def test_bibtex_export_reimports_with_counts_and_metadata(self, environment) -> None:
        client, publications = environment
        publications.add_publications(
            PROJECT_ID,
            [
                make_publication(1, doi="10.1000/alpha", year=2024),
                make_publication(2, doi="10.1000/beta", year=2023),
                make_publication(3),
            ],
        )

        body = client.get(f"/api/v1/projects/{PROJECT_ID}/exports/bibtex").text
        parsed = parse_bibtex(body)

        assert len(parsed) == 3
        dois = {entry["fields"].get("doi") for entry in parsed}
        assert {"10.1000/alpha", "10.1000/beta"} <= dois

    def test_ris_export_reimports_with_counts_and_metadata(self, environment) -> None:
        client, publications = environment
        publications.add_publications(
            PROJECT_ID,
            [
                make_publication(1, doi="10.1000/alpha", year=2024),
                make_publication(2, doi="10.1000/beta", year=2023),
            ],
        )

        body = client.get(f"/api/v1/projects/{PROJECT_ID}/exports/ris").text
        parsed = parse_ris(body)

        assert len(parsed) == 2
        assert body.count("ER  - \r\n") == 2
        years = sorted(record["PY"][0] for record in parsed)
        assert years == ["2023", "2024"]
