import sqlite3
from pathlib import Path

from app.domain.identifiers import Identifier, IdentifierType
from app.domain.provenance import ProvenanceEntry
from app.domain.publication import Publication
from app.repositories.import_history_repository import SqliteImportHistoryRepository
from app.repositories.import_source_record_repository import SqliteImportSourceRecordRepository
from app.repositories.normalization_execution_repository import SqliteNormalizationExecutionRepository
from app.repositories.project_publication_repository import SqliteProjectPublicationRepository
from app.repositories.transaction_manager import SqliteTransactionManager
from app.services.project_import_service import ProjectImportService


def _service(tmp_path: Path):
    db = tmp_path / "v073.db"
    pub = SqliteProjectPublicationRepository(db)
    hist = SqliteImportHistoryRepository(db)
    norm = SqliteNormalizationExecutionRepository(db)
    tx = SqliteTransactionManager(db)
    src = SqliteImportSourceRecordRepository(db)
    service = ProjectImportService(pub, hist, norm, tx, source_record_repository=src)
    con = sqlite3.connect(db)
    con.execute("INSERT INTO projects(project_id,title) VALUES ('p1','P1')")
    con.execute("INSERT INTO projects(project_id,title) VALUES ('p2','P2')")
    con.commit()
    con.close()
    return service, pub, src, db


def _pub(title: str, doi: str | None = None) -> Publication:
    identifiers = [Identifier(type=IdentifierType.DOI, value=doi)] if doi else []
    return Publication(
        title=title,
        identifiers=identifiers,
        provenance=[ProvenanceEntry(source="ris", source_record_id=doi or title)],
    )


def test_same_doi_imports_independently_in_two_projects(tmp_path: Path) -> None:
    service, pub, src, _ = _service(tmp_path)
    publication = _pub("Same DOI", "10.1000/same")
    first, _ = service.import_bibliographic_publications("p1", "a.ris", "RIS", [publication], source_file_hash="hash-a")
    second, _ = service.import_bibliographic_publications("p2", "a.ris", "RIS", [publication], source_file_hash="hash-a")
    assert first.imported_count == 1
    assert second.imported_count == 1
    assert len(src.list_source_records("p1")) == 1
    assert len(src.list_source_records("p2")) == 1
    assert len(pub.get_publications("p1")) == 1
    assert len(pub.get_publications("p2")) == 1


def test_repeated_identical_file_is_idempotent(tmp_path: Path) -> None:
    service, pub, src, _ = _service(tmp_path)
    publication = _pub("Repeat", "10.1000/repeat")
    first, _ = service.import_bibliographic_publications("p1", "a.ris", "RIS", [publication], source_file_hash="hash-a")
    second, history = service.import_bibliographic_publications("p1", "a.ris", "RIS", [publication], source_file_hash="hash-a")
    assert first.imported_count == 1
    assert second.imported_count == 0
    assert len(pub.get_publications("p1")) == 1
    assert len(src.list_source_records("p1")) == 1
    assert any("repeated source occurrence" in warning for warning in history.warnings)


def test_title_without_doi_is_preserved_and_flagged(tmp_path: Path) -> None:
    service, pub, src, _ = _service(tmp_path)
    publication_a = _pub("Identical Title")
    publication_b = _pub("Identical Title")
    service.import_bibliographic_publications("p1", "a.ris", "RIS", [publication_a], source_file_hash="hash-a")
    result, history = service.import_bibliographic_publications(
        "p1", "b.ris", "RIS", [publication_b], source_file_hash="hash-b"
    )
    assert result.imported_count == 1
    assert len(pub.get_publications("p1")) == 2
    records = src.list_source_records("p1")
    assert any(record.duplicate_match_type == "title_candidate" for record in records)
    assert any("title-only candidate" in warning for warning in history.warnings)


def test_malformed_doi_does_not_match_valid_doi(tmp_path: Path) -> None:
    service, pub, _, _ = _service(tmp_path)
    service.import_bibliographic_publications(
        "p1", "a.ris", "RIS", [_pub("Valid", "10.1000/valid")], source_file_hash="hash-a"
    )
    malformed = Publication(
        title="Malformed",
        provenance=[ProvenanceEntry(source="ris", source_record_id="not-a-doi")],
    )
    result, _ = service.import_bibliographic_publications(
        "p1", "b.ris", "RIS", [malformed], source_file_hash="hash-b"
    )
    assert result.imported_count == 1
    assert len(pub.get_publications("p1")) == 2


def test_source_record_links_to_canonical_publication(tmp_path: Path) -> None:
    service, _, src, _ = _service(tmp_path)
    service.import_bibliographic_publications(
        "p1", "a.ris", "RIS", [_pub("Linked", "10.1000/linked")], source_file_hash="hash-a"
    )
    record = src.list_source_records("p1")[0]
    assert record.canonical_publication_id is not None
    assert record.source_file_hash == "hash-a"
    assert record.source_record_index == 1
