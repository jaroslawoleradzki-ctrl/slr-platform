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
from app.domain.full_text_screening import FullTextAvailability
from app.domain.provenance import ProvenanceEntry
from app.domain.publication import Publication
from app.repositories.conflict_resolution_repository import SqliteConflictResolutionRepository
from app.repositories.duplicate_review_decision_repository import SqliteDuplicateReviewDecisionRepository
from app.repositories.full_text_availability_repository import SqliteFullTextAvailabilityRepository
from app.repositories.import_history_repository import SqliteImportHistoryRepository
from app.repositories.normalization_execution_repository import SqliteNormalizationExecutionRepository
from app.repositories.project_publication_repository import SqliteProjectPublicationRepository
from app.repositories.project_repository import SqliteProjectRepository
from app.repositories.screening_criterion_repository import SqliteScreeningCriterionRepository
from app.repositories.screening_decision_repository import SqliteScreeningDecisionRepository
from app.repositories.screening_reviewer_assignment_repository import (
    SqliteScreeningReviewerAssignmentRepository,
)
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
        full_text_availability_repo=SqliteFullTextAvailabilityRepository(db_path),
        screening_reviewer_assignment_repo=SqliteScreeningReviewerAssignmentRepository(db_path),
        conflict_resolution_repo=SqliteConflictResolutionRepository(db_path),
        classification_repo=_synthesis_classification_repo(db_path),
        matrix_repo=_synthesis_matrix_repo(db_path),
        mechanism_repo=_synthesis_mechanism_repo(db_path),
        context_repo=_synthesis_context_repo(db_path),
        gap_repo=_synthesis_gap_repo(db_path),
        snapshot_repo=_synthesis_snapshot_repo(db_path),
        tx_manager=SqliteTransactionManager(db_path),
    )


def _synthesis_classification_repo(db_path: Path):
    from app.repositories.synthesis_classification_repository import SqliteSynthesisClassificationRepository
    return SqliteSynthesisClassificationRepository(db_path)


def _synthesis_matrix_repo(db_path: Path):
    from app.repositories.synthesis_matrix_repository import SqliteSynthesisMatrixRepository
    return SqliteSynthesisMatrixRepository(db_path)


def _synthesis_mechanism_repo(db_path: Path):
    from app.repositories.synthesis_mechanism_repository import SqliteSynthesisMechanismRepository
    return SqliteSynthesisMechanismRepository(db_path)


def _synthesis_context_repo(db_path: Path):
    from app.repositories.synthesis_context_repository import SqliteSynthesisContextRepository
    return SqliteSynthesisContextRepository(db_path)


def _synthesis_gap_repo(db_path: Path):
    from app.repositories.synthesis_gap_repository import SqliteSynthesisGapRepository
    return SqliteSynthesisGapRepository(db_path)


def _synthesis_snapshot_repo(db_path: Path):
    from app.repositories.synthesis_snapshot_repository import SqliteSynthesisSnapshotRepository
    return SqliteSynthesisSnapshotRepository(db_path)


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
        screening_reviewer_assignment_repo=SqliteScreeningReviewerAssignmentRepository(db_path),
        conflict_resolution_repo=SqliteConflictResolutionRepository(db_path),
        classification_repo=_synthesis_classification_repo(db_path),
        matrix_repo=_synthesis_matrix_repo(db_path),
        mechanism_repo=_synthesis_mechanism_repo(db_path),
        context_repo=_synthesis_context_repo(db_path),
        gap_repo=_synthesis_gap_repo(db_path),
        snapshot_repo=_synthesis_snapshot_repo(db_path),
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
    availability = SqliteFullTextAvailabilityRepository(db_path)
    reviewer_assignments = SqliteScreeningReviewerAssignmentRepository(db_path)
    project_a_snapshot = snapshots.save(_snapshot(created_project_id, "project-a-source"))
    project_b_snapshot = snapshots.save(_snapshot(other_id, "project-b-source"))
    _seed_project_owned_rows(db_path, created_project_id, "a")
    _seed_project_owned_rows(db_path, other_id, "b")
    availability.save(FullTextAvailability(project_id=created_project_id, publication_id=uuid4()))
    availability.save(FullTextAvailability(project_id=other_id, publication_id=uuid4()))
    from app.domain.screening import ScreeningStage

    reviewer_assignments.replace_active(created_project_id, ScreeningStage.TITLE_ABSTRACT, ["alice"])
    reviewer_assignments.replace_active(other_id, ScreeningStage.TITLE_ABSTRACT, ["bob"])
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
            "full_text_availability",
            "screening_reviewer_assignments",
            "screening_conflict_resolutions",
        ):
            assert connection.execute(
                f"SELECT COUNT(*) FROM {table} WHERE project_id = ?",  # noqa: S608 - fixed table allowlist
                (created_project_id,),
            ).fetchone()[0] == 0
            assert connection.execute(
                f"SELECT COUNT(*) FROM {table} WHERE project_id = ?",  # noqa: S608 - fixed table allowlist
                (other_id,),
            ).fetchone()[0] == 1
        assert connection.execute(
            "SELECT COUNT(*) FROM screening_conflict_resolution_decisions WHERE resolution_id = ?",
            ("resolution-a",),
        ).fetchone()[0] == 0
        assert connection.execute(
            "SELECT COUNT(*) FROM screening_conflict_resolution_decisions WHERE resolution_id = ?",
            ("resolution-b",),
        ).fetchone()[0] == 1


