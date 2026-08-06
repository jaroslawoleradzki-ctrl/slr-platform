from pathlib import Path

import pytest

from app.repositories.import_history_repository import (
    SqliteImportHistoryRepository,
)
from app.repositories.normalization_execution_repository import (
    SqliteNormalizationExecutionRepository,
)
from app.repositories.project_publication_repository import (
    SqliteProjectPublicationRepository,
)
from tests.fixtures.factories import (
    make_import_history,
    make_normalization_execution,
    make_publication,
)


@pytest.fixture
def empty_project(tmp_path: Path) -> str:
    """Fixture providing an empty project with 0 publications, history, or executions."""
    project_id = "ai_architecture"
    db_file = tmp_path / "empty_project.db"
    repo = SqliteProjectPublicationRepository(db_file)
    repo.get_publications(project_id)
    return project_id


@pytest.fixture
def project_100(tmp_path: Path) -> str:
    """Fixture providing a project pre-populated with exactly 100 publications and import history."""
    project_id = "lean_energy"
    db_file = tmp_path / "project_100.db"

    pub_repo = SqliteProjectPublicationRepository(db_file)
    history_repo = SqliteImportHistoryRepository(db_file)

    publications = [make_publication(index=i) for i in range(1, 101)]
    pub_repo.add_publications(project_id, publications)

    history_record = make_import_history(
        project_id=project_id,
        records_count=100,
        provider="openalex",
    )
    history_repo.create(history_record)

    return project_id


@pytest.fixture
def project_duplicates(tmp_path: Path) -> str:
    """Fixture providing a project pre-populated with deterministic candidate duplicate publication groups."""
    project_id = "lean_energy"
    db_file = tmp_path / "project_duplicates.db"

    pub_repo = SqliteProjectPublicationRepository(db_file)
    history_repo = SqliteImportHistoryRepository(db_file)

    pub1_a = make_publication(
        index=1,
        title="Energy reduction through lean production: A systematic review",
        doi="10.1016/j.jclepro.2021.102834",
        openalex_id="W3128349201",
        source="OpenAlex",
        source_id="W3128349201",
    )
    pub1_b = make_publication(
        index=2,
        title="Energy reduction through lean production: Systematic Review",
        doi="10.1016/j.jclepro.2021.102834",
        openalex_id="W3128349201",
        source="Crossref",
        source_id="10.1016/j.jclepro.2021.102834",
    )
    pub2_a = make_publication(
        index=3,
        title="Applying Kaizen principles to lower electricity consumption",
        doi="10.1007/s00170-019-04122-z",
        source="Semantic Scholar",
        source_id="S2-31204912",
    )
    pub2_b = make_publication(
        index=4,
        title="Applying Kaizen principles to lower electricity consumption.",
        doi="10.1007/s00170-019-04122-z",
        source="RIS file",
        source_id="IMP-002",
    )
    pub3_unique = make_publication(
        index=5,
        title="Unique publication on industrial heat recovery without duplicates",
        doi="10.1016/j.enercon.2024.109988",
        source="OpenAlex",
        source_id="W99887766",
    )

    pub_repo.add_publications(
        project_id, [pub1_a, pub1_b, pub2_a, pub2_b, pub3_unique]
    )

    history_record = make_import_history(
        project_id=project_id,
        records_count=5,
        provider="openalex",
    )
    history_repo.create(history_record)

    return project_id


@pytest.fixture
def project_normalized(tmp_path: Path) -> str:
    """Fixture providing a project with 10 normalized publications and a recorded normalization summary."""
    project_id = "lean_energy"
    db_file = tmp_path / "project_normalized.db"

    pub_repo = SqliteProjectPublicationRepository(db_file)
    history_repo = SqliteImportHistoryRepository(db_file)
    norm_repo = SqliteNormalizationExecutionRepository(db_file)

    publications = [
        make_publication(
            index=i,
            doi=f"10.1000/test.norm.{i}",
            title=f"Normalized Paper Title {i}",
        )
        for i in range(1, 11)
    ]
    pub_repo.add_publications(project_id, publications)

    history_record = make_import_history(
        project_id=project_id,
        records_count=10,
        provider="openalex",
    )
    history_repo.create(history_record)

    execution = make_normalization_execution(
        project_id=project_id,
        processed_records=10,
        clean_records=10,
        status="completed",
    )
    norm_repo.save(execution)

    return project_id
