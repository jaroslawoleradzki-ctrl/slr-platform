from __future__ import annotations

import sqlite3
from pathlib import Path
from uuid import uuid4

from app.repositories.import_source_record_repository import (
    ImportSkipAuditRecord,
    ImportSourceRecord,
    SqliteImportSourceRecordRepository,
)
from app.domain.provenance import ProvenanceEntry
from app.domain.publication import Publication
from app.repositories.project_publication_repository import (
    SqliteProjectPublicationRepository,
)


OLD_SOURCE_DDL = """
CREATE TABLE import_source_records (
    source_record_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    import_id TEXT NOT NULL,
    source_filename TEXT,
    source_record_index INTEGER NOT NULL,
    title TEXT NOT NULL,
    publication_year INTEGER,
    original_doi TEXT,
    normalized_doi TEXT,
    authors_json TEXT NOT NULL DEFAULT '[]' CHECK (json_valid(authors_json)),
    document_type TEXT,
    provenance_json TEXT NOT NULL CHECK (json_valid(provenance_json)),
    canonical_publication_id TEXT,
    duplicate_match_type TEXT,
    duplicate_match_reason TEXT,
    duplicate_candidate_group_id TEXT,
    recovery_status TEXT NOT NULL DEFAULT 'not_needed',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (project_id, import_id, source_record_index)
)
"""

OLD_SKIP_DDL = """
CREATE TABLE import_skip_audit (
    skip_audit_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    import_id TEXT NOT NULL,
    source_filename TEXT,
    source_record_index INTEGER NOT NULL,
    source_title TEXT NOT NULL,
    source_doi TEXT,
    matched_publication_id TEXT,
    match_type TEXT NOT NULL,
    match_reason TEXT NOT NULL,
    proposed_action TEXT NOT NULL,
    review_required INTEGER NOT NULL DEFAULT 0 CHECK (review_required IN (0, 1)),
    recovery_status TEXT NOT NULL DEFAULT 'pending_review',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (project_id, import_id, source_record_index)
)
"""


def _seed_project(db: Path) -> None:
    con = sqlite3.connect(db)
    con.execute("INSERT INTO projects(project_id,title) VALUES ('p1','Project')")
    con.execute(
        "INSERT INTO duplicate_review_decisions(project_id,group_id,decision,rationale,updated_at) "
        "VALUES ('p1','g1','APPROVE','keep',CURRENT_TIMESTAMP)"
    )
    con.commit()
    con.close()
    SqliteProjectPublicationRepository(db).add_publications(
        "p1",
        [
            Publication(
                title="Preserved Publication",
                provenance=[ProvenanceEntry(source="OpenAlex", source_record_id="W1")],
            )
        ],
    )


def test_upgrade_from_v072_adds_tables_without_data_loss(tmp_path: Path) -> None:
    db = tmp_path / "v072.db"
    SqliteProjectPublicationRepository(db)
    _seed_project(db)
    con = sqlite3.connect(db)
    for table in (
        "import_source_records",
        "import_skip_audit",
        "import_recovery_approvals",
        "import_recovery_audit",
    ):
        con.execute(f"DROP TABLE IF EXISTS {table}")
    con.execute(
        "DELETE FROM schema_migrations WHERE version LIKE '0034%' OR version LIKE '0035%' OR version LIKE '0036%'"
    )
    before = con.execute("SELECT COUNT(*) FROM project_publications").fetchone()[0]
    con.commit()
    con.close()

    repo = SqliteImportSourceRecordRepository(db)
    con = sqlite3.connect(db)
    assert con.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    assert con.execute("SELECT COUNT(*) FROM project_publications").fetchone()[0] == before
    assert con.execute(
        "SELECT decision FROM duplicate_review_decisions WHERE project_id='p1' AND group_id='g1'"
    ).fetchone()[0] == "APPROVE"
    assert con.execute(
        "SELECT COUNT(*) FROM schema_migrations WHERE version='0036_import_recovery_audit.sql'"
    ).fetchone()[0] == 1
    columns = {row[1] for row in con.execute("PRAGMA table_info(import_source_records)")}
    assert {"source_file_hash", "record_fingerprint", "import_format", "doi_status"} <= columns
    assert {row[1] for row in con.execute("PRAGMA table_info(import_source_records)") if row[5]} == {
        "project_id",
        "source_record_id",
    }
    con.close()

    repo2 = SqliteImportSourceRecordRepository(db)
    assert repo2.list_source_records("p1") == []


