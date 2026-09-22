from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from app.domain.author import Author
from app.domain.pre_screening import PreScreeningRemovalReason
from app.domain.project import Project
from app.domain.provenance import ProvenanceEntry
from app.domain.publication import Publication
from app.domain.screening import ScreeningDecision, ScreeningOutcome, ScreeningStage
from app.repositories.corpus_finalization_repository import (
    SqliteCorpusFinalizationRepository,
)
from app.repositories.pre_screening_decision_repository import (
    SqlitePreScreeningDecisionRepository,
)
from app.repositories.project_publication_repository import (
    SqliteProjectPublicationRepository,
)
from app.repositories.project_repository import SqliteProjectRepository
from app.repositories.screening_decision_repository import (
    SqliteScreeningDecisionRepository,
)
from app.services.corpus_finalization_service import (
    CorpusFinalizationService,
)
from app.services.pre_screening_review_service import (
    CorpusFinalizedError,
    PreScreeningReviewService,
    RecordAlreadyScreenedError,
)
from app.services.screening_input_service import ScreeningInputService


def _create_publication(record_id: UUID, title: str) -> Publication:
    return Publication(
        record_id=record_id,
        title=title,
        authors=[Author(display_name="Author A")],
        publication_year=2024,
        provenance=[ProvenanceEntry(source="Crossref", source_record_id=str(record_id))],
        created_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def test_db_path(tmp_path: Path) -> Path:
    db_path = tmp_path / "test_corpus_finalization.db"
    project_repo = SqliteProjectRepository(db_path)
    project_repo.create(Project(project_id="test_p1", title="Test Project"))
    return db_path


def test_corpus_finalization_lifecycle_and_idempotency(test_db_path: Path) -> None:
    pub_repo = SqliteProjectPublicationRepository(test_db_path)
    ps_decision_repo = SqlitePreScreeningDecisionRepository(test_db_path)
    fin_repo = SqliteCorpusFinalizationRepository(test_db_path)
    ps_service = PreScreeningReviewService(pub_repo, ps_decision_repo, fin_repo)
    fin_service = CorpusFinalizationService(fin_repo, pub_repo, ps_decision_repo)

    rec1 = uuid4()
    rec2 = uuid4()
    rec3 = uuid4()
    import_id = uuid4()

    pub_repo.import_source_publications(
        "test_p1",
        [
            _create_publication(rec1, "Retained Paper 1"),
            _create_publication(rec2, "Paper To Remove"),
            _create_publication(rec3, "Retained Paper 2"),
        ],
        import_id=import_id,
    )

    # Remove rec2 during pre-screening review
    ps_service.remove_record(
        "test_p1",
        import_id,
        rec2,
        reason=PreScreeningRemovalReason.RETRIEVAL_ARTEFACT,
        notes="Noise from search",
    )

    # Finalize corpus
    fin1 = fin_service.finalize_corpus("test_p1", finalized_by="reviewer_x")
    assert fin1.source_records_count == 3
    assert fin1.prescreening_removed_count == 1
    assert fin1.retained_count == 2
    assert fin1.duplicates_removed_count == 0

    members = fin_service.get_finalization_members(fin1.finalization_id)
    assert len(members) == 3

    admitted_ids = fin_service.get_admitted_record_ids("test_p1")
    assert admitted_ids == {rec1, rec3}

    # Idempotency check: repeated finalization returns the same event
    fin2 = fin_service.finalize_corpus("test_p1", finalized_by="reviewer_y")
    assert fin2.finalization_id == fin1.finalization_id
    assert fin2.created_at == fin1.created_at

    # Check that pre-screening modifications are locked after finalization
    with pytest.raises(CorpusFinalizedError):
        ps_service.restore_record("test_p1", import_id, rec2)

    with pytest.raises(CorpusFinalizedError):
        ps_service.remove_record(
            "test_p1",
            import_id,
            rec1,
            reason=PreScreeningRemovalReason.CLEARLY_OUTSIDE_SCOPE,
        )


def test_post_finalization_imports_cannot_enter_screening(test_db_path: Path) -> None:
    pub_repo = SqliteProjectPublicationRepository(test_db_path)
    ps_decision_repo = SqlitePreScreeningDecisionRepository(test_db_path)
    fin_repo = SqliteCorpusFinalizationRepository(test_db_path)
    fin_service = CorpusFinalizationService(fin_repo, pub_repo, ps_decision_repo)
    screening_input_service = ScreeningInputService(
        publication_repository=pub_repo,
        finalization_repository=fin_repo,
    )

    rec1 = uuid4()
    rec2 = uuid4()
    import1 = uuid4()

    pub_repo.import_source_publications(
        "test_p1",
        [_create_publication(rec1, "Initial Paper 1"), _create_publication(rec2, "Initial Paper 2")],
        import_id=import1,
    )

    fin = fin_service.finalize_corpus("test_p1")
    assert fin.retained_count == 2

    # Check screening input before new import
    screening_input = screening_input_service.get_input_set("test_p1")
    assert screening_input.ready is True
    assert len(screening_input.publications) == 2
    assert {p.record_id for p in screening_input.publications} == {rec1, rec2}

    # Now a new import arrives after finalization
    rec_late = uuid4()
    import2 = uuid4()
    pub_repo.import_source_publications(
        "test_p1",
        [_create_publication(rec_late, "Late Paper Arriving Post-Finalization")],
        import_id=import2,
    )

    # Verify screening input set remains strictly locked to the 2 admitted members
    updated_screening_input = screening_input_service.get_input_set("test_p1")
    assert len(updated_screening_input.publications) == 2
    assert {p.record_id for p in updated_screening_input.publications} == {rec1, rec2}
    assert rec_late not in {p.record_id for p in updated_screening_input.publications}


def test_pre_screening_modification_rejected_if_already_screened(test_db_path: Path) -> None:
    pub_repo = SqliteProjectPublicationRepository(test_db_path)
    ps_decision_repo = SqlitePreScreeningDecisionRepository(test_db_path)
    screening_decision_repo = SqliteScreeningDecisionRepository(test_db_path)
    # Not finalized yet
    ps_service = PreScreeningReviewService(
        publication_repository=pub_repo,
        decision_repository=ps_decision_repo,
        finalization_repository=None,
        screening_decision_repository=screening_decision_repo,
    )

    rec1 = uuid4()
    import_id = uuid4()
    pub_repo.import_source_publications(
        "test_p1",
        [_create_publication(rec1, "Paper in Screening")],
        import_id=import_id,
    )

    # Record a formal Title/Abstract decision
    decision = ScreeningDecision(
        project_id="test_p1",
        publication_id=rec1,
        stage=ScreeningStage.TITLE_ABSTRACT,
        outcome=ScreeningOutcome.INCLUDE,
        reviewer_id="reviewer_1",
    )
    screening_decision_repo.save(decision)

    # Attempting to pre-screen remove this record must be rejected
    with pytest.raises(RecordAlreadyScreenedError):
        ps_service.remove_record(
            "test_p1",
            import_id,
            rec1,
            reason=PreScreeningRemovalReason.CLEARLY_OUTSIDE_SCOPE,
        )
