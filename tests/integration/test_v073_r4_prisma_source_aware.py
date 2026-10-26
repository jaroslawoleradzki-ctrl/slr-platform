from __future__ import annotations

import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.api.main import app
from app.api.routers.deduplication import get_duplicate_service
from app.api.routers.projects import get_prisma_metrics_service
from app.domain.project import Project
from app.domain.provenance import ProvenanceEntry
from app.domain.publication import Publication
from app.repositories.duplicate_merge_repository import SqliteDuplicateMergeRepository
from app.repositories.duplicate_review_decision_repository import (
    SqliteDuplicateReviewDecisionRepository,
)
from app.repositories.import_history_repository import (
    ImportHistoryRecord,
    SqliteImportHistoryRepository,
)
from app.repositories.import_source_record_repository import (
    SqliteImportSourceRecordRepository,
)
from app.repositories.normalization_execution_repository import (
    SqliteNormalizationExecutionRepository,
)
from app.repositories.pre_screening_archive_repository import (
    SqlitePreScreeningArchiveRepository,
)
from app.repositories.project_publication_repository import (
    SqliteProjectPublicationRepository,
)
from app.repositories.project_repository import SqliteProjectRepository
from app.repositories.transaction_manager import SqliteTransactionManager
from app.services.duplicate_group_builder import DuplicateGroupBuilder
from app.services.export.prisma_flow_builder import build_flow_model
from app.services.prisma_metrics_service import PrismaMetricsService
from app.services.project_duplicate_service import ProjectDuplicateService


def _ris(title: str, year: int | None = None, doi: str | None = None) -> str:
    lines = ["TY  - JOUR", f"TI  - {title}"]
    if year is not None:
        lines.append(f"PY  - {year}")
    if doi is not None:
        lines.append(f"DO  - {doi}")
    lines.append("ER  - ")
    return "\n".join(lines) + "\n"


class WorkflowStub:
    def get_status(self, project_id: str, reviewer_id: str = "default"):
        return SimpleNamespace(
            title_abstract_screening=SimpleNamespace(evaluated_count=3),
            full_text_screening=SimpleNamespace(evaluated_count=2),
            quality_assessment=SimpleNamespace(eligible_count=1),
        )

    def get_excluded_counts(self, project_id: str, reviewer_id: str = "default"):
        return (1, 1)


@pytest.fixture
def environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db = tmp_path / "v073_r4.db"
    monkeypatch.setenv("SLR_DATABASE_PATH", str(db))
    project_repo = SqliteProjectRepository(db)
    pub = SqliteProjectPublicationRepository(db)
    history = SqliteImportHistoryRepository(db)
    normalization = SqliteNormalizationExecutionRepository(db)
    source = SqliteImportSourceRecordRepository(db)
    decisions = SqliteDuplicateReviewDecisionRepository(db)
    merges = SqliteDuplicateMergeRepository(db)
    archive = SqlitePreScreeningArchiveRepository(db)
    project_repo.create(Project(project_id="p1", title="Project 1"))
    con = sqlite3.connect(db)
    con.execute("INSERT INTO projects(project_id,title) VALUES ('p2','Project 2')")
    con.commit()
    con.close()
    service = PrismaMetricsService(
        publication_repository=pub,
        import_history_repository=history,
        decision_repository=decisions,
        workflow_status_service=WorkflowStub(),
        builder=DuplicateGroupBuilder(),
        archive_repository=archive,
        source_record_repository=source,
        merge_repository=merges,
    )
    duplicate_service = ProjectDuplicateService(
        pub,
        decisions,
        merge_repository=merges,
        transaction_manager=SqliteTransactionManager(db),
        source_record_repository=source,
    )
    app.dependency_overrides[get_prisma_metrics_service] = lambda: service
    app.dependency_overrides[get_duplicate_service] = lambda: duplicate_service
    client = TestClient(app)
    yield {
        "client": client,
        "pub": pub,
        "history": history,
        "source": source,
        "decisions": decisions,
        "merges": merges,
        "service": service,
        "db": db,
    }
    app.dependency_overrides.clear()


def _upload(client: TestClient, filename: str, content: str):
    response = client.post(
        "/api/v1/projects/p1/imports",
        files={"file": (filename, content, "application/x-research-info-systems")},
        data={"source_database": "google_scholar_pop"},
    )
    assert response.status_code == 201, response.text
    return response


def test_prisma_counts_source_records_duplicates_and_title_candidates(environment) -> None:
    client = environment["client"]
    _upload(client, "GS01.ris", _ris("Source New", 2020, "10.1000/new"))
    _upload(client, "GS2.ris", _ris("Source New Again", 2021, "10.1000/new"))
    _upload(client, "GS3.ris", _ris("Title Candidate", 2020))
    _upload(client, "GS4.ris", _ris("Title Candidate", 2021))
    _upload(client, "GS5.ris", _ris("Repeated File", 2020))
    _upload(client, "GS5.ris", _ris("Repeated File", 2020))

    body = client.get("/api/v1/projects/p1/prisma/metrics").json()
    assert body["persisted_source_records"] == 5
    assert body["source_records_identified"] == 6
    assert body["records_identified_imports"] == 6
    assert body["exact_duplicates_linked"] == 1
    assert body["repeated_source_occurrences"] == 1
    assert body["total_identified"] == 6
    assert body["canonical_publications"] == 4
    assert body["duplicate_groups_pending_review"] == 1
    assert body["historical_canonical_without_source_records"] == 0

    metrics = environment["service"].get_metrics("p1")
    flow = build_flow_model(metrics)
    assert flow.metadata.counts_echo["source_records_identified"] == 6
    assert flow.metadata.counts_echo["exact_duplicates_linked"] == 1
    assert flow.metadata.counts_echo["repeated_source_occurrences"] == 1
    assert flow.removed["duplicates_removed"] == 2


