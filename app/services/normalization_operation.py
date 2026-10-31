"""Atomic normalization, duplicate projection and execution-summary persistence."""

import logging
import sqlite3
from time import perf_counter

from app.repositories.normalization_execution_repository import NormalizationExecutionRepository
from app.repositories.project_publication_repository import (
    ProjectPublicationRepository,
    SqliteProjectPublicationRepository,
)
from app.repositories.transaction_manager import SqliteTransactionManager
from app.services.normalization_service import NormalizationExecution, normalize_project
from app.services.project_duplicate_service import ProjectDuplicateService

logger = logging.getLogger(__name__)


def run_project_normalization(
    repository: ProjectPublicationRepository,
    executions: NormalizationExecutionRepository,
    project_id: str,
    *,
    duplicate_service: ProjectDuplicateService | None = None,
    connection: sqlite3.Connection | None = None,
) -> NormalizationExecution:
    if not isinstance(repository, SqliteProjectPublicationRepository):
        execution = normalize_project(repository, project_id)
        executions.save(execution)
        return execution

    if connection is not None:
        execution = normalize_project(repository, project_id, connection=connection)
        duplicates = duplicate_service or ProjectDuplicateService(repository=repository)
        duplicates.materialize_candidate_group_projection(project_id, connection=connection)
        executions.save(execution, connection=connection)
        return execution

    transaction_manager = SqliteTransactionManager(repository._database_path)
    duplicates = duplicate_service or ProjectDuplicateService(
        repository=repository, transaction_manager=transaction_manager
    )
    started = perf_counter()
    try:
        with transaction_manager.transaction() as connection:
            execution = normalize_project(repository, project_id, connection=connection)
            duplicates.materialize_candidate_group_projection(project_id, connection=connection)
            executions.save(execution, connection=connection)
    except sqlite3.OperationalError as exc:
        logger.warning(
            "normalization_transaction outcome=error busy_or_locked=%s duration_ms=%.3f",
            "locked" in str(exc).lower() or "busy" in str(exc).lower(),
            (perf_counter() - started) * 1000,
        )
        raise
    logger.info(
        "normalization_transaction outcome=committed busy_or_locked=false duration_ms=%.3f records=%d",
        (perf_counter() - started) * 1000,
        execution.processed_records,
    )
    return execution
