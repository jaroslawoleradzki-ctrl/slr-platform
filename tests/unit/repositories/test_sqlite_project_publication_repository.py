from pathlib import Path
from uuid import uuid4

import pytest

from app.domain.provenance import ProvenanceEntry
from app.domain.publication import Publication
from app.repositories.project_publication_repository import (
    ProjectNotFoundError,
    SqliteProjectPublicationRepository,
)


def _publication(title: str, source_id: str) -> Publication:
    return Publication(
        record_id=uuid4(),
        title=title,
        publication_year=2024,
        provenance=[ProvenanceEntry(source="openalex", source_record_id=source_id)],
    )


def test_publications_survive_reopening_repository(tmp_path: Path) -> None:
    database = tmp_path / "working-collection.db"
    repository = SqliteProjectPublicationRepository(database)
    publication = _publication("Persistent record", "W1")

    assert repository.add_publications("ai_architecture", [publication]) == 1
    reopened = SqliteProjectPublicationRepository(database)

    assert reopened.get_publications("ai_architecture") == [publication]


def test_import_and_replace_are_project_scoped(tmp_path: Path) -> None:
    repository = SqliteProjectPublicationRepository(tmp_path / "working-collection.db")
    first = _publication("First", "W1")
    duplicate = first.model_copy(deep=True)
    second = _publication("Second", "W2")

    result = repository.import_source_publications(
        "ai_architecture", [first, duplicate, second]
    )
    assert result.imported_count == 2
    assert result.skipped_count == 1
    assert repository.get_publications("lean_energy") == []

    repository.replace_publications("ai_architecture", [second])
    assert repository.get_publications("ai_architecture") == [second]


def test_unknown_project_is_rejected(tmp_path: Path) -> None:
    repository = SqliteProjectPublicationRepository(tmp_path / "working-collection.db")

    with pytest.raises(ProjectNotFoundError):
        repository.get_publications("missing")
