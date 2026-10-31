from __future__ import annotations

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier, Event

import pytest
from fastapi.testclient import TestClient

from app.api.main import app
from app.api.routers.deduplication import get_duplicate_service
from app.repositories.duplicate_merge_repository import SqliteDuplicateMergeRepository
from app.repositories.duplicate_review_decision_repository import (
    SqliteDuplicateReviewDecisionRepository,
)
from app.repositories.import_history_repository import SqliteImportHistoryRepository
from app.repositories.import_source_record_repository import (
    SqliteImportSourceRecordRepository,
)
from app.repositories.normalization_execution_repository import (
    SqliteNormalizationExecutionRepository,
)
from app.repositories.project_publication_repository import (
    SqliteProjectPublicationRepository,
)
from app.repositories.transaction_manager import SqliteTransactionManager
from app.services.project_duplicate_service import ProjectDuplicateService
from app.services.project_import_service import ProjectImportService
from app.services.screening_input_service import ScreeningInputReadinessStatus, ScreeningInputService
from tests.fixtures.factories import make_publication


def _ris(title: str, year: int | None = None, doi: str | None = None) -> str:
    lines = ["TY  - JOUR", f"TI  - {title}"]
    if year is not None:
        lines.append(f"PY  - {year}")
    if doi is not None:
        lines.append(f"DO  - {doi}")
    lines.append("ER  - ")
    return "\n".join(lines) + "\n"


@pytest.fixture
def environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db = tmp_path / "v073_r2.db"
    monkeypatch.setenv("SLR_DATABASE_PATH", str(db))
    pub = SqliteProjectPublicationRepository(db)
    SqliteImportHistoryRepository(db)
    SqliteNormalizationExecutionRepository(db)
    source = SqliteImportSourceRecordRepository(db)
    decisions = SqliteDuplicateReviewDecisionRepository(db)
    merges = SqliteDuplicateMergeRepository(db)
    duplicate_service = ProjectDuplicateService(
        pub,
        decisions,
        merge_repository=merges,
        transaction_manager=SqliteTransactionManager(db),
        source_record_repository=source,
    )
    app.dependency_overrides[get_duplicate_service] = lambda: duplicate_service
    con = sqlite3.connect(db)
    con.execute("INSERT INTO projects(project_id,title) VALUES ('p1','Project 1')")
    con.commit()
    con.close()
    client = TestClient(app)
    yield client, pub, source, duplicate_service, decisions, db
    app.dependency_overrides.clear()


def _upload(client: TestClient, filename: str, content: str, source_database: str = "google_scholar_pop"):
    response = client.post(
        "/api/v1/projects/p1/imports",
        files={"file": (filename, content, "application/x-research-info-systems")},
        data={"source_database": source_database},
    )
    assert response.status_code == 201, response.text
    return response


def _groups(client: TestClient):
    response = client.get("/api/v1/projects/p1/duplicate-groups")
    assert response.status_code == 200
    return response.json()["groups"]


def test_real_path_title_candidate_includes_doi_bearing_counterpart(environment) -> None:
    client, _, source, _, _, db = environment
    _upload(client, "GS01.ris", _ris("Real Shared Title", 2020, "10.1000/real-shared"))
    _upload(client, "GS2.ris", _ris("Real Shared Title", 2021))
    # Candidate projection and membership snapshots are materialized with the
    # import transaction, never as a side effect of this GET.
    before_ids = {
        record.source_record_id: record.duplicate_candidate_group_id
        for record in source.list_source_records("p1")
    }
    with sqlite3.connect(db) as connection:
        before_snapshots = connection.execute(
            "SELECT project_id, group_id, publication_ids_json, match_type, match_reason, status, observed_at "
            "FROM duplicate_candidate_group_snapshots ORDER BY group_id"
        ).fetchall()
    groups = _groups(client)
    after_ids = {
        record.source_record_id: record.duplicate_candidate_group_id
        for record in source.list_source_records("p1")
    }
    with sqlite3.connect(db) as connection:
        after_snapshots = connection.execute(
            "SELECT project_id, group_id, publication_ids_json, match_type, match_reason, status, observed_at "
            "FROM duplicate_candidate_group_snapshots ORDER BY group_id"
        ).fetchall()
    assert after_ids == before_ids
    assert after_snapshots == before_snapshots
    assert len(groups) == 1
    assert groups[0]["records_count"] == 2
    assert "conflicting DOI" in groups[0]["reason"]
    assert set(before_ids.values()) == {groups[0]["group_id"]}
    records = source.list_source_records("p1")
    assert len(records) == 2
    assert {record.duplicate_candidate_group_id for record in records} == {
        groups[0]["group_id"]
    }


