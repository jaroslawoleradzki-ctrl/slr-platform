from __future__ import annotations

import json
import shutil
import sqlite3
from pathlib import Path

import pytest

from app.domain.author import Author
from app.domain.identifiers import Identifier, IdentifierType
from app.domain.provenance import ProvenanceEntry
from app.domain.publication import Publication
from app.repositories.import_source_record_repository import (
    SqliteImportSourceRecordRepository,
)
from app.repositories.project_publication_repository import (
    ProjectNotFoundError,
    SqliteProjectPublicationRepository,
)
from scripts.ris_import_reconciliation import (
    build_reconciliation_report,
    compute_prisma_reconciliation,
    execute_approved_recovery,
    record_recovery_approvals,
)

RIS_CONTENT = """TY  - JOUR
TI  - Exact Work
PY  - 2020
DO  - 10.1000/exact
ER  - 

TY  - JOUR
TI  - Verified Work
PY  - 2020
AU  - Smith, A.
ER  - 

TY  - JOUR
TI  - Ambiguous Work
PY  - 2021
AU  - New, B.
ER  - 

TY  - JOUR
TI  - Distinct New Work
PY  - 2022
AU  - Jones, C.
ER  - 

TY  - JOUR
DO  - 10.1000/no-title
ER  - 
"""


@pytest.fixture
def environment(tmp_path: Path):
    db = tmp_path / "recovery.db"
    repo = SqliteProjectPublicationRepository(db)
    con = sqlite3.connect(db)
    con.execute("INSERT INTO projects(project_id,title) VALUES ('p1','Project 1')")
    con.execute("INSERT INTO projects(project_id,title) VALUES ('p2','Project 2')")
    con.execute(
        "INSERT INTO duplicate_review_decisions(project_id,group_id,decision,rationale,updated_at) "
        "VALUES ('p1','existing-group','APPROVE','preserve me',CURRENT_TIMESTAMP)"
    )
    con.commit()
    con.close()
    repo.add_publications(
        "p1",
        [
            Publication(
                title="Exact Work",
                publication_year=2020,
                identifiers=[Identifier(type=IdentifierType.DOI, value="10.1000/exact")],
                provenance=[ProvenanceEntry(source="Crossref", source_record_id="10.1000/exact")],
            ),
            Publication(
                title="Verified Work",
                publication_year=2020,
                authors=[Author(display_name="Smith, A.")],
                provenance=[ProvenanceEntry(source="OpenAlex", source_record_id="W2")],
            ),
            Publication(
                title="Ambiguous Work",
                publication_year=2019,
                authors=[Author(display_name="Old, Z.")],
                provenance=[ProvenanceEntry(source="OpenAlex", source_record_id="W3")],
            ),
        ],
    )
    ris = tmp_path / "GS01.ris"
    ris.write_text(RIS_CONTENT, encoding="utf-8")
    report = build_reconciliation_report(db, "p1", [ris])
    backup = tmp_path / "backup.db"
    shutil.copy2(db, backup)
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps({"files": [{"filename": "GS01.ris", "count": len(report)}], "total": len(report)}),
        encoding="utf-8",
    )
    return {
        "db": db,
        "repo": repo,
        "ris": ris,
        "report": report,
        "backup": backup,
        "manifest": manifest,
        "root": tmp_path,
    }


def _approve(env, rows, *, decision="approved", reviewer="researcher@example.org"):
    return record_recovery_approvals(
        env["db"],
        "p1",
        [row["source_record_id"] for row in rows],
        reviewer_identity=reviewer,
        decision=decision,
        rationale="Checked against publisher evidence",
        allowed_source_ids={row["source_record_id"] for row in env["report"]},
    )


def _execute(env, report=None):
    return execute_approved_recovery(
        env["db"],
        "p1",
        report or env["report"],
        backup_path=env["backup"],
        manifest_path=env["manifest"],
        confirmation="RECOVER",
    )


def test_report_contains_all_five_classifications_without_aborting(environment) -> None:
    classifications = {row["classification"] for row in environment["report"]}
    assert classifications == {
        "confirmed_exact_doi",
        "confirmed_duplicate_verified",
        "ambiguous_potential_duplicate",
        "confirmed_distinct_publication",
        "insufficient_evidence",
    }
    assert len(environment["report"]) == 5
    assert all(row["source_record_id"] for row in environment["report"])
    malformed = [row for row in environment["report"] if row["validation_error"]]
    assert len(malformed) == 1
    assert malformed[0]["classification"] == "insufficient_evidence"