def test_upgrade_from_earlier_v073_rebuilds_old_tables_and_preserves_rows(
    tmp_path: Path,
) -> None:
    db = tmp_path / "earlier.db"
    SqliteProjectPublicationRepository(db)
    _seed_project(db)
    import_id = str(uuid4())
    con = sqlite3.connect(db)
    con.execute("DROP TABLE IF EXISTS import_source_records")
    con.execute("DROP TABLE IF EXISTS import_skip_audit")
    con.execute(OLD_SOURCE_DDL)
    con.execute(OLD_SKIP_DDL)
    con.execute(
        """INSERT INTO import_source_records
           (source_record_id, project_id, import_id, source_filename, source_record_index,
            title, original_doi, normalized_doi, provenance_json, recovery_status)
           VALUES ('legacy-source','p1',?,'GS01.ris',1,'Legacy Title','10.1000/legacy',
                   '10.1000/legacy','{"source":"ris"}','imported')""",
        (import_id,),
    )
    con.execute(
        """INSERT INTO import_skip_audit
           (skip_audit_id, project_id, import_id, source_filename, source_record_index,
            source_title, source_doi, match_type, match_reason, proposed_action)
           VALUES ('legacy-skip','p1',?,'GS01.ris',1,'Legacy Title','10.1000/legacy',
                   'exact_doi','duplicate','link')""",
        (import_id,),
    )
    con.execute(
        "INSERT OR IGNORE INTO schema_migrations(version) VALUES ('0034_import_source_records.sql')"
    )
    con.execute(
        "INSERT OR IGNORE INTO schema_migrations(version) VALUES ('0035_import_skip_audit.sql')"
    )
    con.commit()
    con.close()

    repo = SqliteImportSourceRecordRepository(db)
    records = repo.list_source_records("p1")
    assert len(records) == 1
    assert records[0].title == "Legacy Title"
    assert records[0].source_file_hash is None
    assert records[0].doi_status == "valid"
    skips = repo.list_skip_audit("p1")
    assert len(skips) == 1
    assert skips[0].source_record_id is None

    con = sqlite3.connect(db)
    assert con.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    assert {row[1] for row in con.execute("PRAGMA table_info(import_source_records)") if row[5]} == {
        "project_id",
        "source_record_id",
    }
    assert con.execute(
        "SELECT COUNT(*) FROM import_recovery_approvals"
    ).fetchone()[0] == 0
    con.close()


def test_new_rows_round_trip_all_audit_fields(tmp_path: Path) -> None:
    db = tmp_path / "roundtrip.db"
    SqliteProjectPublicationRepository(db)
    _seed_project(db)
    repo = SqliteImportSourceRecordRepository(db)
    import_id = uuid4()
    record = ImportSourceRecord(
        source_record_id="occ-1",
        project_id="p1",
        import_id=import_id,
        source_filename="GS01.ris",
        source_file_hash="file-hash",
        record_fingerprint="record-fingerprint",
        import_format="RIS",
        source_record_index=1,
        title="Round Trip",
        publication_year=2024,
        original_doi="https://doi.org/10.1000/ROUND",
        normalized_doi="10.1000/round",
        doi_status="valid",
        authors=("Smith, A.",),
        document_type="journal_article",
        provenance={"source": "google_scholar_pop"},
        canonical_publication_id="pub-1",
        duplicate_match_type="exact_doi",
        duplicate_match_reason="match",
        recovery_status="linked",
    )
    repo.create_source_record(record)
    loaded = repo.find_source_record_by_id("p1", "occ-1")
    assert loaded is not None
    assert loaded.record_fingerprint == "record-fingerprint"
    assert loaded.import_format == "RIS"
    assert loaded.doi_status == "valid"
    assert loaded.authors == ("Smith, A.",)

    skip = ImportSkipAuditRecord(
        skip_audit_id="skip-1",
        project_id="p1",
        import_id=import_id,
        source_record_id="occ-1",
        source_filename="GS01.ris",
        source_file_hash="file-hash",
        record_fingerprint="record-fingerprint",
        import_format="RIS",
        source_record_index=1,
        source_title="Round Trip",
        source_doi="10.1000/round",
        matched_publication_id="pub-1",
        match_type="exact_doi",
        match_reason="match",
        proposed_action="link",
        review_required=False,
    )
    repo.create_skip_audit(skip)
    loaded_skip = repo.list_skip_audit_for_import("p1", import_id)
    assert len(loaded_skip) == 1
    assert loaded_skip[0].source_record_id == "occ-1"
    assert loaded_skip[0].record_fingerprint == "record-fingerprint"


def test_recovery_approval_is_persistent(tmp_path: Path) -> None:
    db = tmp_path / "approval.db"
    SqliteProjectPublicationRepository(db)
    _seed_project(db)
    repo = SqliteImportSourceRecordRepository(db)
    from datetime import datetime, timezone

    from app.repositories.import_source_record_repository import RecoveryApproval

    approval = RecoveryApproval(
        approval_id=str(uuid4()),
        project_id="p1",
        source_record_id="occ-2",
        reviewer_identity="researcher@example.org",
        decision="approved",
        rationale="Checked against publisher record",
        approved_at=datetime.now(timezone.utc),
    )
    repo.save_recovery_approval(approval)
    loaded = repo.get_recovery_approval("p1", "occ-2")
    assert loaded is not None
    assert loaded.reviewer_identity == "researcher@example.org"
    assert loaded.decision == "approved"
    assert repo.get_recovery_approval("p2", "occ-2") is None
