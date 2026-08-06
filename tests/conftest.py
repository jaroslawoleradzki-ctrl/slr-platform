from pathlib import Path

import pytest

from app.api.main import app
from app.api.routers.deduplication import get_duplicate_service
from app.repositories.duplicate_review_decision_repository import (
    in_memory_duplicate_review_decision_repository,
)
from app.repositories.project_publication_repository import (
    demo_project_publication_repository,
)
from app.services.project_duplicate_service import ProjectDuplicateService

# Expose standard project fixtures for test suite
from tests.fixtures.project_fixtures import (
    empty_project,
    project_100,
    project_duplicates,
    project_normalized,
)

__all__ = [
    "empty_project",
    "project_100",
    "project_duplicates",
    "project_normalized",
]


@pytest.fixture(autouse=True)
def isolate_test_database(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Isolate SQLite database path for pytest runs to prevent polluting data/slr-platform.db."""
    db_file = tmp_path / "test_slr.db"
    monkeypatch.setenv("SLR_DATABASE_PATH", str(db_file))


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
