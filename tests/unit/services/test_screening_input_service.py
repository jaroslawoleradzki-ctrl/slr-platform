from uuid import UUID

from app.domain.duplicate_review import DuplicateDecision, DuplicateGroupReviewDecision
from app.domain.identifiers import Identifier, IdentifierType
from app.domain.provenance import ProvenanceEntry
from app.domain.publication import Publication
from app.repositories.duplicate_review_decision_repository import InMemoryDuplicateReviewDecisionRepository
from app.services.duplicate_group_builder import DuplicateGroupBuilder
from app.services.screening_input_service import ScreeningInputReadinessStatus, ScreeningInputService


class _Publications:
    def __init__(self, projects):
        self.projects = projects

    def get_publications(self, project_id):
        return list(self.projects[project_id])


def _pub(number: int, doi: str | None = None, *, abstract: str | None = None) -> Publication:
    return Publication(
        record_id=UUID(f"00000000-0000-0000-0000-{number:012d}"),
        title=f"Title {number}",
        abstract=abstract,
        identifiers=[] if doi is None else [Identifier(type=IdentifierType.DOI, value=doi)],
        provenance=[ProvenanceEntry(source=f"source-{number}", source_record_id=str(number))],
    )


def _service(publications, decisions=()):
    repo = _Publications({"a": publications, "b": []})
    decision_repo = InMemoryDuplicateReviewDecisionRepository()
    groups = DuplicateGroupBuilder().build(publications)
    for group, decision in zip(groups, decisions):
        decision_repo.save_decision("a", str(group.group_id), DuplicateGroupReviewDecision(decision=decision))
    return ScreeningInputService(repo, decision_repo), repo


def test_empty_and_records_without_groups_are_ready_and_sorted() -> None:
    empty, _ = _service([])
    assert empty.get_input_set("a").ready
    service, _ = _service([_pub(2), _pub(1)])
    result = service.get_input_set("a")
    assert [p.record_id for p in result.publications] == sorted(p.record_id for p in result.publications)


def test_pending_blocks_the_entire_input_set() -> None:
    service, _ = _service([_pub(1, "10.1/x"), _pub(2, "10.1/x")])
    result = service.get_readiness("a")
    assert not result.ready and result.unresolved_groups_count == 1
    assert result.publications == () and result.canonical_records_count == 0
    assert result.readiness_status is ScreeningInputReadinessStatus.UNRESOLVED_DUPLICATES


def test_approved_group_blocks_until_persisted_merge() -> None:
    publications = [_pub(2, "10.1/x", abstract="short"), _pub(1, "10.1/x", abstract="long abstract")]
    service, _ = _service(publications, [DuplicateDecision.APPROVE])
    first = service.get_input_set("a")
    assert not first.ready
    assert first.readiness_status is ScreeningInputReadinessStatus.UNMERGED_DUPLICATES


def test_reject_keeps_all_records_separate() -> None:
    service, _ = _service([_pub(1, "10.1/x"), _pub(2, "10.1/x")], [DuplicateDecision.REJECT])
    assert len(service.get_input_set("a").publications) == 2


def test_multiple_approved_groups_block_without_in_memory_merge() -> None:
    publications = [_pub(5), _pub(4, "10.1/y"), _pub(3, "10.1/y"), _pub(2, "10.1/x"), _pub(1, "10.1/x")]
    service, _ = _service(publications, [DuplicateDecision.APPROVE, DuplicateDecision.APPROVE])
    assert not service.get_input_set("a").ready


def test_project_isolation() -> None:
    service, repo = _service([_pub(1)])
    repo.projects["b"] = [_pub(9)]
    assert service.get_input_set("a").publications != service.get_input_set("b").publications


def test_no_merge_conflict_path_is_executed_in_memory() -> None:
    first = _pub(1, "10.1/first").model_copy(
        update={
            "identifiers": [
                Identifier(type=IdentifierType.DOI, value="10.1/first"),
                Identifier(type=IdentifierType.PMID, value="shared"),
            ]
        }
    )
    second = _pub(2, "10.1/second").model_copy(
        update={
            "identifiers": [
                Identifier(type=IdentifierType.DOI, value="10.1/second"),
                Identifier(type=IdentifierType.PMID, value="shared"),
            ]
        }
    )
    service, _ = _service([first, second], [DuplicateDecision.APPROVE])

    result = service.get_input_set("a")

    assert not result.ready
    assert result.unresolved_groups_count == 1
    assert result.readiness_status is ScreeningInputReadinessStatus.UNMERGED_DUPLICATES
