from pathlib import Path
from uuid import uuid4

import pytest

from app.domain.identifiers import Identifier, IdentifierType
from app.domain.pre_screening import (
    PreScreeningArchivedRecord,
    PreScreeningRemovalReason,
)
from app.domain.project import Project
from app.repositories.pre_screening_archive_repository import (
    InMemoryPreScreeningArchiveRepository,
    SqlitePreScreeningArchiveRepository,
)
from app.repositories.project_publication_repository import (
    SqliteProjectPublicationRepository,
)
from app.repositories.project_repository import SqliteProjectRepository
from tests.fixtures.factories import make_publication


@pytest.mark.parametrize("repo_type", ["sqlite", "memory"])
def test_pre_screening_archive_crud_and_lookup(tmp_path: Path, repo_type: str):
    db_path = tmp_path / f"archive_test_{repo_type}.db"
    if repo_type == "sqlite":
        proj_repo = SqliteProjectRepository(db_path)
        proj_repo.create(Project(project_id="test_proj", title="Test Project"))
        _ = SqliteProjectPublicationRepository(db_path)
        repo = SqlitePreScreeningArchiveRepository(db_path)
    else:
        repo = InMemoryPreScreeningArchiveRepository()

    project_id = "test_proj"
    import_id = uuid4()
    pub = make_publication(
        index=1,
        title="Sample Retrieval Artefact",
        doi="10.1000/182",
        source="crossref",
    )

    archived = PreScreeningArchivedRecord.from_publication(
        publication=pub,
        project_id=project_id,
        import_id=import_id,
        removal_reason=PreScreeningRemovalReason.RETRIEVAL_ARTEFACT,
        removal_notes="Conference announcement",
        removed_by="reviewer_test",
    )

    # 1. Archive record
    saved = repo.archive_record(archived)
    assert saved.archive_id == archived.archive_id
    assert saved.record_id == pub.record_id

    # 2. Get by record_id
    fetched = repo.get_archived_record(project_id, pub.record_id)
    assert fetched is not None
    assert fetched.record_id == pub.record_id
    assert fetched.title == "Sample Retrieval Artefact"
    assert fetched.removal_reason == PreScreeningRemovalReason.RETRIEVAL_ARTEFACT
    assert fetched.removal_notes == "Conference announcement"
    assert fetched.removed_by == "reviewer_test"
    assert fetched.identifiers == [Identifier(type=IdentifierType.DOI, value="10.1000/182")]

    # 3. List and count
    count = repo.count_archived_for_project(project_id, import_id=import_id)
    assert count == 1
    items = repo.list_archived_for_project(project_id, import_id=import_id)
    assert len(items) == 1
    assert items[0].record_id == pub.record_id

    # 4. Search
    search_match = repo.list_archived_for_project(project_id, search="Artefact")
    assert len(search_match) == 1
    search_miss = repo.list_archived_for_project(project_id, search="Nonexistent")
    assert len(search_miss) == 0

    # 5. Delete from archive (upon restore)
    deleted = repo.delete_archived_record(project_id, pub.record_id)
    assert deleted is True
    assert repo.get_archived_record(project_id, pub.record_id) is None
    assert repo.count_archived_for_project(project_id) == 0