def test_duplicate_group_get_preserves_all_history_with_and_without_candidates(environment) -> None:
    client, _, source, duplicate_service, decisions, db = environment
    merges = SqliteDuplicateMergeRepository(db)
    _upload(client, "merged-a.ris", _ris("Historical merged group", 2020))
    _upload(client, "merged-b.ris", _ris("Historical merged group", 2021))
    merged_group = _groups(client)[0]
    duplicate_service.record_decision("p1", merged_group["group_id"], "APPROVE", "human-approved")
    duplicate_service.merge_group("p1", merged_group["group_id"])
    _upload(client, "pending-a.ris", _ris("Pending candidate group", 2020))
    _upload(client, "pending-b.ris", _ris("Pending candidate group", 2021))

    with sqlite3.connect(db) as connection:
        before_snapshots = connection.execute(
            "SELECT * FROM duplicate_candidate_group_snapshots WHERE project_id = 'p1' ORDER BY group_id"
        ).fetchall()
    before_ids = {
        record.source_record_id: record.duplicate_candidate_group_id
        for record in source.list_source_records("p1")
    }
    before_decisions = decisions.list_decisions_for_project("p1")
    before_merges = merges.list_merges_for_project("p1")

    response = _groups(client)

    assert any(group["status"] == "PENDING" for group in response)
    assert any(group["status"] == "MERGED" for group in response)
    assert {
        record.source_record_id: record.duplicate_candidate_group_id
        for record in source.list_source_records("p1")
    } == before_ids
    assert decisions.list_decisions_for_project("p1") == before_decisions
    assert merges.list_merges_for_project("p1") == before_merges
    with sqlite3.connect(db) as connection:
        assert connection.execute(
            "SELECT * FROM duplicate_candidate_group_snapshots WHERE project_id = 'p1' ORDER BY group_id"
        ).fetchall() == before_snapshots

    with sqlite3.connect(db) as connection:
        connection.execute("INSERT INTO projects(project_id,title) VALUES ('p2','Empty project')")
        connection.commit()
    empty_before = {
        "ids": source.list_source_records("p2"),
        "decisions": decisions.list_decisions_for_project("p2"),
        "merges": merges.list_merges_for_project("p2"),
        "snapshots": source.list_candidate_group_snapshots("p2"),
    }
    assert client.get("/api/v1/projects/p2/duplicate-groups").json()["groups"] == []
    assert empty_before == {
        "ids": source.list_source_records("p2"),
        "decisions": decisions.list_decisions_for_project("p2"),
        "merges": merges.list_merges_for_project("p2"),
        "snapshots": source.list_candidate_group_snapshots("p2"),
    }


def test_parallel_duplicate_reads_during_import_return_complete_states(environment) -> None:
    client, _, _, _, _, _ = environment
    barrier = Barrier(9)

    def read_groups():
        barrier.wait(timeout=5)
        return client.get("/api/v1/projects/p1/duplicate-groups")

    def import_pair():
        barrier.wait(timeout=5)
        return _upload(
            client,
            "concurrent-pair.ris",
            _ris("Concurrent synthetic candidate", 2020) + _ris("Concurrent synthetic candidate", 2021),
        )

    with ThreadPoolExecutor(max_workers=9) as executor:
        reads = [executor.submit(read_groups) for _ in range(8)]
        imported = executor.submit(import_pair)
        responses = [future.result(timeout=20) for future in reads]
        import_response = imported.result(timeout=20)

    assert import_response.status_code == 201, import_response.text
    for response in responses:
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["project_id"] == "p1"
        assert payload["total_groups_count"] == len(payload["groups"])
        assert all(group["records_count"] == len(group["records"]) for group in payload["groups"])
    final = client.get("/api/v1/projects/p1/duplicate-groups").json()
    assert any(group["records_count"] == 2 for group in final["groups"])


