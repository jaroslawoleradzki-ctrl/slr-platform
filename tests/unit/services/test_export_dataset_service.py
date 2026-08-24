"""Unit tests for the read-only export dataset facade (v0.6.1 Slice 1)."""

from pathlib import Path

import pytest

from app.domain.extraction import ExtractionCompletenessStatus
from app.domain.publication import Publication
from app.repositories.project_publication_repository import (
    ProjectNotFoundError,
    SqliteProjectPublicationRepository,
)
from app.services.export_dataset_service import ExportDatasetService
from tests.fixtures.factories import make_publication

KNOWN_PROJECT_ID = "lean_energy"


class FakeExtractionService:
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def get_publication_read_models(self, project_id, reviewer_id="", *, status_filter=None):
        self.calls.append((project_id, reviewer_id, status_filter))
        return ["extraction-model"]


class FakePrismaService:
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def get_metrics(self, project_id, reviewer_id="default_reviewer"):
        self.calls.append((project_id, reviewer_id))
        return "prisma-metrics"


@pytest.fixture
def populated_repo(tmp_path: Path) -> SqliteProjectPublicationRepository:
    repo = SqliteProjectPublicationRepository(tmp_path / "exports.db")
    repo.add_publications(KNOWN_PROJECT_ID, [make_publication(1), make_publication(2), make_publication(3)])
    return repo


def build_service(repo: SqliteProjectPublicationRepository) -> ExportDatasetService:
    return ExportDatasetService(
        publication_repository=repo,
        extraction_service=FakeExtractionService(),
        prisma_service=FakePrismaService(),
    )


class TestBibliographicRecords:
    def test_returns_active_records_in_collection_order(self, populated_repo) -> None:
        service = build_service(populated_repo)

        records = service.get_bibliographic_records(KNOWN_PROJECT_ID)

        assert [record.record_id for record in records] == [
            publication.record_id for publication in populated_repo.get_publications(KNOWN_PROJECT_ID)
        ]

    def test_superseded_duplicates_are_never_returned(self, populated_repo) -> None:
        publications = populated_repo.get_publications(KNOWN_PROJECT_ID)
        canonical, superseded = publications[0], publications[1]
        populated_repo.mark_superseded(KNOWN_PROJECT_ID, [superseded.record_id], canonical.record_id)
        service = build_service(populated_repo)

        records = service.get_bibliographic_records(KNOWN_PROJECT_ID)

        returned_ids = {record.record_id for record in records}
        assert canonical.record_id in returned_ids
        assert superseded.record_id not in returned_ids
        assert len(records) == 2

    def test_unknown_project_raises_project_not_found(self, populated_repo) -> None:
        service = build_service(populated_repo)

        with pytest.raises(ProjectNotFoundError):
            service.get_bibliographic_records("missing_project")

    def test_export_is_read_only(self, populated_repo) -> None:
        service = build_service(populated_repo)
        count_before = populated_repo.count_by_project(KNOWN_PROJECT_ID)
        active_before = populated_repo.count_active_by_project(KNOWN_PROJECT_ID)

        service.get_bibliographic_records(KNOWN_PROJECT_ID)

        assert populated_repo.count_by_project(KNOWN_PROJECT_ID) == count_before
        assert populated_repo.count_active_by_project(KNOWN_PROJECT_ID) == active_before


class TestDelegates:
    def test_extraction_read_models_delegate_passes_arguments_through(self, populated_repo) -> None:
        fake_extraction = FakeExtractionService()
        service = ExportDatasetService(
            publication_repository=populated_repo,
            extraction_service=fake_extraction,
            prisma_service=FakePrismaService(),
        )

        result = service.get_extraction_read_models(
            "proj", "alice", status_filter=ExtractionCompletenessStatus.COMPLETE
        )

        assert result == ["extraction-model"]
        assert fake_extraction.calls == [("proj", "alice", ExtractionCompletenessStatus.COMPLETE)]

    def test_prisma_metrics_delegate_passes_reviewer_through(self, populated_repo) -> None:
        fake_prisma = FakePrismaService()
        service = ExportDatasetService(
            publication_repository=populated_repo,
            extraction_service=FakeExtractionService(),
            prisma_service=fake_prisma,
        )

        result = service.get_prisma_metrics("proj", reviewer_id="bob")

        assert result == "prisma-metrics"
        assert fake_prisma.calls == [("proj", "bob")]


def test_empty_collection_is_valid(tmp_path: Path) -> None:
    """A known project with zero publications exports an empty record list."""
    repo = SqliteProjectPublicationRepository(tmp_path / "empty.db")
    repo.get_publications("ai_architecture")
    service = ExportDatasetService(
        publication_repository=repo,
        extraction_service=FakeExtractionService(),
        prisma_service=FakePrismaService(),
    )
    records: list[Publication] = service.get_bibliographic_records("ai_architecture")
    assert records == []
