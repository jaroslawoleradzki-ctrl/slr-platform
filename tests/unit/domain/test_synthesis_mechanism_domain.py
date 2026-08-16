"""Unit tests for Phase 10 Task 10.4 Mechanism Synthesis Domain Models."""

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.domain.synthesis import (
    AnalyticalMechanismCategory,
    ClassificationApprovalState,
    MechanismPathway,
    MechanismSynthesisPathway,
)


def test_analytical_mechanism_category_valid():
    cat = AnalyticalMechanismCategory(
        category_id="idle_time_reduction",
        name="Idle-Time Reduction",
        project_id="proj_1",
        description="Mitigating machinery idle energy losses.",
        display_order=1,
    )
    assert cat.category_id == "idle_time_reduction"
    assert cat.name == "Idle-Time Reduction"
    assert cat.project_id == "proj_1"
    assert cat.created_at.tzinfo is not None


def test_analytical_mechanism_category_validation_failures():
    # Empty name forbidden
    with pytest.raises(ValidationError):
        AnalyticalMechanismCategory(category_id="test", name="", project_id="proj_1")

    # Empty category_id forbidden
    with pytest.raises(ValidationError):
        AnalyticalMechanismCategory(category_id="", name="Test", project_id="proj_1")


def test_mechanism_pathway_valid():
    path_id = uuid4()
    rel_id = uuid4()
    g_id = uuid4()
    pub_id = uuid4()
    rev_id = uuid4()

    pathway = MechanismPathway(
        pathway_id=path_id,
        project_id="proj_1",
        analytical_relation_id=rel_id,
        group_item_id=g_id,
        publication_id=pub_id,
        latest_revision_id=rev_id,
        source_mechanism_text="Turning off conveyers when empty saved 15% power.",
        analytical_mechanism_category_id="idle_time_reduction",
        is_review_synthesized=False,
        approval_state=ClassificationApprovalState.APPROVED,
        approved_by="reviewer_alpha",
        approved_at=datetime.now(timezone.utc),
        notes="Empirically confirmed in line 2.",
    )
    assert pathway.pathway_id == path_id
    assert pathway.analytical_relation_id == rel_id
    assert pathway.source_mechanism_text == "Turning off conveyers when empty saved 15% power."
    assert pathway.analytical_mechanism_category_id == "idle_time_reduction"
    assert not pathway.is_review_synthesized
    assert pathway.approval_state == ClassificationApprovalState.APPROVED


def test_mechanism_synthesis_pathway_aggregation():
    chain = MechanismSynthesisPathway(
        lean_category_id="5s",
        lean_category_name="5S & Visual Management",
        mechanism_category_id="idle_reduction",
        mechanism_category_name="Idle-Time Reduction",
        energy_category_id="elec",
        energy_category_name="Electricity Consumption",
        pathway_count=3,
        publication_count=2,
        relation_count=3,
        pathways=[],
    )
    assert chain.lean_category_id == "5s"
    assert chain.mechanism_category_id == "idle_reduction"
    assert chain.energy_category_id == "elec"
    assert chain.pathway_count == 3
    assert chain.publication_count == 2
    assert chain.relation_count == 3