def test_prisma_reflects_merged_duplicate_groups(environment) -> None:
    client = environment["client"]
    _upload(client, "GS01.ris", _ris("Merge Candidate", 2020))
    _upload(client, "GS2.ris", _ris("Merge Candidate", 2021))
    group = client.get("/api/v1/projects/p1/duplicate-groups").json()["groups"][0]
    client.post(
        f"/api/v1/projects/p1/duplicate-groups/{group['group_id']}/decision",
        json={"decision": "APPROVE", "rationale": "same"},
    )
    merge = client.post(
        f"/api/v1/projects/p1/duplicate-groups/{group['group_id']}/merge",
        json={"rationale": "merge"},
    )
    assert merge.status_code == 200
    body = client.get("/api/v1/projects/p1/prisma/metrics").json()
    assert body["merged_duplicate_groups"] == 1
    assert body["merged_duplicate_records"] == 1
    assert body["canonical_publications"] == 1


def test_prisma_historical_project_falls_back_transparently(environment) -> None:
    history = environment["history"]
    pub = environment["pub"]
    history.create(
        ImportHistoryRecord(
            import_id=__import__("uuid").uuid4(),
            project_id="p2",
            source_type="file",
            filename="legacy.ris",
            format="RIS",
            provider=None,
            query=None,
            records_count=7,
            total_available=None,
            status="success",
            warnings=(),
            created_at=__import__("datetime").datetime.now(
                __import__("datetime").timezone.utc
            ),
            fingerprint=None,
            source_database="google_scholar_pop",
        )
    )
    pub.add_publications(
        "p2",
        [
            Publication(
                title=f"Historical {index}",
                provenance=[ProvenanceEntry(source="google_scholar_pop", source_record_id=str(index))],
            )
            for index in range(7)
        ],
    )
    body = environment["client"].get("/api/v1/projects/p2/prisma/metrics").json()
    assert body["records_identified_imports"] == 7
    assert body["total_identified"] == 7
    assert body["persisted_source_records"] == 0
    assert body["historical_canonical_without_source_records"] == 7
    assert "Historical project" in body["prisma_accounting_note"]


def test_prisma_counts_recovered_records(environment) -> None:
    import json
    import shutil

    from scripts.ris_import_reconciliation import (
        build_reconciliation_report,
        execute_approved_recovery,
        record_recovery_approvals,
    )

    db = environment["db"]
    ris = environment["db"].parent / "GS01.ris"
    ris.write_text(_ris("Recovered PRISMA Record", 2020), encoding="utf-8")
    report = build_reconciliation_report(db, "p1", [ris])
    distinct = [
        row for row in report if row["classification"] == "confirmed_distinct_publication"
    ]
    record_recovery_approvals(
        db,
        "p1",
        [row["source_record_id"] for row in distinct],
        reviewer_identity="researcher@example.org",
        decision="approved",
        rationale="checked",
        allowed_source_ids={row["source_record_id"] for row in report},
    )
    backup = environment["db"].parent / "r4-backup.db"
    shutil.copy2(db, backup)
    manifest = environment["db"].parent / "r4-manifest.json"
    manifest.write_text(
        json.dumps({"files": [{"filename": "GS01.ris", "count": 1}], "total": 1}),
        encoding="utf-8",
    )
    result = execute_approved_recovery(
        db,
        "p1",
        report,
        backup_path=backup,
        manifest_path=manifest,
        confirmation="RECOVER",
    )
    assert result.recovered_count == 1
    body = environment["client"].get("/api/v1/projects/p1/prisma/metrics").json()
    assert body["recovered_records"] == 1
    assert body["canonical_publications"] == 1
    assert body["source_records_identified"] == 1


def test_prisma_export_and_api_agree(environment) -> None:
    client = environment["client"]
    _upload(client, "GS01.ris", _ris("Export Agreement", 2020, "10.1000/export"))
    _upload(client, "GS2.ris", _ris("Export Agreement", 2021))
    body = client.get("/api/v1/projects/p1/prisma/metrics").json()
    metrics = environment["service"].get_metrics("p1")
    flow = build_flow_model(metrics)
    for field in (
        "total_identified",
        "source_records_identified",
        "exact_duplicates_linked",
        "repeated_source_occurrences",
        "canonical_publications",
        "merged_duplicate_records",
        "recovered_records",
        "historical_canonical_without_source_records",
    ):
        assert flow.metadata.counts_echo[field] == body[field]