def test_both_title_only_candidates_are_visible_and_identically_reasoned(environment) -> None:
    client, _, source, _, _, _ = environment
    _upload(client, "GS01.ris", _ris("Both Title Only", 2020))
    _upload(client, "GS2.ris", _ris("Both Title Only", 2020))
    groups = _groups(client)
    assert len(groups) == 1
    assert groups[0]["reason"] == "Identical normalized title without DOI"
    assert all(
        record.duplicate_candidate_group_id == groups[0]["group_id"]
        for record in source.list_source_records("p1")
    )


def test_different_doi_same_title_is_a_candidate(environment) -> None:
    client, _, _, _, _, _ = environment
    _upload(client, "GS01.ris", _ris("Conflicting DOI Title", 2020, "10.1000/one"))
    _upload(client, "GS2.ris", _ris("Conflicting DOI Title", 2020, "10.1000/two"))
    groups = _groups(client)
    assert len(groups) == 1
    assert "conflicting DOI" in groups[0]["reason"]


def test_similar_title_is_a_candidate_not_a_merge(environment) -> None:
    client, _, source, _, _, _ = environment
    _upload(client, "GS01.ris", _ris("Energy efficiency in manufacturing systems", 2020))
    _upload(client, "GS2.ris", _ris("Energy efficiency in manufacturing system", 2020))
    groups = _groups(client)
    assert len(groups) == 1
    assert "Similar normalized title" in groups[0]["reason"]
    assert groups[0]["status"] == "PENDING"
    assert all(
        record.duplicate_candidate_group_id == groups[0]["group_id"]
        for record in source.list_source_records("p1")
    )

    summary = client.get("/api/v1/projects/p1/sources-summary").json()["import_history"]
    assert sum(item["similar_title_candidate_count"] or 0 for item in summary) == 2


def test_sequential_titles_are_not_similar_title_candidates(environment) -> None:
    client, _, _, _, _, _ = environment
    _upload(client, "GS01.ris", _ris("Test Publication Title 201", 2024))
    _upload(client, "GS2.ris", _ris("Test Publication Title 202", 2024))
    assert _groups(client) == []


def test_reviewer_rejection_and_approval_merge_preserve_canonical_ids(environment) -> None:
    client, pub, _, _, decisions, _ = environment
    _upload(client, "GS01.ris", _ris("Decision Title", 2020))
    _upload(client, "GS2.ris", _ris("Decision Title", 2020))
    group = _groups(client)[0]
    group_id = group["group_id"]
    ids = sorted(record["id"] for record in group["records"])

    reject = client.post(
        f"/api/v1/projects/p1/duplicate-groups/{group_id}/decision",
        json={"decision": "REJECT", "rationale": "Different works"},
    )
    assert reject.status_code == 200
    rejected = [item for item in _groups(client) if item["group_id"] == group_id][0]
    assert rejected["status"] == "REJECTED"

    merge_after_reject = client.post(
        f"/api/v1/projects/p1/duplicate-groups/{group_id}/merge",
        json={"rationale": "should fail"},
    )
    assert merge_after_reject.status_code == 422

    approve = client.post(
        f"/api/v1/projects/p1/duplicate-groups/{group_id}/decision",
        json={"decision": "APPROVE", "rationale": "Same work"},
    )
    assert approve.status_code == 200
    merge = client.post(
        f"/api/v1/projects/p1/duplicate-groups/{group_id}/merge",
        json={"rationale": "merge"},
    )
    assert merge.status_code == 200, merge.text
    assert merge.json()["canonical_record_id"] == ids[0]
    live = [item for item in _groups(client) if item["group_id"] == group_id][0]
    assert live["status"] == "MERGED"
    assert live["canonical_record_id"] == ids[0]
    assert decisions.get_decision("p1", group_id) is not None