def test_delete_removes_all_synthesis_data(
    db_path: Path, repo: SqliteProjectRepository, created_project_id: str
) -> None:
    """Phase 10 synthesis rows (Tasks 10.2-10.7) are removed on project hard-delete.

    Regression guard: before Task 10.8 the project deletion service did not clean
    any synthesis table, and FK cascades never fired because the transaction
    manager connection did not enable PRAGMA foreign_keys.
    """
    _seed_synthesis_rows(db_path, created_project_id)

    with sqlite3.connect(db_path) as connection:
        for table in _SYNTHESIS_TABLES:
            assert connection.execute(
                f"SELECT COUNT(*) FROM {table} WHERE project_id = ?",  # noqa: S608 - fixed allowlist
                (created_project_id,),
            ).fetchone()[0] == 1, f"expected seed row in {table}"

    _make_service(db_path).delete_project(created_project_id)

    with sqlite3.connect(db_path) as connection:
        for table in _SYNTHESIS_TABLES:
            assert connection.execute(
                f"SELECT COUNT(*) FROM {table} WHERE project_id = ?",  # noqa: S608 - fixed allowlist
                (created_project_id,),
            ).fetchone()[0] == 0, f"synthesis rows remained in {table} after delete"


_SYNTHESIS_TABLES = (
    "synthesis_lean_categories",
    "synthesis_term_mappings",
    "synthesis_analytical_relations",
    "synthesis_mechanism_categories",
    "synthesis_mechanism_pathways",
    "synthesis_context_categories",
    "synthesis_relation_context_links",
    "synthesis_research_gaps",
    "synthesis_research_gap_links",
    "synthesis_snapshots",
)


def _seed_synthesis_rows(db_path: Path, project_id: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    pub_id = str(uuid4())
    group_item_id = str(uuid4())
    revision_id = str(uuid4())
    relation_id = str(uuid4())
    pathway_id = str(uuid4())
    link_id = str(uuid4())
    gap_id = str(uuid4())
    snapshot_id = str(uuid4())
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            "INSERT INTO synthesis_lean_categories (project_id, category_id, name, display_order) VALUES (?, 'cat_1', 'Cat', 1)",
            (project_id,),
        )
        connection.execute(
            "INSERT INTO synthesis_term_mappings "
            "(mapping_id, project_id, term_type, source_value, analytical_category_id, approval_state) "
            "VALUES (?, ?, 'lean_practice', '5S', 'cat_1', 'pending')",
            (str(uuid4()), project_id),
        )
        connection.execute(
            "INSERT INTO synthesis_analytical_relations "
            "(relation_id, project_id, publication_id, latest_revision_id, group_item_id, item_index, "
            "source_practice, source_effect, direction, evidence_character, approval_state) "
            "VALUES (?, ?, ?, ?, ?, 1, '5S', 'elec', 'positive', 'empirical', 'approved')",
            (relation_id, project_id, pub_id, revision_id, group_item_id),
        )
        connection.execute(
            "INSERT INTO synthesis_mechanism_categories (project_id, category_id, name, display_order) VALUES (?, 'mc1', 'MC', 1)",
            (project_id,),
        )
        connection.execute(
            "INSERT INTO synthesis_mechanism_pathways "
            "(pathway_id, project_id, analytical_relation_id, group_item_id, publication_id, "
            "latest_revision_id, is_review_synthesized, approval_state) "
            "VALUES (?, ?, ?, ?, ?, ?, 0, 'pending')",
            (pathway_id, project_id, relation_id, group_item_id, pub_id, revision_id),
        )
        connection.execute(
            "INSERT INTO synthesis_context_categories (project_id, category_id, name, display_order) VALUES (?, 'cc1', 'CC', 1)",
            (project_id,),
        )
        connection.execute(
            "INSERT INTO synthesis_relation_context_links "
            "(link_id, project_id, analytical_relation_id, group_item_id, publication_id, "
            "latest_revision_id, source_context_text, context_impact, approval_state) "
            "VALUES (?, ?, ?, ?, ?, ?, 'context text', 'ENABLE', 'pending')",
            (link_id, project_id, relation_id, group_item_id, pub_id, revision_id),
        )
        connection.execute(
            "INSERT INTO synthesis_research_gaps "
            "(project_id, gap_id, gap_type, title, rationale, researcher_id, created_at, updated_at) "
            "VALUES (?, ?, 'thematic', 'Gap', 'Rationale', 'researcher', ?, ?)",
            (project_id, gap_id, now, now),
        )
        connection.execute(
            "INSERT INTO synthesis_research_gap_links "
            "(link_id, project_id, gap_id, link_type, target_id, group_item_id, publication_id, latest_revision_id) "
            "VALUES (?, ?, ?, 'analytical_relation', ?, ?, ?, ?)",
            (str(uuid4()), project_id, gap_id, relation_id, group_item_id, pub_id, revision_id),
        )
        connection.execute(
            "INSERT INTO synthesis_snapshots "
            "(snapshot_id, project_id, version, actor, extraction_dataset_hash, classification_version, "
            "content_hash, content_json, created_at) "
            "VALUES (?, ?, 1, 'researcher', ?, ?, ?, '{}', ?)",
            (snapshot_id, project_id, "a" * 64, "b" * 64, "c" * 64, now),
        )


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
        connection.execute(
            """INSERT INTO screening_conflict_resolutions
            (resolution_id, project_id, publication_id, stage, decision_set_key,
             resolved_outcome, resolver_id, rationale, resolved_at)
            VALUES (?, ?, ?, 'title_abstract', ?, 'include', 'resolver', 'resolution rationale', ?)""",
            (f"resolution-{suffix}", project_id, str(publication.record_id), f"key-{suffix}", now),
        )
        connection.execute(
            """INSERT INTO screening_conflict_resolution_decisions
            (resolution_id, decision_id, reviewer_id, outcome)
            VALUES (?, ?, 'reviewer', 'include')""",
            (f"resolution-{suffix}", f"decision-{suffix}"),
        )
