from pathlib import Path
from uuid import uuid4

import pytest

from app.domain.identifiers import Identifier, IdentifierType
from app.domain.pre_screening import (
    PreScreeningRemovalReason,
)
from app.domain.project import Project
from app.repositories.import_history_repository import SqliteImportHistoryRepository
from app.repositories.pre_screening_archive_repository import (
    SqlitePreScreeningArchiveRepository,
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
from app.services.active_publication_filter import (
    count_active_project_publications,
    get_active_project_publications,
)
from app.services.pre_screening_review_service import (
    PreScreeningRecordNotFoundError,
    PreScreeningReviewService,
)
from tests.fixtures.factories import make_publication


@pytest.fixture
def invariant_setup(tmp_path: Path):
    db_path = tmp_path / "invariants.db"
    proj_repo = SqliteProjectRepository(db_path)
    proj_repo.create(Project(project_id="proj_1", title="Project 1"))
    proj_repo.create(Project(project_id="proj_2", title="Project 2"))

    pub_repo = SqliteProjectPublicationRepository(db_path)
    decision_repo = SqlitePreScreeningDecisionRepository(db_path)
    archive_repo = SqlitePreScreeningArchiveRepository(db_path)
    history_repo = SqliteImportHistoryRepository(db_path)
    screening_decision_repo = SqliteScreeningDecisionRepository(db_path)

    service = PreScreeningReviewService(
        publication_repository=pub_repo,
        decision_repository=decision_repo,
        archive_repository=archive_repo,
        screening_decision_repository=screening_decision_repo,
    )

    return {
        "db_path": db_path,
        "service": service,
        "pub_repo": pub_repo,
        "decision_repo": decision_repo,
        "archive_repo": archive_repo,
        "history_repo": history_repo,
        "screening_decision_repo": screening_decision_repo,
    }


def test_invariant_a_retained_publication_appears_in_active_corpus(invariant_setup):
    """Invariant A: retained publication appears in active corpus."""
    pub_repo = invariant_setup["pub_repo"]
    project_id = "proj_1"

    pub = make_publication(index=1, title="Retained Study", source="crossref")
    pub_repo.import_source_publications(project_id, [pub])

    active = get_active_project_publications(project_id, repository=pub_repo)
    assert len(active) == 1
    assert active[0].record_id == pub.record_id
    assert count_active_project_publications(project_id, repository=pub_repo) == 1


def test_invariant_b_prescreening_removed_does_not_appear_in_active_corpus(invariant_setup):
    """Invariant B: pre-screening removed publication does NOT appear in active corpus."""
    pub_repo = invariant_setup["pub_repo"]
    service = invariant_setup["service"]
    project_id = "proj_1"
    import_id = uuid4()

    p_retained = make_publication(index=1, title="Valid Study")
    p_removed = make_publication(index=2, title="Editorial Artefact")
    pub_repo.import_source_publications(project_id, [p_retained, p_removed], import_id=import_id)

    # Mark p_removed as removed in legacy/in-place mode
    service.remove_record(
        project_id=project_id,
        import_id=import_id,
        record_id=p_removed.record_id,
        reason=PreScreeningRemovalReason.RETRIEVAL_ARTEFACT,
    )

    active = get_active_project_publications(project_id, repository=pub_repo)
    assert len(active) == 1
    assert active[0].record_id == p_retained.record_id
    assert count_active_project_publications(project_id, repository=pub_repo) == 1


def test_invariant_c_archived_publication_does_not_appear_in_active_corpus(invariant_setup):
    """Invariant C: archived publication does NOT appear in active corpus."""
    pub_repo = invariant_setup["pub_repo"]
    service = invariant_setup["service"]
    project_id = "proj_1"
    import_id = uuid4()

    p_retained = make_publication(index=1, title="Valid Study")
    p_archived = make_publication(index=2, title="Index Announcement")
    pub_repo.import_source_publications(project_id, [p_retained, p_archived], import_id=import_id)

    # Archive and physically delete p_archived
    service.archive_pre_screening_removal(
        project_id=project_id,
        import_id=import_id,
        record_id=p_archived.record_id,
        reason=PreScreeningRemovalReason.RETRIEVAL_ARTEFACT,
        physical_delete=True,
    )

    active = get_active_project_publications(project_id, repository=pub_repo)
    assert len(active) == 1
    assert active[0].record_id == p_retained.record_id
    assert count_active_project_publications(project_id, repository=pub_repo) == 1

    # Ensure p_archived is also physically gone from project_publications
    assert pub_repo.count_by_project(project_id) == 1


def test_invariant_d_and_e_archive_preserves_full_metadata_and_provenance(invariant_setup):
    """Invariant D & E: archive contains complete metadata, identifiers, DOI, provenance, and raw snapshot."""
    pub_repo = invariant_setup["pub_repo"]
    archive_repo = invariant_setup["archive_repo"]
    service = invariant_setup["service"]
    project_id = "proj_1"
    import_id = uuid4()

    p_original = make_publication(
        index=10,
        title="Comprehensive Meta-Analysis of Lean Energy Methods",
        doi="10.1016/j.cleaner.2024.101234",
        source="openalex",
        year=2024,
    )
    pub_repo.import_source_publications(project_id, [p_original], import_id=import_id)

    archived = service.archive_pre_screening_removal(
        project_id=project_id,
        import_id=import_id,
        record_id=p_original.record_id,
        reason=PreScreeningRemovalReason.CLEARLY_OUTSIDE_SCOPE,
        notes="Non-manufacturing sector",
        reviewer_id="reviewer_lead",
        physical_delete=True,
    )

    # Assert archive record exists and is complete
    fetched = archive_repo.get_archived_record(project_id, p_original.record_id)
    assert fetched is not None
    assert fetched.archive_id == archived.archive_id
    assert fetched.project_id == project_id
    assert fetched.record_id == p_original.record_id
    assert fetched.import_id == import_id
    assert fetched.title == p_original.title
    assert fetched.publication_year == 2024
    assert fetched.removal_reason == PreScreeningRemovalReason.CLEARLY_OUTSIDE_SCOPE
    assert fetched.removal_notes == "Non-manufacturing sector"
    assert fetched.removed_by == "reviewer_lead"
    assert fetched.identifiers == [Identifier(type=IdentifierType.DOI, value="10.1016/j.cleaner.2024.101234")]
    assert fetched.provenance[0].source.casefold() == "openalex"

    # Reconstruct Publication from snapshot
    reconstituted = fetched.to_publication()
    assert reconstituted.record_id == p_original.record_id
    assert reconstituted.title == p_original.title
    assert reconstituted.publication_year == p_original.publication_year


def test_invariant_f_archive_operation_cross_project_isolation(invariant_setup):
    """Invariant F: archive operation cannot silently archive record from another project."""
    pub_repo = invariant_setup["pub_repo"]
    service = invariant_setup["service"]

    # Pub belongs to proj_2
    p_proj2 = make_publication(index=1, title="Project 2 Publication")
    pub_repo.import_source_publications("proj_2", [p_proj2])

    # Attempting to archive in proj_1 must fail
    with pytest.raises(PreScreeningRecordNotFoundError):
        service.archive_pre_screening_removal(
            project_id="proj_1",
            import_id=uuid4(),
            record_id=p_proj2.record_id,
            reason=PreScreeningRemovalReason.RETRIEVAL_ARTEFACT,
            physical_delete=True,
        )


def test_invariant_g_archive_operation_idempotency(invariant_setup):
    """Invariant G: archive operation is safe against duplicate invocation."""
    pub_repo = invariant_setup["pub_repo"]
    archive_repo = invariant_setup["archive_repo"]
    service = invariant_setup["service"]
    project_id = "proj_1"
    import_id = uuid4()

    pub = make_publication(index=1, title="Duplicate Archive Target")
    pub_repo.import_source_publications(project_id, [pub], import_id=import_id)

    # First invocation (physical deletion)
    first = service.archive_pre_screening_removal(
        project_id=project_id,
        import_id=import_id,
        record_id=pub.record_id,
        reason=PreScreeningRemovalReason.RETRIEVAL_ARTEFACT,
        physical_delete=True,
    )

    # Second invocation on the already physically deleted record
    second = service.archive_pre_screening_removal(
        project_id=project_id,
        import_id=import_id,
        record_id=pub.record_id,
        reason=PreScreeningRemovalReason.RETRIEVAL_ARTEFACT,
        physical_delete=True,
    )

    assert second.record_id == first.record_id
    assert second.archive_id == first.archive_id
    assert archive_repo.count_archived_for_project(project_id) == 1


def test_invariant_h_archive_does_not_create_formal_screening_exclusion(invariant_setup):
    """Invariant H: archive does NOT create formal screening exclusion/decision."""
    pub_repo = invariant_setup["pub_repo"]
    screening_decision_repo = invariant_setup["screening_decision_repo"]
    service = invariant_setup["service"]
    project_id = "proj_1"
    import_id = uuid4()

    pub = make_publication(index=1, title="Pre-Screening Removal")
    pub_repo.import_source_publications(project_id, [pub], import_id=import_id)

    service.archive_pre_screening_removal(
        project_id=project_id,
        import_id=import_id,
        record_id=pub.record_id,
        reason=PreScreeningRemovalReason.RETRIEVAL_ARTEFACT,
        physical_delete=True,
    )

    # Ensure 0 formal screening decisions exist
    decisions = screening_decision_repo.list_by_project(project_id)
    assert len(decisions) == 0


def test_invariant_i_legacy_projects_remain_readable(invariant_setup):
    """Invariant I: existing legacy projects remain readable."""
    pub_repo = invariant_setup["pub_repo"]
    project_id = "proj_1"

    # Project with multiple retained publications and no archive entries
    pubs = [make_publication(index=i, title=f"Legacy Pub {i}") for i in range(5)]
    pub_repo.import_source_publications(project_id, pubs)

    active = get_active_project_publications(project_id, repository=pub_repo)
    assert len(active) == 5
    assert count_active_project_publications(project_id, repository=pub_repo) == 5


def test_invariant_j_active_corpus_query_provider_agnostic(invariant_setup):
    """Invariant J: active corpus query does not depend on hardcoded provider names."""
    pub_repo = invariant_setup["pub_repo"]
    project_id = "proj_1"

    p_crossref = make_publication(index=1, source="crossref", title="Crossref Pub")
    p_openalex = make_publication(index=2, source="openalex", title="OpenAlex Pub")
    p_s2 = make_publication(index=3, source="semantic_scholar", title="S2 Pub")
    p_custom = make_publication(index=4, source="custom_file_ris", title="RIS Pub")

    pub_repo.import_source_publications(project_id, [p_crossref, p_openalex, p_s2, p_custom])

    active = get_active_project_publications(project_id, repository=pub_repo)
    assert len(active) == 4
    sources = {p.provenance[0].source for p in active}
    assert sources == {"crossref", "openalex", "semantic_scholar", "custom_file_ris"}
