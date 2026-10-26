import sqlite3
from pathlib import Path

from app.repositories.project_publication_repository import SqliteProjectPublicationRepository
from scripts.ris_import_reconciliation import (
    apply_approved_recovery,
    build_reconciliation_report,
    compute_prisma_reconciliation,
)

RIS_CONTENT = """TY  - JOUR
TI  - Unique Work
DO  - 10.1000/unique
ER  - 

TY  - JOUR
TI  - Ambiguous Work
ER  - 
"""


def _db(tmp_path: Path) -> Path:
    db = tmp_path / "reconcile.db"
    SqliteProjectPublicationRepository(db)
    con = sqlite3.connect(db)
    con.execute("INSERT INTO projects(project_id,title) VALUES ('p1','P1')")
    con.commit()
    con.close()
    return db


def test_reconciliation_report_produces_one_row_per_occurrence(tmp_path: Path) -> None:
    db = _db(tmp_path)
    ris = tmp_path / "GS01.ris"
    ris.write_text(RIS_CONTENT, encoding="utf-8")
    rows = build_reconciliation_report(db, "p1", [ris])
    assert len(rows) == 2
    assert rows[0]["source_record_index"] == 1
    assert rows[0]["classification"] == "confirmed_distinct_publication"
    assert rows[0]["source_file_hash"]
    assert rows[1]["classification"] == "confirmed_distinct_publication"


def test_reconciliation_detects_exact_doi_and_ambiguous_title(tmp_path: Path) -> None:
    db = _db(tmp_path)
    repo = SqliteProjectPublicationRepository(db)
    from app.domain.identifiers import Identifier, IdentifierType
    from app.domain.provenance import ProvenanceEntry
    from app.domain.publication import Publication

    repo.add_publications(
        "p1",
        [
            Publication(
                title="Unique Work",
                identifiers=[Identifier(type=IdentifierType.DOI, value="10.1000/unique")],
                provenance=[ProvenanceEntry(source="ris", source_record_id="10.1000/unique")],
            ),
            Publication(
                title="Ambiguous Work",
                provenance=[ProvenanceEntry(source="ris", source_record_id="Ambiguous Work")],
            ),
        ],
    )
    ris = tmp_path / "GS01.ris"
    ris.write_text(RIS_CONTENT, encoding="utf-8")
    rows = build_reconciliation_report(db, "p1", [ris])
    assert rows[0]["classification"] == "confirmed_exact_doi"
    assert rows[1]["classification"] == "ambiguous_potential_duplicate"
    assert rows[1]["approval_required"] is True


def test_recovery_requires_approval_and_is_idempotent(tmp_path: Path) -> None:
    db = _db(tmp_path)
    ris = tmp_path / "GS01.ris"
    ris.write_text(RIS_CONTENT, encoding="utf-8")
    rows = build_reconciliation_report(db, "p1", [ris])
    approved = {f"{rows[0]['source_file_hash']}:1"}
    first = apply_approved_recovery(db, "p1", rows, approved)
    second = apply_approved_recovery(db, "p1", rows, approved)
    assert first == 1
    assert second == 0


def test_prisma_reconciliation_returns_persisted_counts(tmp_path: Path) -> None:
    db = _db(tmp_path)
    result = compute_prisma_reconciliation(db, "p1")
    assert result["source_records_identified"] == 0
    assert result["active_canonical_publications"] == 0
    assert "canonical_equals_source_minus_duplicates" in result
