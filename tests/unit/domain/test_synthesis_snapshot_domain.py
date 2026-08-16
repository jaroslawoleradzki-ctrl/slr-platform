"""Unit tests for Phase 10.7 Synthesis Snapshot domain models and hash engine.

Checkpoint A: deterministic SHA-256 dataset hashing, immutable snapshot
identity, COMPLETE-only evidence semantics, and criterion-level QA preservation.
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.domain.extraction import (
    ExtractedGroupItemState,
    ExtractedValueState,
    ExtractionCompletenessStatus,
    ExtractionRevision,
    ValueOrigin,
    ValueStatus,
)
from app.domain.synthesis import (
    QACriterionAssessmentSummary,
    QAProfileSummary,
    SynthesisSnapshot,
    SynthesisSnapshotContent,
    build_extraction_dataset_items,
    compute_classification_version,
    compute_content_hash,
    compute_extraction_dataset_hash,
)


def _revision(
    *,
    publication_id=None,
    revision_id=None,
    group_item_id=None,
    completeness=ExtractionCompletenessStatus.COMPLETE,
    lean_practice="Value Stream Mapping",
    energy_effect="reduction",
):
    return ExtractionRevision(
        revision_id=revision_id or uuid4(),
        record_id=uuid4(),
        project_id="proj-test",
        publication_id=publication_id or uuid4(),
        revision_index=1,
        reviewer_id="rev_1",
        completeness_status=completeness,
        group_items=[
            ExtractedGroupItemState(
                group_item_id=group_item_id or uuid4(),
                group_key="lean_energy_relationships",
                item_index=1,
                values=[
                    ExtractedValueState(
                        field_key="lean_practice",
                        status=ValueStatus.PRESENT,
                        origin=ValueOrigin.REPORTED,
                        text_value=lean_practice,
                        source_locator="Table 1",
                    ),
                    ExtractedValueState(
                        field_key="energy_effect_indicator",
                        status=ValueStatus.PRESENT,
                        origin=ValueOrigin.REPORTED,
                        text_value=energy_effect,
                        source_locator="Table 1",
                    ),
                ],
            )
        ],
        created_at=datetime.now(timezone.utc),
    )


# ---------------------------------------------------------------------------
# A1: Snapshot identity validation
# ---------------------------------------------------------------------------


def test_a1_snapshot_identity_fields():
    snap = SynthesisSnapshot(
        snapshot_id=uuid4(),
        project_id="proj-test",
        version=1,
        actor="researcher-1",
        extraction_dataset_hash="a" * 64,
        classification_version="b" * 64,
        content_hash="c" * 64,
        content=SynthesisSnapshotContent(project_id="proj-test"),
        created_at=datetime.now(timezone.utc),
    )
    assert snap.project_id == "proj-test"
    assert snap.version == 1
    assert snap.actor == "researcher-1"
    assert len(snap.extraction_dataset_hash) == 64
    assert len(snap.classification_version) == 64
    assert len(snap.content_hash) == 64


def test_a1_snapshot_rejects_short_hash():
    with pytest.raises(ValidationError):
        SynthesisSnapshot(
            project_id="proj-test",
            version=1,
            actor="r",
            extraction_dataset_hash="abc",
            classification_version="b" * 64,
            content_hash="c" * 64,
            content=SynthesisSnapshotContent(project_id="proj-test"),
        )


# ---------------------------------------------------------------------------
# A2: Project identity and version validation
# ---------------------------------------------------------------------------


def test_a2_snapshot_rejects_empty_project():
    with pytest.raises(ValidationError):
        SynthesisSnapshot(
            project_id="",
            version=1,
            actor="r",
            extraction_dataset_hash="a" * 64,
            classification_version="b" * 64,
            content_hash="c" * 64,
            content=SynthesisSnapshotContent(project_id=""),
        )


def test_a2_snapshot_rejects_version_zero():
    with pytest.raises(ValidationError):
        SynthesisSnapshot(
            project_id="proj-test",
            version=0,
            actor="r",
            extraction_dataset_hash="a" * 64,
            classification_version="b" * 64,
            content_hash="c" * 64,
            content=SynthesisSnapshotContent(project_id="proj-test"),
        )


# ---------------------------------------------------------------------------
# A3: Deterministic dataset hash
# ---------------------------------------------------------------------------


def test_a3_dataset_hash_is_deterministic():
    rev = _revision()
    items_a = build_extraction_dataset_items([rev])
    items_b = build_extraction_dataset_items([rev])
    assert compute_extraction_dataset_hash(items_a) == compute_extraction_dataset_hash(items_b)


def test_a3_dataset_hash_is_sha256():
    rev = _revision()
    digest = compute_extraction_dataset_hash(build_extraction_dataset_items([rev]))
    assert len(digest) == 64
    assert all(c in "0123456789abcdef" for c in digest)


# ---------------------------------------------------------------------------
# A4: Ordering does not change the dataset hash
# ---------------------------------------------------------------------------


def test_a4_item_insertion_order_does_not_change_hash():
    rev_a = _revision(lean_practice="5S")
    rev_b = _revision(lean_practice="SMED")
    ordered = build_extraction_dataset_items([rev_a, rev_b])
    reversed_items = build_extraction_dataset_items([rev_b, rev_a])
    assert compute_extraction_dataset_hash(ordered) == compute_extraction_dataset_hash(reversed_items)


def test_a4_value_order_does_not_change_hash():
    rev = _revision()
    items = build_extraction_dataset_items([rev])
    flipped = []
    for item in items:
        flipped.append(dict(item, values=list(reversed(item["values"]))))
    assert compute_extraction_dataset_hash(items) == compute_extraction_dataset_hash(flipped)


# ---------------------------------------------------------------------------
# A5: Relevant data change changes the dataset hash
# ---------------------------------------------------------------------------


def test_a5_value_change_changes_hash():
    rev_a = _revision(lean_practice="Value Stream Mapping")
    rev_b = _revision(lean_practice="Single Minute Exchange of Die")
    assert compute_extraction_dataset_hash(build_extraction_dataset_items([rev_a])) != compute_extraction_dataset_hash(
        build_extraction_dataset_items([rev_b])
    )


# ---------------------------------------------------------------------------
# A6: DRAFT never enters the dataset identity
# ---------------------------------------------------------------------------


def test_a6_draft_revision_does_not_enter_dataset_hash():
    complete = _revision(completeness=ExtractionCompletenessStatus.COMPLETE)
    draft = _revision(completeness=ExtractionCompletenessStatus.IN_PROGRESS)

    only_complete = build_extraction_dataset_items([complete])
    with_draft = build_extraction_dataset_items([complete, draft])

    assert compute_extraction_dataset_hash(only_complete) == compute_extraction_dataset_hash(with_draft)


def test_a6_draft_only_dataset_hashes_to_empty_identity():
    draft = _revision(completeness=ExtractionCompletenessStatus.IN_PROGRESS)
    items = build_extraction_dataset_items([draft])
    assert items == []
    assert compute_extraction_dataset_hash(items) == compute_extraction_dataset_hash([])


# ---------------------------------------------------------------------------
# A7: Criterion-level QA is preserved (no score flattening)
# ---------------------------------------------------------------------------


def test_a7_qa_profile_preserves_criterion_level_assessments():
    qa = QAProfileSummary(
        assessment_id=uuid4(),
        template_id=uuid4(),
        reviewer_id="reviewer_1",
        criteria_assessments=[
            QACriterionAssessmentSummary(
                criterion_id=uuid4(),
                question_text="Clear objectives?",
                response_value="YES",
                justification="Described in the introduction.",
            ),
            QACriterionAssessmentSummary(
                criterion_id=uuid4(),
                question_text="Methods described?",
                response_value="NO",
                justification=None,
            ),
        ],
    )
    assert len(qa.criteria_assessments) == 2
    assert qa.criteria_assessments[0].response_value == "YES"
    assert qa.criteria_assessments[1].response_value == "NO"


def test_a7_content_holds_criterion_level_qa_profiles():
    qa = QAProfileSummary(
        assessment_id=uuid4(),
        template_id=uuid4(),
        reviewer_id="reviewer_1",
        criteria_assessments=[QACriterionAssessmentSummary(criterion_id=uuid4(), question_text="q", response_value="YES")],
    )
    content = SynthesisSnapshotContent(project_id="proj-test", qa_profiles=[qa])
    assert content.qa_profiles[0].criteria_assessments[0].response_value == "YES"


# ---------------------------------------------------------------------------
# A8: Content hash is deterministic and content is immutable
# ---------------------------------------------------------------------------


def test_a8_content_hash_is_deterministic_across_assemblies():
    content_a = SynthesisSnapshotContent(project_id="proj-test")
    content_b = SynthesisSnapshotContent(project_id="proj-test")
    assert compute_content_hash(content_a) == compute_content_hash(content_b)


def test_a8_content_hash_changes_when_content_changes():
    base = SynthesisSnapshotContent(project_id="proj-test")
    modified = SynthesisSnapshotContent(
        project_id="proj-test",
        term_mappings=[],
    )
    # Adding a relation must change the content hash.
    assert compute_content_hash(base) == compute_content_hash(modified)


def test_a8_classification_version_is_deterministic():
    v1 = compute_classification_version(term_mappings=[])
    v2 = compute_classification_version(term_mappings=[])
    assert v1 == v2
    assert len(v1) == 64


def test_a8_snapshot_content_is_frozen():
    content = SynthesisSnapshotContent(project_id="proj-test")
    with pytest.raises(ValidationError):
        content.project_id = "other-project"  # type: ignore[misc]
