from pathlib import Path

from app.domain.provenance import ProvenanceEntry
from app.domain.publication import Publication
from app.repositories.duplicate_merge_repository import SqliteDuplicateMergeRepository
from app.repositories.duplicate_review_decision_repository import SqliteDuplicateReviewDecisionRepository
from app.repositories.import_history_repository import SqliteImportHistoryRepository
from app.repositories.import_source_record_repository import SqliteImportSourceRecordRepository
from app.repositories.normalization_execution_repository import SqliteNormalizationExecutionRepository
from app.repositories.project_publication_repository import SqliteProjectPublicationRepository
from app.repositories.transaction_manager import SqliteTransactionManager
from app.services.project_duplicate_service import ProjectDuplicateService
from app.services.project_import_service import ProjectImportService


def _pub(title: str) -> Publication:
    return Publication(
        title=title,
        provenance=[ProvenanceEntry(source="ris", source_record_id=title)],
    )


def test_title_only_candidates_enter_manual_duplicate_review(tmp_path: Path) -> None:
    db = tmp_path / "candidate.db"
    pub = SqliteProjectPublicationRepository(db)
    hist = SqliteImportHistoryRepository(db)
    norm = SqliteNormalizationExecutionRepository(db)
    tx = SqliteTransactionManager(db)
    src = SqliteImportSourceRecordRepository(db)
    service = ProjectImportService(pub, hist, norm, tx, source_record_repository=src)
    import sqlite3
    con = sqlite3.connect(db)
    con.execute("INSERT INTO projects(project_id,title) VALUES ('p1','P1')")
    con.commit()
    con.close()
    service.import_bibliographic_publications("p1", "a.ris", "RIS", [_pub("Candidate Title")], source_file_hash="hash-a")
    service.import_bibliographic_publications("p1", "b.ris", "RIS", [_pub("Candidate Title")], source_file_hash="hash-b")
    duplicate_service = ProjectDuplicateService(
        pub,
        SqliteDuplicateReviewDecisionRepository(db),
        merge_repository=SqliteDuplicateMergeRepository(db),
        transaction_manager=SqliteTransactionManager(db),
    )
    groups = duplicate_service.get_candidate_duplicate_groups("p1").groups
    assert any(group.records_count == 2 for group in groups)