def test_historical_status_distinguishes_imported_and_skipped(environment) -> None:
    rows = {row["original_title"]: row for row in environment["report"]}
    assert rows["Exact Work"]["historical_status"] == "imported"
    assert rows["Verified Work"]["historical_status"] == "imported"
    assert rows["Ambiguous Work"]["historical_status"] == "imported"
    assert rows["Distinct New Work"]["historical_status"] == "skipped"
    assert rows["Distinct New Work"]["historical_evidence"] == "inferred_missing_from_corpus"


def test_approval_is_persistent_and_unknown_source_is_rejected(environment) -> None:
    distinct = [
        row for row in environment["report"] if row["classification"] == "confirmed_distinct_publication"
    ]
    _approve(environment, distinct)
    repo = SqliteImportSourceRecordRepository(environment["db"])
    approvals = repo.list_recovery_approvals("p1")
    assert len(approvals) == 1
    assert approvals[0].reviewer_identity == "researcher@example.org"
    assert approvals[0].decision == "approved"
    with pytest.raises(ValueError):
        record_recovery_approvals(
            environment["db"],
            "p1",
            ["forged-source-id"],
            reviewer_identity="researcher@example.org",
            decision="approved",
            rationale="forged",
            allowed_source_ids={row["source_record_id"] for row in environment["report"]},
        )
    with pytest.raises(ProjectNotFoundError):
        record_recovery_approvals(
            environment["db"],
            "ghost",
            ["forged-source-id"],
            reviewer_identity="researcher@example.org",
            decision="approved",
            rationale="forged",
        )


def test_recovery_requires_confirmation_backup_and_manifest(environment) -> None:
    distinct = [
        row for row in environment["report"] if row["classification"] == "confirmed_distinct_publication"
    ]
    _approve(environment, distinct)
    with pytest.raises(ValueError, match="confirmation"):
        execute_approved_recovery(
            environment["db"],
            "p1",
            environment["report"],
            backup_path=environment["backup"],
            manifest_path=environment["manifest"],
            confirmation="yes",
        )
    with pytest.raises(ValueError, match="backup"):
        execute_approved_recovery(
            environment["db"],
            "p1",
            environment["report"],
            backup_path=environment["root"] / "missing.db",
            manifest_path=environment["manifest"],
            confirmation="RECOVER",
        )


def test_recovery_writes_valid_readable_publication_and_audit(environment) -> None:
    distinct = [
        row for row in environment["report"] if row["classification"] == "confirmed_distinct_publication"
    ]
    _approve(environment, distinct)
    result = _execute(environment)
    assert result.recovered_count == 1

    publications = environment["repo"].get_publications("p1")
    recovered = [item for item in publications if item.title == "Distinct New Work"]
    assert len(recovered) == 1
    assert recovered[0].publication_year == 2022
    assert recovered[0].authors[0].display_name == "Jones, C."

    source_repo = SqliteImportSourceRecordRepository(environment["db"])
    linked = [
        item for item in source_repo.list_source_records("p1") if item.recovery_status == "recovered"
    ]
    assert len(linked) == 1
    assert linked[0].canonical_publication_id == str(recovered[0].record_id)
    approvals = source_repo.list_recovery_approvals("p1")
    assert approvals[0].recovery_executed_at is not None
    assert approvals[0].recovery_outcome == "recovered"

    con = sqlite3.connect(environment["db"])
    audit_rows = con.execute("SELECT outcome FROM import_recovery_audit WHERE project_id='p1'").fetchall()
    decision = con.execute(
        "SELECT decision FROM duplicate_review_decisions WHERE project_id='p1' AND group_id='existing-group'"
    ).fetchone()
    con.close()
    assert audit_rows == [("recovered",)]
    assert decision == ("APPROVE",)

    # Idempotent re-execution after a new backup/manifest is not needed: the
    # persisted execution state short-circuits before writes.
    again = _execute(environment)
    assert again.recovered_count == 0
    assert again.skipped_count == 1


def test_ambiguous_and_rejected_rows_are_not_recovered(environment) -> None:
    ambiguous = [
        row
        for row in environment["report"]
        if row["classification"] == "ambiguous_potential_duplicate"
    ]
    _approve(environment, ambiguous, decision="approved")
    result = _execute(environment)
    assert result.recovered_count == 0
    assert not any(
        item.title == "Ambiguous Work" and item.publication_year == 2021
        for item in environment["repo"].get_publications("p1")
    )

    distinct = [
        row for row in environment["report"] if row["classification"] == "confirmed_distinct_publication"
    ]
    _approve(environment, distinct, decision="rejected")
    result = _execute(environment)
    assert result.recovered_count == 0


