"""
Regression tests for Project hard delete API and CORS preflight behaviour.

Coverage:
- DELETE /projects/{project_id} returns 204 and removes the project.
- DELETE /projects/{unknown} returns 404.
- After deletion the project is absent from LIST.
- OPTIONS /projects/{project_id} with request-method DELETE from a permitted
  frontend origin returns 200 (not 400) — regression guard for the missing
  DELETE in CORS allow_methods.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.main import app
from app.api.routers.projects import get_project_deletion_service, get_project_repository
from app.domain.duplicate_review import DuplicateDecision, DuplicateGroupReviewDecision
from app.domain.provenance import ProvenanceEntry
from app.domain.publication import Publication
from app.repositories.duplicate_review_decision_repository import SqliteDuplicateReviewDecisionRepository
from app.repositories.import_history_repository import SqliteImportHistoryRepository
from app.repositories.normalization_execution_repository import SqliteNormalizationExecutionRepository
from app.repositories.project_publication_repository import SqliteProjectPublicationRepository
from app.repositories.project_repository import SqliteProjectRepository
from app.repositories.screening_criterion_repository import SqliteScreeningCriterionRepository
from app.repositories.screening_decision_repository import SqliteScreeningDecisionRepository
from app.repositories.search_result_snapshot_repository import (
    SearchResultSnapshot,
    SearchResultSnapshotNotFoundError,
    SqliteSearchResultSnapshotRepository,
)
from app.repositories.search_strategy_repository import SqliteSearchStrategyRepository
from app.repositories.transaction_manager import SqliteTransactionManager
from app.services.project_deletion_service import SqliteProjectDeletionService

client = TestClient(app)

FRONTEND_ORIGIN = "http://localhost:5173"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "test_delete.db"


@pytest.fixture()
def repo(db_path: Path) -> SqliteProjectRepository:
    r = SqliteProjectRepository(db_path)
    deletion_service = _make_service(db_path)

    def _override() -> SqliteProjectRepository:
        return r

    app.dependency_overrides[get_project_repository] = _override
    app.dependency_overrides[get_project_deletion_service] = lambda: deletion_service
    yield r
    app.dependency_overrides.clear()


def _make_service(db_path: Path) -> SqliteProjectDeletionService:
    """Build a ProjectDeletionService where all repos point at the same DB."""
    return SqliteProjectDeletionService(
        project_repo=SqliteProjectRepository(db_path),
        import_history_repo=SqliteImportHistoryRepository(db_path),
        normalization_repo=SqliteNormalizationExecutionRepository(db_path),
        publication_repo=SqliteProjectPublicationRepository(db_path),
        duplicate_review_repo=SqliteDuplicateReviewDecisionRepository(db_path),
        screening_decision_repo=SqliteScreeningDecisionRepository(db_path),
        screening_criterion_repo=SqliteScreeningCriterionRepository(db_path),
        search_strategy_repo=SqliteSearchStrategyRepository(db_path),
        search_result_snapshot_repo=SqliteSearchResultSnapshotRepository(db_path),
        tx_manager=SqliteTransactionManager(db_path),
    )


@pytest.fixture()
def created_project_id(repo: SqliteProjectRepository) -> str:
    """Creates a project via POST and returns its project_id."""
    resp = client.post(
        "/projects",
        json={"title": "Delete Test Project", "description": "For deletion", "protocol_version": "1.0"},
    )
    assert resp.status_code == 201
    return str(resp.json()["project_id"])


# ---------------------------------------------------------------------------
# CORS preflight regression test
# ---------------------------------------------------------------------------

def test_cors_preflight_delete_returns_200(repo: SqliteProjectRepository) -> None:
    """
    OPTIONS /projects/{project_id} with Access-Control-Request-Method: DELETE
    from a permitted frontend origin must return 200, not 400.

    Regression guard: DELETE was missing from allow_methods in CORSMiddleware,
    causing the preflight to be rejected with 400 Bad Request.
    """
    resp = client.options(
        "/projects/some-project-id",
        headers={
            "Origin": FRONTEND_ORIGIN,
            "Access-Control-Request-Method": "DELETE",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert resp.status_code == 200, (
        f"CORS preflight for DELETE returned {resp.status_code}; "
        "DELETE must be included in CORSMiddleware allow_methods"
    )
    allowed = resp.headers.get("access-control-allow-methods", "")
    assert "DELETE" in allowed, (
        f"Access-Control-Allow-Methods header missing DELETE: {allowed!r}"
    )


# ---------------------------------------------------------------------------
# DELETE endpoint functional tests — service operates on the same DB as repo
# ---------------------------------------------------------------------------

def test_delete_project_returns_204(
    db_path: Path, repo: SqliteProjectRepository, created_project_id: str
) -> None:
    """DELETE /projects/{project_id} returns 204 No Content for an existing project."""
    response = client.delete(f"/projects/{created_project_id}")
    assert response.status_code == 204
    assert response.content == b""

    # Verify via API
    get_resp = client.get(f"/projects/{created_project_id}")
    assert get_resp.status_code == 404


def test_delete_project_removes_from_list(
    db_path: Path, repo: SqliteProjectRepository, created_project_id: str
) -> None:
    """After deletion the project must not appear in LIST (including archived)."""
    _make_service(db_path).delete_project(created_project_id)
    list_resp = client.get("/projects", params={"include_archived": True})
    assert list_resp.status_code == 200
    ids = [p["project_id"] for p in list_resp.json()["items"]]
    assert created_project_id not in ids


def test_delete_nonexistent_project_returns_404(repo: SqliteProjectRepository, db_path: Path) -> None:
    """DELETE /projects/{unknown} returns 404 when the project does not exist."""
    from app.repositories.project_repository import ProjectNotFoundError
    service = _make_service(db_path)
    with pytest.raises(ProjectNotFoundError):
        service.delete_project("nonexistent-project-id")


def test_delete_is_idempotent_error_on_second_call(
    db_path: Path, repo: SqliteProjectRepository, created_project_id: str
) -> None:
    """Second DELETE on an already-deleted project raises ProjectNotFoundError."""
    from app.repositories.project_repository import ProjectNotFoundError
    service = _make_service(db_path)
    service.delete_project(created_project_id)
    with pytest.raises(ProjectNotFoundError):
        service.delete_project(created_project_id)


# ---------------------------------------------------------------------------
# HTTP-level DELETE endpoint tests (via TestClient, repo overridden via DI)
# ---------------------------------------------------------------------------

def test_http_delete_nonexistent_project_returns_404(repo: SqliteProjectRepository) -> None:
    """DELETE /projects/{unknown} via HTTP returns 404."""
    resp = client.delete("/projects/nonexistent-xyz")
    assert resp.status_code == 404


def test_delete_rolls_back_all_cleanup_on_failure(
    db_path: Path, repo: SqliteProjectRepository, created_project_id: str
) -> None:
    duplicate_reviews = SqliteDuplicateReviewDecisionRepository(db_path)
    duplicate_reviews.save_decision(
        created_project_id,
        "rollback-group",
        DuplicateGroupReviewDecision(decision=DuplicateDecision.APPROVE),
    )
    snapshots = SqliteSearchResultSnapshotRepository(db_path)
    snapshot = _snapshot(created_project_id, "rollback-source")
    snapshots.save(snapshot)

    class FailingSearchStrategyRepository(SqliteSearchStrategyRepository):
        def delete_for_project(self, project_id, *, connection=None):
            raise RuntimeError("injected cleanup failure")

    service = SqliteProjectDeletionService(
        project_repo=repo,
        import_history_repo=SqliteImportHistoryRepository(db_path),
        normalization_repo=SqliteNormalizationExecutionRepository(db_path),
        publication_repo=SqliteProjectPublicationRepository(db_path),
        duplicate_review_repo=duplicate_reviews,
        screening_decision_repo=SqliteScreeningDecisionRepository(db_path),
        screening_criterion_repo=SqliteScreeningCriterionRepository(db_path),
        search_strategy_repo=FailingSearchStrategyRepository(db_path),
        search_result_snapshot_repo=snapshots,
        tx_manager=SqliteTransactionManager(db_path),
    )

    with pytest.raises(RuntimeError, match="injected cleanup failure"):
        service.delete_project(created_project_id)

    assert repo.get(created_project_id).project_id == created_project_id
    assert "rollback-group" in duplicate_reviews.list_decisions_for_project(created_project_id)
    assert snapshots.get(created_project_id, snapshot.snapshot_id) == snapshot


def test_delete_is_project_scoped_and_accepts_archived_project(
    db_path: Path, repo: SqliteProjectRepository, created_project_id: str
) -> None:
    other_response = client.post(
        "/projects",
        json={"title": "Project B", "description": "Must remain", "protocol_version": "1.0"},
    )
    assert other_response.status_code == 201
    other_id = str(other_response.json()["project_id"])
    duplicate_reviews = SqliteDuplicateReviewDecisionRepository(db_path)
    duplicate_reviews.save_decision(
        created_project_id,
        "project-a-group",
        DuplicateGroupReviewDecision(decision=DuplicateDecision.APPROVE),
    )
    duplicate_reviews.save_decision(
        other_id,
        "project-b-group",
        DuplicateGroupReviewDecision(decision=DuplicateDecision.REJECT),
    )
    snapshots = SqliteSearchResultSnapshotRepository(db_path)
    project_a_snapshot = snapshots.save(_snapshot(created_project_id, "project-a-source"))
    project_b_snapshot = snapshots.save(_snapshot(other_id, "project-b-source"))
    _seed_project_owned_rows(db_path, created_project_id, "a")
    _seed_project_owned_rows(db_path, other_id, "b")
    repo.archive(created_project_id)

    response = client.delete(f"/projects/{created_project_id}")

    assert response.status_code == 204
    assert repo.get(other_id).project_id == other_id
    assert "project-b-group" in duplicate_reviews.list_decisions_for_project(other_id)
    with pytest.raises(SearchResultSnapshotNotFoundError):
        snapshots.get(created_project_id, project_a_snapshot.snapshot_id)
    assert snapshots.get(other_id, project_b_snapshot.snapshot_id) == project_b_snapshot
    with sqlite3.connect(db_path) as connection:
        for table in (
            "import_history",
            "project_publications",
            "screening_criteria",
            "screening_decisions",
        ):
            assert connection.execute(
                f"SELECT COUNT(*) FROM {table} WHERE project_id = ?",  # noqa: S608 - fixed table allowlist
                (created_project_id,),
            ).fetchone()[0] == 0
            assert connection.execute(
                f"SELECT COUNT(*) FROM {table} WHERE project_id = ?",  # noqa: S608 - fixed table allowlist
                (other_id,),
            ).fetchone()[0] == 1


def _snapshot(project_id: str, source_id: str) -> SearchResultSnapshot:
    run_id = uuid4()
    publication = Publication(
        title=f"Publication from {source_id}",
        provenance=[
            ProvenanceEntry(
                source="openalex",
                source_record_id=source_id,
                run_id=run_id,
            )
        ],
    )
    return SearchResultSnapshot.create(
        project_id=project_id,
        search_run_id=run_id,
        provider="openalex",
        source_id=source_id,
        publication=publication,
    )


def _seed_project_owned_rows(database: Path, project_id: str, suffix: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    publication = Publication(title=f"Publication {suffix}")
    with sqlite3.connect(database) as connection:
        connection.execute(
            """INSERT INTO import_history
            (import_id, project_id, source_type, records_count, status, warnings, created_at)
            VALUES (?, ?, 'provider', 1, 'success', '[]', ?)""",
            (f"import-{suffix}", project_id, now),
        )
        connection.execute(
            """INSERT INTO project_publications
            (project_id, record_id, position, title, title_normalized, publication_year,
             authors, identifiers, provenance, created_at, document)
            VALUES (?, ?, 0, ?, ?, NULL, '[]', '[]', '[]', ?, ?)""",
            (
                project_id,
                str(publication.record_id),
                publication.title,
                publication.title_normalized,
                publication.created_at.isoformat(),
                json.dumps(publication.model_dump(mode="json")),
            ),
        )
        connection.execute(
            """INSERT INTO screening_criteria
            (criterion_id, project_id, name, criterion_type, screening_stage,
             display_order, is_active, is_required)
            VALUES (?, ?, 'Criterion', 'inclusion', 'title_abstract', 0, 1, 0)""",
            (f"criterion-{suffix}", project_id),
        )
        connection.execute(
            """INSERT INTO screening_decisions
            (decision_id, project_id, publication_id, stage, outcome, reviewer_id, decided_at)
            VALUES (?, ?, ?, 'title_abstract', 'include', 'reviewer', ?)""",
            (f"decision-{suffix}", project_id, str(publication.record_id), now),
        )
