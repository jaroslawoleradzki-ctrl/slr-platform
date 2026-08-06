from pathlib import Path

from app.repositories.duplicate_review_decision_repository import (
    DuplicateReviewDecisionRepository,
    SqliteDuplicateReviewDecisionRepository,
)
from app.repositories.import_history_repository import (
    ImportHistoryRepository,
    SqliteImportHistoryRepository,
)
from app.repositories.normalization_execution_repository import (
    NormalizationExecutionRepository,
    SqliteNormalizationExecutionRepository,
)
from app.repositories.project_publication_repository import (
    ProjectPublicationRepository,
    SqliteProjectPublicationRepository,
)
from app.repositories.search_strategy_repository import (
    SearchStrategyRepository,
    SqliteSearchStrategyRepository,
)


def test_sqlite_project_publication_repository_implements_protocol(
    tmp_path: Path,
) -> None:
    db_file = tmp_path / "test.db"
    repo: ProjectPublicationRepository = SqliteProjectPublicationRepository(db_file)
    assert isinstance(repo, ProjectPublicationRepository)


def test_sqlite_import_history_repository_implements_protocol(tmp_path: Path) -> None:
    db_file = tmp_path / "test.db"
    repo: ImportHistoryRepository = SqliteImportHistoryRepository(db_file)
    assert isinstance(repo, ImportHistoryRepository)


def test_sqlite_normalization_execution_repository_implements_protocol(
    tmp_path: Path,
) -> None:
    db_file = tmp_path / "test.db"
    repo: NormalizationExecutionRepository = SqliteNormalizationExecutionRepository(
        db_file
    )
    assert isinstance(repo, NormalizationExecutionRepository)


def test_sqlite_duplicate_review_decision_repository_implements_protocol(
    tmp_path: Path,
) -> None:
    db_file = tmp_path / "test.db"
    repo: DuplicateReviewDecisionRepository = (
        SqliteDuplicateReviewDecisionRepository(db_file)
    )
    assert isinstance(repo, DuplicateReviewDecisionRepository)


def test_sqlite_search_strategy_repository_implements_protocol(
    tmp_path: Path,
) -> None:
    db_file = tmp_path / "test.db"
    repo: SearchStrategyRepository = SqliteSearchStrategyRepository(db_file)
    assert isinstance(repo, SearchStrategyRepository)