def test_pending_title_candidate_affects_screening_readiness(environment) -> None:
    client, pub, source, _, decisions, db = environment
    _upload(client, "GS01.ris", _ris("Screening Candidate", 2020))
    _upload(client, "GS2.ris", _ris("Screening Candidate", 2020))
    group = _groups(client)[0]
    input_service = ScreeningInputService(pub, decisions)
    pending = input_service.get_input_set("p1")
    assert pending.ready is False
    assert pending.readiness_status is ScreeningInputReadinessStatus.UNRESOLVED_DUPLICATES

    client.post(
        f"/api/v1/projects/p1/duplicate-groups/{group['group_id']}/decision",
        json={"decision": "REJECT", "rationale": "distinct"},
    )
    after = input_service.get_input_set("p1")
    assert after.readiness_status is not ScreeningInputReadinessStatus.UNRESOLVED_DUPLICATES


def test_diagnostics_match_persisted_state(environment) -> None:
    client, _, source, _, _, _ = environment
    _upload(client, "GS01.ris", _ris("Diagnostic DOI", 2020, "10.1000/diag"))
    _upload(client, "GS2.ris", _ris("Diagnostic DOI Again", 2021, "10.1000/diag"))
    _upload(client, "GS3.ris", _ris("Diagnostic Title", 2020))
    _upload(client, "GS4.ris", _ris("Diagnostic Title", 2021))
    _upload(client, "GS5.ris", _ris("Diagnostic Invalid", 2020, "not-a-doi"))
    _upload(client, "GS6.ris", _ris("Diagnostic Invalid", 2021, "also-not-a-doi"))
    _groups(client)

    body = client.get("/api/v1/projects/p1/sources-summary").json()
    history = body["import_history"]
    all_source = source.list_source_records("p1")
    assert sum(item["source_record_count"] or 0 for item in history) == len(all_source)
    assert sum(item["canonical_publication_count"] or 0 for item in history) == len(
        source.list_source_records("p1")
    ) - sum(1 for item in source.list_skip_audit("p1") if item.match_type == "exact_doi")
    assert sum(item["exact_doi_match_count"] or 0 for item in history) == 1
    assert sum(item["invalid_doi_count"] or 0 for item in history) == 2
    assert sum(item["title_candidate_count"] or 0 for item in history) == 4
    assert all(item["recovery_status"] in {"not_started", None} for item in history)
    assert all(item["audit_available"] for item in history)
    assert len(all_source) == 6


def test_group_changes_are_traceable_and_historical_decision_survives(environment) -> None:
    client, _, source, _, decisions, _ = environment
    _upload(client, "GS01.ris", _ris("Historical Decision", 2020))
    _upload(client, "GS2.ris", _ris("Historical Decision", 2021))
    first_group = _groups(client)[0]
    client.post(
        f"/api/v1/projects/p1/duplicate-groups/{first_group['group_id']}/decision",
        json={"decision": "REJECT", "rationale": "first review"},
    )
    _upload(client, "GS3.ris", _ris("Historical Decision", 2022))
    groups = _groups(client)
    current = [item for item in groups if item["status"] == "PENDING"]
    assert len(current) == 1
    assert current[0]["group_id"] != first_group["group_id"]
    assert decisions.get_decision("p1", first_group["group_id"]) is not None
    snapshots = source.list_candidate_group_snapshots("p1")
    assert any(item["group_id"] == first_group["group_id"] for item in snapshots)
    assert any(item["group_id"] == current[0]["group_id"] for item in snapshots)


def test_validation_failure_is_visible_in_diagnostics(environment) -> None:
    client, _, _, _, _, _ = environment
    invalid = client.post(
        "/api/v1/projects/p1/imports",
        files={
            "file": (
                "invalid.ris",
                "TY  - JOUR\nDO  - 10.1000/no-title\nER  - \n",
                "application/x-research-info-systems",
            )
        },
        data={"source_database": "google_scholar_pop"},
    )
    assert invalid.status_code == 422
    history = client.get("/api/v1/projects/p1/sources-summary").json()["import_history"]
    failed = [item for item in history if item["filename"] == "invalid.ris"]
    assert len(failed) == 1
    assert failed[0]["status"] == "failed"
    assert failed[0]["validation_error_count"] == 1
    assert "missing a title" in failed[0]["warnings"][0]


