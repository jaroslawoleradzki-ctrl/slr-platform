from pathlib import Path

from app.repositories.import_history_repository import SqliteImportHistoryRepository
from app.repositories.normalization_execution_repository import (
    SqliteNormalizationExecutionRepository,
)
from app.repositories.project_publication_repository import (
    SqliteProjectPublicationRepository,
)
from app.services.duplicate_group_builder import DuplicateGroupBuilder
from tests.fixtures.factories import (
    make_duplicate_decision,
    make_import_history,
    make_normalization_execution,
    make_publication,
)


def test_factories_produce_valid_deterministic_objects() -> None:
    pub = make_publication(index=1, doi="10.1000/1", title="Title 1")
    assert pub.title == "Title 1"
    assert pub.identifiers[0].value == "10.1000/1"
    assert pub.authors[0].display_name == "Author 1"

    history = make_import_history(project_id="p1", records_count=5)
    assert history.project_id == "p1"
    assert history.records_count == 5

    norm = make_normalization_execution(project_id="p1", clean_records=10)
    assert norm.project_id == "p1"
    assert norm.clean_records == 10

    dec = make_duplicate_decision(project_id="p1", group_id="g1")
    assert dec.decision.value == "APPROVE"


def test_empty_project_fixture(empty_project: str, tmp_path: Path) -> None:
    assert empty_project == "ai_architecture"
    db_file = tmp_path / "empty_project.db"
    repo = SqliteProjectPublicationRepository(db_file)
    assert repo.count_by_project(empty_project) == 0


def test_project_100_fixture(project_100: str, tmp_path: Path) -> None:
    assert project_100 == "lean_energy"
    db_file = tmp_path / "project_100.db"
    pub_repo = SqliteProjectPublicationRepository(db_file)
    history_repo = SqliteImportHistoryRepository(db_file)

    assert pub_repo.count_by_project(project_100) == 100
    history = history_repo.list_for_project(project_100)
    assert len(history) == 1
    assert history[0].records_count == 100


def test_project_duplicates_fixture(project_duplicates: str, tmp_path: Path) -> None:
    assert project_duplicates == "lean_energy"
    db_file = tmp_path / "project_duplicates.db"
    pub_repo = SqliteProjectPublicationRepository(db_file)

    pubs = pub_repo.get_publications(project_duplicates)
    assert len(pubs) == 5

    builder = DuplicateGroupBuilder()
    groups = builder.build(pubs)
    assert len(groups) >= 1


def test_project_normalized_fixture(project_normalized: str, tmp_path: Path) -> None:
    assert project_normalized == "lean_energy"
    db_file = tmp_path / "project_normalized.db"
    pub_repo = SqliteProjectPublicationRepository(db_file)
    norm_repo = SqliteNormalizationExecutionRepository(db_file)

    assert pub_repo.count_by_project(project_normalized) == 10
    execution = norm_repo.get_for_project(project_normalized)
    assert execution is not None
    assert execution.clean_records == 10
    assert execution.status == "completed"
