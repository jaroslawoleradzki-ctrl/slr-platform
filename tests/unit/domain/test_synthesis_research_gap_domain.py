"""Unit tests for Phase 10 Task 10.6 Research Gap Domain Models."""

from datetime import datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.domain.synthesis import (
    ResearchGap,
    ResearchGapDetail,
    ResearchGapLink,
    ResearchGapLinkType,
    ResearchGapType,
    ResearchGapWorkspaceData,
    ResearchGapWorkspaceStats,
)


def test_research_gap_type_exactly_five_members():
    assert set(ResearchGapType) == {
        ResearchGapType.THEMATIC,
        ResearchGapType.MECHANISM,
        ResearchGapType.METHODOLOGICAL,
        ResearchGapType.CONTEXTUAL,
        ResearchGapType.INCONSISTENT_EVIDENCE,
    }


def test_research_gap_valid():
    gap = ResearchGap(
        project_id="proj_1",
        gap_type=ResearchGapType.METHODOLOGICAL,
        title="Recurring sample size limitation",
        rationale="Across eligible studies, sample sizes were reported too small for subgroup analysis.",
        researcher_id="reviewer_alpha",
    )
    assert gap.gap_id is not None
    assert gap.gap_type == ResearchGapType.METHODOLOGICAL
    assert gap.title == "Recurring sample size limitation"
    assert gap.rationale != ""
    assert gap.created_at.tzinfo is not None
    assert gap.updated_at.tzinfo is not None


def test_research_gap_validation_failures():
    with pytest.raises(ValidationError):
        ResearchGap(project_id="proj_1", gap_type=ResearchGapType.THEMATIC, title="", rationale="R", researcher_id="r")
    with pytest.raises(ValidationError):
        ResearchGap(project_id="proj_1", gap_type=ResearchGapType.THEMATIC, title="T", rationale="", researcher_id="r")
    with pytest.raises(ValidationError):
        ResearchGap(project_id="proj_1", gap_type=ResearchGapType.THEMATIC, title="T", rationale="R", researcher_id="")
    with pytest.raises(ValidationError):
        ResearchGap(
            project_id="proj_1",
            gap_type=ResearchGapType.THEMATIC,
            title="T",
            rationale="R",
            researcher_id="r",
            invented_score=42,
        )
    with pytest.raises(ValidationError):
        ResearchGap(
            project_id="proj_1",
            gap_type=ResearchGapType.THEMATIC,
            title="T",
            rationale="R",
            researcher_id="r",
            created_at=datetime(2024, 1, 1),
        )


def test_research_gap_link_valid():
    rel_id = uuid4()
    link = ResearchGapLink(
        project_id="proj_1",
        gap_id=uuid4(),
        link_type=ResearchGapLinkType.ANALYTICAL_RELATION,
        target_id=rel_id,
        group_item_id=uuid4(),
        publication_id=uuid4(),
        latest_revision_id=uuid4(),
    )
    assert link.link_id is not None
    assert link.link_type == ResearchGapLinkType.ANALYTICAL_RELATION
    assert link.target_id == rel_id
    assert link.created_at.tzinfo is not None


def test_research_gap_link_type_values():
    assert ResearchGapLinkType.ANALYTICAL_RELATION.value == "analytical_relation"
    assert ResearchGapLinkType.MECHANISM_PATHWAY.value == "mechanism_pathway"
    assert ResearchGapLinkType.CONTEXT_FACTOR_LINK.value == "context_factor_link"


def test_research_gap_link_validation_failures():
    with pytest.raises(ValidationError):
        ResearchGapLink(
            project_id="proj_1",
            gap_id=uuid4(),
            link_type="unknown_type",
            target_id=uuid4(),
            group_item_id=uuid4(),
            publication_id=uuid4(),
            latest_revision_id=uuid4(),
        )
    with pytest.raises(ValidationError):
        ResearchGapLink(
            project_id="proj_1",
            gap_id=uuid4(),
            link_type=ResearchGapLinkType.ANALYTICAL_RELATION,
            target_id=uuid4(),
            group_item_id=uuid4(),
            publication_id=uuid4(),
            latest_revision_id=uuid4(),
            gap_strength=0.9,
        )


def test_research_gap_workspace_stats():
    stats = ResearchGapWorkspaceStats(
        total_gaps=3,
        thematic_count=1,
        mechanism_count=1,
        methodological_count=0,
        contextual_count=0,
        inconsistent_evidence_count=1,
        linked_publication_count=2,
    )
    assert stats.total_gaps == 3
    assert stats.inconsistent_evidence_count == 1


def test_research_gap_detail_with_links():
    gap = ResearchGap(project_id="p", gap_type=ResearchGapType.CONTEXTUAL, title="T", rationale="R", researcher_id="r")
    link = ResearchGapLink(
        project_id="p",
        gap_id=gap.gap_id,
        link_type=ResearchGapLinkType.CONTEXT_FACTOR_LINK,
        target_id=uuid4(),
        group_item_id=uuid4(),
        publication_id=uuid4(),
        latest_revision_id=uuid4(),
    )
    detail = ResearchGapDetail(gap=gap, links=[link])
    assert detail.gap.gap_id == gap.gap_id
    assert len(detail.links) == 1


def test_research_gap_workspace_data():
    gap = ResearchGap(project_id="p", gap_type=ResearchGapType.THEMATIC, title="T", rationale="R", researcher_id="r")
    stats = ResearchGapWorkspaceStats(total_gaps=1, thematic_count=1)
    data = ResearchGapWorkspaceData(project_id="p", gaps=[ResearchGapDetail(gap=gap)], stats=stats)
    assert data.project_id == "p"
    assert data.stats.total_gaps == 1
