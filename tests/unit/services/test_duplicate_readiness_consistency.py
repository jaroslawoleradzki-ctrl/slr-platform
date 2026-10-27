from pathlib import Path
from uuid import UUID

from app.domain.duplicate_review import DuplicateDecision, DuplicateGroupReviewDecision
from app.domain.identifiers import Identifier, IdentifierType
from app.domain.project import Project
from app.domain.provenance import ProvenanceEntry
from app.domain.publication import Publication
from app.repositories.duplicate_merge_repository import SqliteDuplicateMergeRepository
from app.repositories.duplicate_review_decision_repository import (
    SqliteDuplicateReviewDecisionRepository,
)
from app.repositories.project_publication_repository import SqliteProjectPublicationRepository
from app.repositories.project_repository import SqliteProjectRepository
from app.repositories.transaction_manager import SqliteTransactionManager
from app.services.project_duplicate_service import ProjectDuplicateService
from app.services.screening_input_service import (
    ScreeningInputReadinessStatus,
    ScreeningInputService,
)

PROJECT_ID = "readiness-project"


def _publication(number: int, doi: str, *, source: str | None = None) -> Publication:
    return Publication(
        record_id=UUID(f"00000000-0000-0000-0000-{number:012d}"),
        title=f"Publication {number}",
        identifiers=[Identifier(type=IdentifierType.DOI, value=doi)],
        provenance=[
            ProvenanceEntry(source=source or f"source-{number}", source_record_id=str(number))
        ],
    )


def _environment(tmp_path: Path, publications: list[Publication]):
    database = tmp_path / "readiness.db"
    SqliteProjectRepository(database).create(
        Project(project_id=PROJECT_ID, title="Readiness project")
    )
    publication_repository = SqliteProjectPublicationRepository(database)
    publication_repository.add_publications(PROJECT_ID, publications)
    decision_repository = SqliteDuplicateReviewDecisionRepository(database)
    merge_repository = SqliteDuplicateMergeRepository(database)
    duplicate_service = ProjectDuplicateService(
        publication_repository,
        decision_repository,
        merge_repository=merge_repository,
        transaction_manager=SqliteTransactionManager(database),
    )
    screening_service = ScreeningInputService(
        publication_repository,
        decision_repository,
        merge_repository=merge_repository,
    )
    return (
        database,
        publication_repository,
        decision_repository,
        merge_repository,
        duplicate_service,
        screening_service,
    )


def test_merged_group_then_new_import_is_pending_in_both_views(tmp_path: Path) -> None:
    first = _publication(1, "10.1000/shared")
    second = _publication(2, "10.1000/shared")
    (
        _,
        publication_repository,
        _,
        _,
        duplicate_service,
        screening_service,
    ) = _environment(tmp_path, [first, second])

    original_group_id = duplicate_service.get_candidate_duplicate_groups(PROJECT_ID).groups[0].group_id
    duplicate_service.merge_group(PROJECT_ID, original_group_id)
    later_import = _publication(3, "10.1000/shared")
    publication_repository.add_publications(PROJECT_ID, [later_import])

    duplicate_response = duplicate_service.get_candidate_duplicate_groups(PROJECT_ID)
    screening_input = screening_service.get_input_set(PROJECT_ID)

    pending_groups = [
        group for group in duplicate_response.groups if group.status.value == "PENDING"
    ]
    assert len(pending_groups) == 1
    assert pending_groups[0].group_id not in {original_group_id}
    assert duplicate_response.readiness.status == "pending_review"
    assert duplicate_response.readiness.pending_review_groups == 1
    assert duplicate_response.readiness.blocking_group_ids == [pending_groups[0].group_id]
    assert screening_input.readiness_status is ScreeningInputReadinessStatus.UNRESOLVED_DUPLICATES
    assert screening_input.duplicate_readiness.status == "pending_review"
    assert screening_input.duplicate_readiness.pending_review_groups == 1
    assert screening_input.duplicate_readiness.blocking_group_ids == (
        pending_groups[0].group_id,
    )


