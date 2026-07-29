import pytest

from app.domain.publication import Publication
from app.repositories.project_publication_repository import (
    DemoProjectPublicationRepository,
    ProjectNotFoundError,
)


def test_demo_repository_returns_publications_for_lean_energy() -> None:
    repo = DemoProjectPublicationRepository()
    pubs = repo.get_publications("lean_energy")

    assert len(pubs) == 5
    assert all(isinstance(p, Publication) for p in pubs)
    assert pubs[0].title.startswith("Energy reduction")


def test_demo_repository_returns_empty_list_for_ai_architecture() -> None:
    repo = DemoProjectPublicationRepository()
    pubs = repo.get_publications("ai_architecture")

    assert pubs == []


def test_demo_repository_raises_project_not_found_for_unknown_id() -> None:
    repo = DemoProjectPublicationRepository()

    with pytest.raises(ProjectNotFoundError) as exc_info:
        repo.get_publications("non_existent_project")

    assert exc_info.value.project_id == "non_existent_project"
    assert "not found" in str(exc_info.value).lower()
