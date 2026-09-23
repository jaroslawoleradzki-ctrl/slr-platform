from __future__ import annotations

import sqlite3
from uuid import UUID, uuid4

import pytest

from app.repositories.import_history_repository import SqliteImportHistoryRepository
from app.repositories.project_publication_repository import SqliteProjectPublicationRepository
from app.services.production_reconciliation_service import (
    ProductionReconciliationService,
    ReconciliationRequest,
    ReconciliationSafetyError,
)
from tests.fixtures.factories import make_import_history, make_publication


def _fixture(tmp_path):
    db = tmp_path / "disposable-reconciliation.db"
    pubs = SqliteProjectPublicationRepository(db)
    project, import_id = "reconcile_fixture", uuid4()
    with sqlite3.connect(db) as conn:
        conn.execute("INSERT INTO projects(project_id, title) VALUES (?, ?)", (project, project))
    SqliteImportHistoryRepository(db).create(
        make_import_history(project_id=project, records_count=20, provider="crossref", import_id=import_id)
    )
    pubs.import_source_publications(
        project,
        [make_publication(i, source="Crossref", source_id=f"CR-{i}") for i in range(1, 21)],
        import_id=import_id,
    )
    removed = tuple(UUID(f"00000000-0000-0000-0000-{i:012d}") for i in range(13, 21))
    with sqlite3.connect(db) as conn:
        conn.executemany(
            "UPDATE project_publications SET pre_screening_status='removed' WHERE project_id=? AND record_id=?",
            [(project, str(i)) for i in removed],
        )
    return db, project, import_id, removed


def test_disposable_lifecycle_dry_run_execute_and_replay(tmp_path):
    db, project, import_id, removed = _fixture(tmp_path)
    service = ProductionReconciliationService(db)
    request = ReconciliationRequest(project, import_id, removed, 8, "test-operator")
    before = sqlite3.connect(db).execute("SELECT COUNT(*) FROM project_publications").fetchone()[0]
    dry = service.dry_run(request)
    assert dry.status == "preflight-ok" and dry.physical_rows_to_remove == 8 and dry.expected_active_corpus_after == 12
    assert sqlite3.connect(db).execute("SELECT COUNT(*) FROM project_publications").fetchone()[0] == before
    assert service.execute(request, backup_acknowledged=True).status == "complete"
    with sqlite3.connect(db) as conn:
        assert (
            conn.execute("SELECT COUNT(*) FROM project_publications WHERE project_id=?", (project,)).fetchone()[0] == 12
        )
        assert (
            conn.execute("SELECT COUNT(*) FROM pre_screening_archive WHERE project_id=?", (project,)).fetchone()[0] == 8
        )
        assert (
            conn.execute("SELECT records_count FROM import_history WHERE import_id=?", (str(import_id),)).fetchone()[0]
            == 20
        )
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    assert service.dry_run(request).status == "already-reconciled"


def test_rejects_retained_or_wrong_import_before_mutation(tmp_path):
    db, project, import_id, removed = _fixture(tmp_path)
    service = ProductionReconciliationService(db)
    with pytest.raises(ReconciliationSafetyError, match="not legacy pre-screening removed"):
        service.dry_run(
            ReconciliationRequest(project, import_id, (UUID("00000000-0000-0000-0000-000000000001"),), 1, "test")
        )
    with pytest.raises(ReconciliationSafetyError, match="different or NULL import_id"):
        service.dry_run(ReconciliationRequest(project, uuid4(), (removed[0],), 1, "test"))


def test_formal_screening_blocks_removal(tmp_path):
    db, project, import_id, removed = _fixture(tmp_path)
    with sqlite3.connect(db) as conn:
        conn.execute(
            "INSERT INTO screening_decisions(decision_id, project_id, publication_id, stage, reviewer_id, outcome, decided_at) VALUES (?, ?, ?, 'title_abstract', 'r', 'include', '2026-01-01T00:00:00+00:00')",
            (str(uuid4()), project, str(removed[0])),
        )
    with pytest.raises(ReconciliationSafetyError) as failure:
        ProductionReconciliationService(db).dry_run(ReconciliationRequest(project, import_id, (removed[0],), 1, "test"))
    assert failure.value.code == "FORMAL_SCREENING_CONFLICT"
