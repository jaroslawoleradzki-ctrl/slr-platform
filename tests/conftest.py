import pytest
from app.api.main import app
from app.api.routers.deduplication import get_duplicate_service
from app.repositories.duplicate_review_decision_repository import (
    in_memory_duplicate_review_decision_repository,
)
from app.repositories.project_publication_repository import demo_project_publication_repository
from app.services.project_duplicate_service import ProjectDuplicateService


@pytest.fixture(autouse=True)
def reset_in_memory_decision_repository() -> None:
    """Automatically clear in-memory decision repository state before each test."""
    in_memory_duplicate_review_decision_repository.clear()


@pytest.fixture(autouse=True)
def isolate_legacy_duplicate_fixture() -> None:
    """Keep legacy duplicate contract tests independent of the live collection."""
    app.dependency_overrides[get_duplicate_service] = lambda: ProjectDuplicateService(
        repository=demo_project_publication_repository
    )
    yield
    app.dependency_overrides.pop(get_duplicate_service, None)
