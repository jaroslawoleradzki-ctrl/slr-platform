"""Unit tests for Phase 10.1 Data Synthesis in-memory domain models and invariants."""

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.domain.synthesis import (
    AnalyticalRelation,
    ClassificationApprovalState,
    ConvertedValue,
    EnergyEffectCategory,
    EvidenceCharacter,
    ExtractionEvidenceReference,
    LeanPracticeCategory,
    QACriterionAssessmentSummary,
    QAProfileSummary,
    RelationDirection,
    convert_physical_energy_unit,
)


def test_analytical_relation_creation_and_attributes():
    rel_id = uuid4()
    pub_id = uuid4()
    rev_id = uuid4()
    group_item_id = uuid4()
    now = datetime.now(timezone.utc)

    relation = AnalyticalRelation(
        relation_id=rel_id,
        project_id="proj-test",
        publication_id=pub_id,
        latest_revision_id=rev_id,
        group_item_id=group_item_id,
        item_index=1,
        source_practice="5S / Visual Management",
        source_effect="12.5% reduction in electricity consumption",
        direction=RelationDirection.POSITIVE,
        magnitude=12.5,
        original_unit="%",
        evidence_character=EvidenceCharacter.EMPIRICAL,
        approval_state=ClassificationApprovalState.PENDING,
        created_at=now,
        updated_at=now,
    )

    assert relation.relation_id == rel_id
    assert relation.project_id == "proj-test"
    assert relation.group_item_id == group_item_id
    assert relation.direction == RelationDirection.POSITIVE
    assert relation.evidence_character == EvidenceCharacter.EMPIRICAL
    assert relation.approval_state == ClassificationApprovalState.PENDING
    assert relation.created_at == now
    assert relation.updated_at == now


def test_analytical_relation_validation_errors():
    group_item_id = uuid4()

    # Invalid item_index (< 1)
    with pytest.raises(ValidationError):
        AnalyticalRelation(
            project_id="proj-test",
            publication_id=uuid4(),
            latest_revision_id=uuid4(),
            group_item_id=group_item_id,
            item_index=0,
            source_practice="5S",
            source_effect="Energy reduction",
        )

    # Blank source practice
    with pytest.raises(ValidationError):
        AnalyticalRelation(
            project_id="proj-test",
            publication_id=uuid4(),
            latest_revision_id=uuid4(),
            group_item_id=group_item_id,
            item_index=1,
            source_practice="",
            source_effect="Energy reduction",
        )

    # Blank source effect
    with pytest.raises(ValidationError):
        AnalyticalRelation(
            project_id="proj-test",
            publication_id=uuid4(),
            latest_revision_id=uuid4(),
            group_item_id=group_item_id,
            item_index=1,
            source_practice="5S",
            source_effect="",
        )

    # Non-timezone-aware created_at
    with pytest.raises(ValidationError, match="timestamps must be timezone-aware"):
        AnalyticalRelation(
            project_id="proj-test",
            publication_id=uuid4(),
            latest_revision_id=uuid4(),
            group_item_id=group_item_id,
            item_index=1,
            source_practice="5S",
            source_effect="Energy reduction",
            created_at=datetime(2026, 1, 1, 0, 0, 0),
        )

    # Non-timezone-aware updated_at
    with pytest.raises(ValidationError, match="timestamps must be timezone-aware"):
        AnalyticalRelation(
            project_id="proj-test",
            publication_id=uuid4(),
            latest_revision_id=uuid4(),
            group_item_id=group_item_id,
            item_index=1,
            source_practice="5S",
            source_effect="Energy reduction",
            updated_at=datetime(2026, 1, 1, 0, 0, 0),
        )


def test_categories_instantiation():
    lean_cat = LeanPracticeCategory(
        category_id="5s", name="5S & Workplace Organization", description="5S standard", display_order=1
    )
    assert lean_cat.category_id == "5s"
    assert lean_cat.display_order == 1

    energy_cat = EnergyEffectCategory(
        category_id="elec", name="Direct Electricity", description="kWh direct consumption", display_order=2
    )
    assert energy_cat.category_id == "elec"
    assert energy_cat.display_order == 2


def test_extraction_evidence_reference():
    ref_id = uuid4()
    pub_id = uuid4()
    rev_id = uuid4()
    group_id = uuid4()
    now = datetime.now(timezone.utc)

    ref = ExtractionEvidenceReference(
        reference_id=ref_id,
        project_id="proj-test",
        publication_id=pub_id,
        revision_id=rev_id,
        group_key="lean_ee_relationships",
        group_item_id=group_id,
        field_key="effect",
        created_at=now,
    )
    assert ref.reference_id == ref_id
    assert ref.project_id == "proj-test"
    assert ref.group_item_id == group_id
    assert ref.created_at == now

    # Non-timezone-aware timestamp
    with pytest.raises(ValidationError, match="created_at must be timezone-aware"):
        ExtractionEvidenceReference(
            project_id="proj-test",
            publication_id=pub_id,
            revision_id=rev_id,
            created_at=datetime(2026, 1, 1, 0, 0, 0),
        )


def test_deterministic_physical_energy_unit_conversion():
    # 1 kWh to MJ: 1 kWh = 3,600,000 J; 1 MJ = 1,000,000 J => 3.6 MJ
    val, unit, rule = convert_physical_energy_unit(10.0, "kWh", "MJ")
    assert val == pytest.approx(36.0)
    assert unit == "MJ"
    assert "1 kWh" in rule and "MJ" in rule

    # 1 GJ to kWh: 1 GJ = 1,000,000,000 J; 1 kWh = 3,600,000 J => 277.777778 kWh
    val2, unit2, _ = convert_physical_energy_unit(1.0, "GJ", "kWh")
    assert val2 == pytest.approx(277.777778, rel=1e-4)
    assert unit2 == "kWh"

    # Unsupported or cross-metric unit conversions raise ValueError
    with pytest.raises(ValueError, match="Unsupported physical energy unit"):
        convert_physical_energy_unit(50.0, "kWh", "liters")

    with pytest.raises(ValueError, match="Unsupported physical energy unit"):
        convert_physical_energy_unit(50.0, "kg", "kWh")


def test_converted_value_value_object():
    cv = ConvertedValue(
        transformed_value=36.0,
        transformed_unit="MJ",
        conversion_rule="1 kWh = 3.6 MJ",
    )
    assert cv.transformed_value == 36.0
    assert cv.transformed_unit == "MJ"
    assert cv.conversion_rule == "1 kWh = 3.6 MJ"


def test_qa_profile_summary_no_score_collapse():
    crit1_id = uuid4()
    crit2_id = uuid4()

    summary = QAProfileSummary(
        assessment_id=uuid4(),
        template_id=uuid4(),
        reviewer_id="reviewer-1",
        criteria_assessments=[
            QACriterionAssessmentSummary(
                criterion_id=crit1_id,
                question_text="Are sampling criteria clearly defined?",
                response_value="yes",
                justification="Detailed sampling protocol provided in Section 2",
            ),
            QACriterionAssessmentSummary(
                criterion_id=crit2_id,
                question_text="Was energy consumption directly metered?",
                response_value="no",
                justification="Derived from utility billing records",
            ),
        ],
    )

    assert len(summary.criteria_assessments) == 2
    # Invariant: Each criterion retains its individual response and justification
    assert summary.criteria_assessments[0].response_value == "yes"
    assert summary.criteria_assessments[1].response_value == "no"
