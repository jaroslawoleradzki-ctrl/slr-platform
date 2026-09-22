from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.domain.pre_screening import (
    PreScreeningRemovalReason,
    PreScreeningStatus,
)
from app.domain.project import Project
from app.repositories.import_history_repository import SqliteImportHistoryRepository
from app.repositories.pre_screening_decision_repository import (
    SqlitePreScreeningDecisionRepository,
)
from app.repositories.project_publication_repository import (
    SqliteProjectPublicationRepository,
)
from app.repositories.project_repository import SqliteProjectRepository
from app.services.pre_screening_review_service import PreScreeningReviewService
from tests.fixtures.factories import make_author, make_import_history, make_publication


@pytest.fixture
def service_setup(tmp_path: Path):
    db_path = tmp_path / "prescreening.db"
    proj_repo = SqliteProjectRepository(db_path)
    proj_repo.create(Project(project_id="test_project", title="Test Project"))
    pub_repo = SqliteProjectPublicationRepository(db_path)
    decision_repo = SqlitePreScreeningDecisionRepository(db_path)
    history_repo = SqliteImportHistoryRepository(db_path)
    service = PreScreeningReviewService(pub_repo, decision_repo)
    return service, pub_repo, decision_repo, history_repo


def test_list_imported_records_and_counts(service_setup):
    service, pub_repo, decision_repo, history_repo = service_setup
    project_id = "test_project"
    import_id = uuid4()

    # Create import history
    history = make_import_history(
        project_id=project_id,
        import_id=import_id,
        records_count=5,
        source_type="provider",
        status="success",
    )
    history_repo.create(history)

    # Add 5 publications linked to this import
    pubs = [
        make_publication(
            index=i,
            title=f"Machine Learning in Medicine {i}",
            source="crossref",
        )
        for i in range(5)
    ]
    pub_repo.import_source_publications(project_id, pubs, import_id=import_id)

    # Initial counts
    counts = service.get_import_counts(project_id, import_id)
    assert counts == (5, 5, 0)

    # Paginated listing (limit 2, offset 0)
    page_1 = service.list_imported_records(project_id, import_id, limit=2, offset=0)
    assert page_1.total == 5
    assert page_1.limit == 2
    assert page_1.offset == 0
    assert len(page_1.items) == 2
    assert page_1.total_imported == 5
    assert page_1.retained_count == 5
    assert page_1.removed_count == 0

    # Page 2
    page_2 = service.list_imported_records(project_id, import_id, limit=2, offset=2)
    assert len(page_2.items) == 2

    # Page 3
    page_3 = service.list_imported_records(project_id, import_id, limit=2, offset=4)
    assert len(page_3.items) == 1


def test_remove_record_with_reason_and_audit(service_setup):
    service, pub_repo, decision_repo, history_repo = service_setup
    project_id = "test_project"
    import_id = uuid4()

    history = make_import_history(
        project_id=project_id,
        import_id=import_id,
        records_count=2,
    )
    history_repo.create(history)

    p1 = make_publication(index=1, title="Relevant Paper")
    p2 = make_publication(index=2, title="Irrelevant Call For Papers")
    pub_repo.import_source_publications(project_id, [p1, p2], import_id=import_id)

    # Remove p2 with controlled reason
    rec = service.remove_record(
        project_id=project_id,
        import_id=import_id,
        record_id=p2.record_id,
        reason=PreScreeningRemovalReason.RETRIEVAL_ARTEFACT,
        notes="Call for papers notification",
        reviewer_id="reviewer_1",
    )
    assert rec.pre_screening_status == PreScreeningStatus.REMOVED
    assert rec.removal_reason == PreScreeningRemovalReason.RETRIEVAL_ARTEFACT
    assert rec.removal_notes == "Call for papers notification"
    assert rec.reviewer_id == "reviewer_1"

    # Verify counts
    counts = service.get_import_counts(project_id, import_id)
    assert counts == (2, 1, 1)

    # Verify filter by status
    retained_page = service.list_imported_records(
        project_id, import_id, status_filter="retained"
    )
    assert len(retained_page.items) == 1
    assert retained_page.items[0].record_id == p1.record_id

    removed_page = service.list_imported_records(
        project_id, import_id, status_filter="removed"
    )
    assert len(removed_page.items) == 1
    assert removed_page.items[0].record_id == p2.record_id


def test_remove_record_requires_note_for_other_reason(service_setup):
    service, pub_repo, decision_repo, history_repo = service_setup
    project_id = "test_project"
    import_id = uuid4()

    history = make_import_history(project_id=project_id, import_id=import_id)
    history_repo.create(history)

    p1 = make_publication(index=1, title="Paper")
    pub_repo.import_source_publications(project_id, [p1], import_id=import_id)

    # Attempting to remove with 'other' reason and empty notes must fail validation
    with pytest.raises(ValidationError):
        service.remove_record(
            project_id=project_id,
            import_id=import_id,
            record_id=p1.record_id,
            reason=PreScreeningRemovalReason.OTHER,
            notes="",
        )


def test_restore_record_undo(service_setup):
    service, pub_repo, decision_repo, history_repo = service_setup
    project_id = "test_project"
    import_id = uuid4()

    history = make_import_history(project_id=project_id, import_id=import_id)
    history_repo.create(history)

    p1 = make_publication(index=1, title="Paper To Undo")
    pub_repo.import_source_publications(project_id, [p1], import_id=import_id)

    # First remove
    service.remove_record(
        project_id=project_id,
        import_id=import_id,
        record_id=p1.record_id,
        reason=PreScreeningRemovalReason.CLEARLY_OUTSIDE_SCOPE,
        reviewer_id="reviewer_1",
    )
    assert service.get_import_counts(project_id, import_id) == (1, 0, 1)

    # Then restore (Undo)
    restored = service.restore_record(
        project_id=project_id,
        import_id=import_id,
        record_id=p1.record_id,
        reviewer_id="reviewer_2",
    )
    assert restored.pre_screening_status == PreScreeningStatus.RETAINED
    assert restored.reviewer_id is None

    # Verify counts restored
    counts = service.get_import_counts(project_id, import_id)
    assert counts == (1, 1, 0)


def test_search_filtering(service_setup):
    service, pub_repo, decision_repo, history_repo = service_setup
    project_id = "test_project"
    import_id = uuid4()

    history = make_import_history(project_id=project_id, import_id=import_id)
    history_repo.create(history)

    p1 = make_publication(index=1, title="Deep Learning for Cardiology", doi="10.1001/jamacardio.2024")
    p2 = make_publication(index=2, title="Transformer Models in NLP", doi="10.1145/transformer")
    p2 = p2.model_copy(update={"authors": [make_author("Vaswani, Ashish")]})
    p3 = make_publication(index=3, title="Systematic Review Methodology", doi="10.1002/cochrane")

    pub_repo.import_source_publications(project_id, [p1, p2, p3], import_id=import_id)

    # Search by title keyword
    search_cardio = service.list_imported_records(
        project_id, import_id, search="Cardiology"
    )
    assert search_cardio.total == 1
    assert search_cardio.items[0].record_id == p1.record_id

    # Search by author keyword
    search_author = service.list_imported_records(
        project_id, import_id, search="Vaswani"
    )
    assert search_author.total == 1
    assert search_author.items[0].record_id == p2.record_id

    # Search by DOI
    search_doi = service.list_imported_records(
        project_id, import_id, search="10.1002"
    )
    assert search_doi.total == 1
    assert search_doi.items[0].record_id == p3.record_id
