from datetime import datetime, timezone
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.domain.deduplication import DuplicateGroup, DuplicateGroupMergeRecord, DuplicateGroupStatus
from app.domain.duplicate_review import DuplicateDecision
from app.domain.provenance import ProvenanceEntry
from app.domain.publication import Publication


def _publication(number: int) -> Publication:
    return Publication(record_id=UUID(f"00000000-0000-0000-0000-{number:012d}"), title=f"Paper {number}", provenance=[ProvenanceEntry(source="test", source_record_id=str(number))])


def test_reviewer_decision_is_strictly_scientific_verdict() -> None:
    assert {value.value for value in DuplicateDecision} == {"APPROVE", "REJECT"}


def test_group_lifecycle_is_separate_from_reviewer_decision() -> None:
    assert {value.value for value in DuplicateGroupStatus} == {"pending", "approved", "rejected", "merged"}


def test_merge_record_requires_complete_reversible_snapshot() -> None:
    first, second = _publication(1), _publication(2)
    record = DuplicateGroupMergeRecord(project_id="p", group_id="g", canonical_record_id=first.record_id, merged_publication_ids=(first.record_id, second.record_id), pre_merge_snapshots=(first, second))
    assert record.status == "merged"
    with pytest.raises(ValidationError):
        DuplicateGroupMergeRecord(project_id="p", group_id="g", canonical_record_id=first.record_id, merged_publication_ids=(first.record_id, second.record_id), pre_merge_snapshots=(first,))


def test_duplicate_group_remains_review_aggregate_only() -> None:
    group = DuplicateGroup(publication_ids=(_publication(1).record_id, _publication(2).record_id), created_at=datetime(2026, 1, 1, tzinfo=timezone.utc), updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc))
    assert group.status is DuplicateGroupStatus.PENDING
    assert not hasattr(group, "merge")