def test_duplicate_doi_recovery_is_rejected_before_writes(environment) -> None:
    synthetic = [
        {
            "source_file": "GS01.ris",
            "source_file_hash": "same-file",
            "source_database": "google_scholar_pop",
            "source_record_id": "synthetic-1",
            "source_record_index": 1,
            "record_fingerprint": "fp1",
            "original_title": "Duplicate DOI One",
            "original_doi": "10.1000/recover-duplicate",
            "normalized_doi": "10.1000/recover-duplicate",
            "doi_status": "valid",
            "authors": [],
            "publication_year": 2020,
            "document_type": "journal_article",
            "abstract": None,
            "classification": "confirmed_distinct_publication",
        },
        {
            "source_file": "GS01.ris",
            "source_file_hash": "same-file",
            "source_database": "google_scholar_pop",
            "source_record_id": "synthetic-2",
            "source_record_index": 2,
            "record_fingerprint": "fp2",
            "original_title": "Duplicate DOI Two",
            "original_doi": "10.1000/recover-duplicate",
            "normalized_doi": "10.1000/recover-duplicate",
            "doi_status": "valid",
            "authors": [],
            "publication_year": 2020,
            "document_type": "journal_article",
            "abstract": None,
            "classification": "confirmed_distinct_publication",
        },
    ]
    manifest = environment["root"] / "synthetic-manifest.json"
    manifest.write_text(
        json.dumps({"files": [{"filename": "GS01.ris", "count": 2}], "total": 2}),
        encoding="utf-8",
    )
    record_recovery_approvals(
        environment["db"],
        "p1",
        [row["source_record_id"] for row in synthetic],
        reviewer_identity="researcher@example.org",
        decision="approved",
        rationale="synthetic",
        allowed_source_ids={row["source_record_id"] for row in synthetic},
    )
    with pytest.raises(ValueError, match="duplicate DOI"):
        execute_approved_recovery(
            environment["db"],
            "p1",
            synthetic,
            backup_path=environment["backup"],
            manifest_path=manifest,
            confirmation="RECOVER",
        )
    assert not any(
        item.title in {"Duplicate DOI One", "Duplicate DOI Two"}
        for item in environment["repo"].get_publications("p1")
    )


def test_transaction_rolls_back_on_mid_batch_failure(environment) -> None:
    synthetic = [
        {
            "source_file": "GS01.ris",
            "source_file_hash": "same-file",
            "source_database": "google_scholar_pop",
            "source_record_id": "rollback-1",
            "source_record_index": 1,
            "record_fingerprint": "fp1",
            "original_title": "Rollback First",
            "original_doi": None,
            "normalized_doi": None,
            "doi_status": "missing",
            "authors": [],
            "publication_year": 2020,
            "document_type": None,
            "abstract": None,
            "classification": "confirmed_distinct_publication",
        },
        {
            "source_file": "GS01.ris",
            "source_file_hash": "same-file",
            "source_database": "google_scholar_pop",
            "source_record_id": "rollback-2",
            "source_record_index": 2,
            "record_fingerprint": "fp2",
            "original_title": None,
            "original_doi": None,
            "normalized_doi": None,
            "doi_status": "missing",
            "authors": [],
            "publication_year": 2020,
            "document_type": None,
            "abstract": None,
            "classification": "confirmed_distinct_publication",
        },
    ]
    manifest = environment["root"] / "rollback-manifest.json"
    manifest.write_text(
        json.dumps({"files": [{"filename": "GS01.ris", "count": 2}], "total": 2}),
        encoding="utf-8",
    )
    record_recovery_approvals(
        environment["db"],
        "p1",
        [row["source_record_id"] for row in synthetic],
        reviewer_identity="researcher@example.org",
        decision="approved",
        rationale="synthetic",
        allowed_source_ids={row["source_record_id"] for row in synthetic},
    )
    with pytest.raises(Exception):
        execute_approved_recovery(
            environment["db"],
            "p1",
            synthetic,
            backup_path=environment["backup"],
            manifest_path=manifest,
            confirmation="RECOVER",
        )
    assert not any(
        item.title == "Rollback First" for item in environment["repo"].get_publications("p1")
    )
    source_repo = SqliteImportSourceRecordRepository(environment["db"])
    approvals = source_repo.list_recovery_approvals("p1")
    assert all(item.recovery_executed_at is None for item in approvals)


def test_recovery_is_project_scoped(environment) -> None:
    distinct = [
        row for row in environment["report"] if row["classification"] == "confirmed_distinct_publication"
    ]
    _approve(environment, distinct)
    _execute(environment)
    assert environment["repo"].get_publications("p2") == []


def test_prisma_reconciliation_reports_recovered_source_state(environment) -> None:
    distinct = [
        row for row in environment["report"] if row["classification"] == "confirmed_distinct_publication"
    ]
    _approve(environment, distinct)
    _execute(environment)
    result = compute_prisma_reconciliation(environment["db"], "p1")
    assert result["recovered_records"] == 1
    assert result["persisted_source_records"] == 1
    assert result["active_canonical_publications"] >= 4
