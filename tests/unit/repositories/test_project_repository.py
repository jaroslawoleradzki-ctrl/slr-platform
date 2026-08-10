import pytest

from app.domain.project import Project, ProjectStatus
from app.repositories.project_repository import (
    ProjectAlreadyExistsError,
    ProjectNotFoundError,
    SqliteProjectRepository,
)


@pytest.fixture
def repo(tmp_path) -> SqliteProjectRepository:
    db_path = tmp_path / "test_projects.db"
    return SqliteProjectRepository(db_path)


def test_create_and_get_project(repo: SqliteProjectRepository) -> None:
    p = Project(project_id="p-1", title="Test Project 1", description="Description 1")
    repo.create(p)

    fetched = repo.get("p-1")
    assert fetched.project_id == "p-1"
    assert fetched.title == "Test Project 1"
    assert fetched.description == "Description 1"
    assert fetched.status is ProjectStatus.ACTIVE


def test_create_duplicate_id_raises_error(repo: SqliteProjectRepository) -> None:
    p1 = Project(project_id="p-1", title="Test Project 1")
    repo.create(p1)

    p2 = Project(project_id="p-1", title="Duplicate ID Project")
    with pytest.raises(ProjectAlreadyExistsError):
        repo.create(p2)


def test_get_nonexistent_project_raises_error(repo: SqliteProjectRepository) -> None:
    with pytest.raises(ProjectNotFoundError):
        repo.get("unknown_project")


def test_list_all_and_include_archived(repo: SqliteProjectRepository) -> None:
    p1 = Project(project_id="p-1", title="Active Project 1")
    p2 = Project(project_id="p-2", title="Active Project 2")
    repo.create(p1)
    repo.create(p2)

    active_list = repo.list_all()
    assert len(active_list) == 2

    # Archive p-1
    repo.archive("p-1")

    # List active only
    active_only = repo.list_all(include_archived=False)
    assert len(active_only) == 1
    assert active_only[0].project_id == "p-2"

    # List including archived
    all_projects = repo.list_all(include_archived=True)
    assert len(all_projects) == 2


def test_update_project_preserves_id(repo: SqliteProjectRepository) -> None:
    p = Project(
        project_id="stable-id-123",
        title="Initial Title",
        description="Initial Desc",
        protocol_version="1.0",
    )
    repo.create(p)

    updated = repo.update(
        "stable-id-123",
        title="Updated Title",
        description="Updated Desc",
        protocol_version="2.0",
    )

    assert updated.project_id == "stable-id-123"  # ID preserved!
    assert updated.title == "Updated Title"
    assert updated.description == "Updated Desc"
    assert updated.protocol_version == "2.0"


def test_archive_and_restore_preserve_id(repo: SqliteProjectRepository) -> None:
    p = Project(project_id="stable-id-456", title="Title")
    repo.create(p)

    archived = repo.archive("stable-id-456")
    assert archived.project_id == "stable-id-456"
    assert archived.status is ProjectStatus.ARCHIVED

    restored = repo.restore("stable-id-456")
    assert restored.project_id == "stable-id-456"
    assert restored.status is ProjectStatus.ACTIVE
