from __future__ import annotations

import sqlite3
from pathlib import Path

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
from app.services.screening_input_service import ScreeningInputService
from app.services.screening_input_service import ScreeningInputReadinessStatus


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
    history = SqliteImportHistoryRepository(db)
    normalization = SqliteNormalizationExecutionRepository(db)
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
    client, _, source, _, _, _ = environment
    _upload(client, "GS01.ris", _ris("Real Shared Title", 2020, "10.1000/real-shared"))
    _upload(client, "GS2.ris", _ris("Real Shared Title", 2021))
    groups = _groups(client)
    assert len(groups) == 1
    assert groups[0]["records_count"] == 2
    assert "conflicting DOI" in groups[0]["reason"]
    records = source.list_source_records("p1")
    assert len(records) == 2
    assert {record.duplicate_candidate_group_id for record in records} == {
        groups[0]["group_id"]
    }


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