def test_source_record_api_exposes_candidate_group(environment) -> None:
    client, _, _, _, _, _ = environment
    _upload(client, "GS01.ris", _ris("API Candidate", 2020))
    _upload(client, "GS2.ris", _ris("API Candidate", 2021))
    group = _groups(client)[0]
    import_id = client.get("/api/v1/projects/p1/sources-summary").json()["import_history"][0][
        "import_id"
    ]
    response = client.get(f"/api/v1/projects/p1/imports/{import_id}/source-records")
    assert response.status_code == 200
    items = response.json()["items"]
    assert items
    assert items[0]["duplicate_candidate_group_id"] == group["group_id"]


def test_duplicate_http_diagnostics_measure_completed_response(environment, caplog):
    client, _, _, _, _, _ = environment
    caplog.set_level("INFO")
    response = client.get("/api/v1/projects/p1/duplicate-groups")
    assert response.status_code == 200
    completed = [r.getMessage() for r in caplog.records if "duplicate_groups_response_complete" in r.getMessage()]
    assert len(completed) == 1
    assert "status=200" in completed[0]
    assert f"response_bytes={len(response.content)}" in completed[0]
    assert "p1" not in completed[0]
    correlation = completed[0].split("correlation_id=", 1)[1].split()[0]
    stages = [r.getMessage() for r in caplog.records if r.getMessage().startswith("duplicate_groups_read ")]
    assert len(stages) == 1
    assert f"correlation_id={correlation}" in stages[0]
    assert "readiness_ms=" in stages[0]


@pytest.mark.parametrize("journal_mode", ["DELETE", "WAL"])
def test_import_between_corpus_and_decision_reads_preserves_complete_snapshot(environment, monkeypatch, journal_mode):
    client, _, _, service, _, database = environment
    with sqlite3.connect(database) as connection:
        assert connection.execute(f"PRAGMA journal_mode={journal_mode}").fetchone()[0].upper() == journal_mode
    _upload(client, "before.ris", _ris("Original synthetic publication", 2020))
    before = client.get("/api/v1/projects/p1/duplicate-groups").json()
    # Prepare repository schemas before the forced interleaving: in DELETE
    # mode schema initialization itself can require an exclusive write lock.
    importer = ProjectImportService(
        publication_repository=SqliteProjectPublicationRepository(database),
        import_history_repository=SqliteImportHistoryRepository(database),
        normalization_repository=SqliteNormalizationExecutionRepository(database),
        source_record_repository=SqliteImportSourceRecordRepository(database),
        transaction_manager=SqliteTransactionManager(database),
    )
    new_publications = [make_publication(
        index=index, title="Concurrent complete candidate", doi=None,
        source="ris", source_id=f"concurrent-{index}",
    ) for index in (811, 812)]
    corpus_read = Event()
    writer_materialized = Event()
    resume_read = Event()
    original_read = service._active_publications
    original_materialize = ProjectDuplicateService.materialize_candidate_group_projection

    def paused_read(*args, **kwargs):
        result = original_read(*args, **kwargs)
        corpus_read.set()
        assert resume_read.wait(5), "reader was not released"
        return result

    def observe_write(self, *args, **kwargs):
        result = original_materialize(self, *args, **kwargs)
        writer_materialized.set()
        return result

    monkeypatch.setattr(service, "_active_publications", paused_read)
    monkeypatch.setattr(ProjectDuplicateService, "materialize_candidate_group_projection", observe_write)
    with ThreadPoolExecutor(max_workers=2) as executor:
        reader = executor.submit(client.get, "/api/v1/projects/p1/duplicate-groups")
        assert corpus_read.wait(5)
        writer = executor.submit(
            importer.import_bibliographic_publications, "p1", "during-read.ris", "RIS", new_publications,
        )
        try:
            assert writer_materialized.wait(5), "writer did not reach its uncommitted projection"
        finally:
            resume_read.set()
        response = reader.result(timeout=10)
        imported = writer.result(timeout=10)
    assert response.status_code == 200
    assert imported[0].imported_count == 2
    assert response.json() == before
    after = client.get("/api/v1/projects/p1/duplicate-groups").json()
    assert after != before
    assert after["total_groups_count"] == 1
    assert after["readiness"]["pending_review_groups"] == 1
    assert after["readiness"]["screening_ready"] is False
    assert {r["title"] for r in after["groups"][0]["records"]} == {"Concurrent complete candidate"}