def test_approved_but_unmerged_group_is_merge_required_in_both_views(tmp_path: Path) -> None:
    first = _publication(1, "10.1000/shared")
    second = _publication(2, "10.1000/shared")
    (
        _,
        _,
        decision_repository,
        _,
        duplicate_service,
        screening_service,
    ) = _environment(tmp_path, [first, second])
    group_id = duplicate_service.get_candidate_duplicate_groups(PROJECT_ID).groups[0].group_id
    decision_repository.save_decision(
        PROJECT_ID,
        group_id,
        DuplicateGroupReviewDecision(decision=DuplicateDecision.APPROVE),
    )

    duplicate_response = duplicate_service.get_candidate_duplicate_groups(PROJECT_ID)
    screening_input = screening_service.get_input_set(PROJECT_ID)

    assert duplicate_response.readiness.status == "approved_unmerged"
    assert duplicate_response.readiness.approved_unmerged_groups == 1
    assert duplicate_response.readiness.screening_ready is False
    assert duplicate_response.readiness.blocking_group_ids == [group_id]
    assert screening_input.readiness_status is ScreeningInputReadinessStatus.UNMERGED_DUPLICATES
    assert screening_input.duplicate_readiness.status == "approved_unmerged"
    assert screening_input.duplicate_readiness.blocking_group_ids == (group_id,)


def test_rejected_and_merged_groups_are_ready_and_do_not_block_screening(tmp_path: Path) -> None:
    first = _publication(1, "10.1000/rejected")
    second = _publication(2, "10.1000/rejected")
    third = _publication(3, "10.1000/merged")
    fourth = _publication(4, "10.1000/merged")
    (
        _,
        _,
        decision_repository,
        _,
        duplicate_service,
        screening_service,
    ) = _environment(tmp_path, [first, second, third, fourth])
    groups = duplicate_service.get_candidate_duplicate_groups(PROJECT_ID).groups
    rejected_group = next(
        group for group in groups if {record.id for record in group.records} == {str(first.record_id), str(second.record_id)}
    )
    merged_group = next(
        group for group in groups if {record.id for record in group.records} == {str(third.record_id), str(fourth.record_id)}
    )
    decision_repository.save_decision(
        PROJECT_ID,
        rejected_group.group_id,
        DuplicateGroupReviewDecision(decision=DuplicateDecision.REJECT),
    )
    duplicate_service.merge_group(PROJECT_ID, merged_group.group_id)

    duplicate_response = duplicate_service.get_candidate_duplicate_groups(PROJECT_ID)
    screening_input = screening_service.get_input_set(PROJECT_ID)

    assert duplicate_response.readiness.status == "ready"
    assert duplicate_response.readiness.rejected_groups == 1
    assert duplicate_response.readiness.merged_groups == 1
    assert duplicate_response.readiness.screening_ready is True
    assert duplicate_response.readiness.blocking_group_ids == []
    assert screening_input.ready is True
    assert screening_input.readiness_status is ScreeningInputReadinessStatus.READY


def test_stale_decision_does_not_block_screening(tmp_path: Path) -> None:
    first = _publication(1, "10.1000/stale")
    second = _publication(2, "10.1000/stale")
    (
        _,
        publication_repository,
        decision_repository,
        _,
        duplicate_service,
        screening_service,
    ) = _environment(tmp_path, [first, second])
    group_id = duplicate_service.get_candidate_duplicate_groups(PROJECT_ID).groups[0].group_id
    decision_repository.save_decision(
        PROJECT_ID,
        group_id,
        DuplicateGroupReviewDecision(decision=DuplicateDecision.REJECT),
    )
    publication_repository.update_pre_screening_status(PROJECT_ID, second.record_id, "removed")

    duplicate_response = duplicate_service.get_candidate_duplicate_groups(PROJECT_ID)
    screening_input = screening_service.get_input_set(PROJECT_ID)

    assert duplicate_response.readiness.status in {"no_candidates", "ready"}
    assert duplicate_response.readiness.stale_decisions == 1
    assert duplicate_response.readiness.blocking_group_ids == []
    assert screening_input.ready is True


def test_no_candidate_groups_is_explicit_and_ready(tmp_path: Path) -> None:
    (
        _,
        _,
        _,
        _,
        duplicate_service,
        screening_service,
    ) = _environment(tmp_path, [_publication(1, "10.1000/unique")])

    duplicate_response = duplicate_service.get_candidate_duplicate_groups(PROJECT_ID)
    screening_input = screening_service.get_input_set(PROJECT_ID)

    assert duplicate_response.readiness.status == "no_candidates"
    assert duplicate_response.readiness.total_groups == 0
    assert duplicate_response.readiness.screening_ready is True
    assert screening_input.ready is True
