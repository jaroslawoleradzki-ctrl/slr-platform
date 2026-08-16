"""Unit tests for SynthesisExtractionAdapter traceability and QA aggregation."""

from pathlib import Path
from uuid import uuid4

import pytest

from app.adapters.synthesis_extraction_adapter import SynthesisExtractionAdapter
from app.domain.extraction import (
    ExtractedGroupItemState,
    ExtractedValueState,
    ExtractionCompletenessStatus,
    ExtractionRecord,
    ExtractionRevision,
    ExtractionTemplate,
    ExtractionTemplateVersion,
    ValueOrigin,
    ValueStatus,
)
from app.domain.project import Project
from app.domain.quality_assessment import (
    QualityAssessment,
    QualityAssessmentResponse,
    QualityAssessmentResponseValue,
    QualityAssessmentTemplate,
    QualityAssessmentTemplateCriterion,
    QualityAssessmentTool,
)
from app.repositories.extraction_repository import SqliteExtractionRepository
from app.repositories.extraction_template_repository import SqliteExtractionTemplateRepository
from app.repositories.project_repository import SqliteProjectRepository
from app.repositories.sqlite_quality_assessment_repository import (
    SqliteQualityAssessmentCatalogRepository,
    SqliteQualityAssessmentRepository,
)


@pytest.fixture
def test_env(tmp_path: Path):
    db_path = tmp_path / "adapter_test.db"

    # Seed projects
    proj_repo = SqliteProjectRepository(db_path)
    proj_repo.create(Project(project_id="proj-a", title="Project A"))
    proj_repo.create(Project(project_id="proj-b", title="Project B"))

    # Seed template
    template_repo = SqliteExtractionTemplateRepository(db_path)
    template_repo.register_template(ExtractionTemplate(template_id="lean_energy", name="Lean Energy"))
    template_repo.register_version(
        ExtractionTemplateVersion(template_id="lean_energy", version="1.0.0", name="v1", is_published=True)
    )

    extraction_repo = SqliteExtractionRepository(db_path)
    qa_repo = SqliteQualityAssessmentRepository(db_path)

    pub_a = uuid4()
    rec_a = extraction_repo.create_record(
        ExtractionRecord(project_id="proj-a", publication_id=pub_a, template_id="lean_energy", template_version="1.0.0")
    )

    group_id_1 = uuid4()

    # Revision 1 in Project A
    rev1 = ExtractionRevision(
        record_id=rec_a.record_id,
        project_id="proj-a",
        publication_id=pub_a,
        revision_index=1,
        reviewer_id="reviewer-1",
        completeness_status=ExtractionCompletenessStatus.IN_PROGRESS,
        publication_values=[
            ExtractedValueState(
                field_key="study_title",
                status=ValueStatus.PRESENT,
                origin=ValueOrigin.REPORTED,
                text_value="Study 1 Title",
                source_locator="Table 1",
            )
        ],
        group_items=[
            ExtractedGroupItemState(
                group_item_id=group_id_1,
                group_key="lean_ee_relationships",
                item_index=1,
                values=[
                    ExtractedValueState(
                        field_key="practice", status=ValueStatus.PRESENT, origin=ValueOrigin.REPORTED, text_value="5S",
                        source_locator="Table 1",
                    )
                ],
            )
        ],
    )
    extraction_repo.append_revision(rev1)

    # Revision 2 in Project A (Same group_item_id with updated practice)
    rev2 = ExtractionRevision(
        record_id=rec_a.record_id,
        project_id="proj-a",
        publication_id=pub_a,
        revision_index=2,
        reviewer_id="reviewer-1",
        completeness_status=ExtractionCompletenessStatus.COMPLETE,
        publication_values=[
            ExtractedValueState(
                field_key="study_title",
                status=ValueStatus.PRESENT,
                origin=ValueOrigin.REPORTED,
                text_value="Study 1 Title (Updated)",
                source_locator="Table 1",
            )
        ],
        group_items=[
            ExtractedGroupItemState(
                group_item_id=group_id_1,
                group_key="lean_ee_relationships",
                item_index=1,
                values=[
                    ExtractedValueState(
                        field_key="practice",
                        status=ValueStatus.PRESENT,
                        origin=ValueOrigin.REPORTED,
                        text_value="5S Advanced",
                        source_locator="Table 1",
                    )
                ],
            )
        ],
    )
    extraction_repo.append_revision(rev2)

    return {
        "db_path": db_path,
        "extraction_repo": extraction_repo,
        "qa_repo": qa_repo,
        "pub_a": pub_a,
        "rev1_id": rev1.revision_id,
        "rev2_id": rev2.revision_id,
        "group_id_1": group_id_1,
    }


def test_resolve_repeating_group_evidence_traceability(test_env):
    adapter = SynthesisExtractionAdapter(test_env["extraction_repo"], test_env["qa_repo"])

    # 1. Resolve against latest revision
    ref_latest = adapter.resolve_relation_traceability(
        project_id="proj-a", publication_id=test_env["pub_a"], group_item_id=test_env["group_id_1"]
    )
    assert ref_latest.project_id == "proj-a"
    assert ref_latest.publication_id == test_env["pub_a"]
    assert ref_latest.revision_id == test_env["rev2_id"]
    assert ref_latest.group_item_id == test_env["group_id_1"]
    assert ref_latest.group_key == "lean_ee_relationships"

    # 2. Resolve against specific historical revision
    ref_rev1 = adapter.resolve_relation_traceability(
        project_id="proj-a",
        publication_id=test_env["pub_a"],
        group_item_id=test_env["group_id_1"],
        revision_id=test_env["rev1_id"],
    )
    assert ref_rev1.revision_id == test_env["rev1_id"]
    assert ref_rev1.group_item_id == test_env["group_id_1"]


def test_resolve_publication_level_evidence_traceability(test_env):
    adapter = SynthesisExtractionAdapter(test_env["extraction_repo"], test_env["qa_repo"])

    # Latest revision
    ref = adapter.resolve_publication_evidence_traceability(
        project_id="proj-a", publication_id=test_env["pub_a"], field_key="study_title"
    )
    assert ref.project_id == "proj-a"
    assert ref.publication_id == test_env["pub_a"]
    assert ref.field_key == "study_title"
    assert ref.group_item_id is None

    # Historical revision
    ref_hist = adapter.resolve_publication_evidence_traceability(
        project_id="proj-a", publication_id=test_env["pub_a"], field_key="study_title", revision_id=test_env["rev1_id"]
    )
    assert ref_hist.revision_id == test_env["rev1_id"]


def test_rejection_of_cross_project_or_nonexistent_references(test_env):
    adapter = SynthesisExtractionAdapter(test_env["extraction_repo"], test_env["qa_repo"])

    # Non-existent publication
    with pytest.raises(ValueError, match="No extraction revisions found"):
        adapter.resolve_relation_traceability(
            project_id="proj-a", publication_id=uuid4(), group_item_id=test_env["group_id_1"]
        )

    # Cross-project request (proj-b does not own pub_a)
    with pytest.raises(ValueError, match="No extraction revisions found"):
        adapter.resolve_relation_traceability(
            project_id="proj-b", publication_id=test_env["pub_a"], group_item_id=test_env["group_id_1"]
        )

    # Non-existent group item
    with pytest.raises(ValueError, match="Group item .* not found"):
        adapter.resolve_relation_traceability(
            project_id="proj-a", publication_id=test_env["pub_a"], group_item_id=uuid4()
        )

    # Non-existent revision_id in history
    with pytest.raises(ValueError, match="Extraction revision .* not found"):
        adapter.resolve_relation_traceability(
            project_id="proj-a",
            publication_id=test_env["pub_a"],
            group_item_id=test_env["group_id_1"],
            revision_id=uuid4(),
        )

    # Publication evidence: non-existent field
    with pytest.raises(ValueError, match="Field .* not found in publication values"):
        adapter.resolve_publication_evidence_traceability(
            project_id="proj-a", publication_id=test_env["pub_a"], field_key="nonexistent_field"
        )

    # Publication evidence: non-existent revision_id in history
    with pytest.raises(ValueError, match="Extraction revision .* not found"):
        adapter.resolve_publication_evidence_traceability(
            project_id="proj-a", publication_id=test_env["pub_a"], field_key="study_title", revision_id=uuid4()
        )

    # Publication evidence: non-existent publication
    with pytest.raises(ValueError, match="No extraction revisions found"):
        adapter.resolve_publication_evidence_traceability(
            project_id="proj-a", publication_id=uuid4(), field_key="study_title"
        )

    # Cross-project mismatch on returned revision (mock/isolated check)
    from unittest.mock import MagicMock
    mock_repo = MagicMock()
    mock_rev = MagicMock()
    mock_rev.project_id = "proj-mismatch"
    mock_repo.get_latest_revision.return_value = mock_rev

    mismatch_adapter = SynthesisExtractionAdapter(mock_repo, None)
    with pytest.raises(ValueError, match="Cross-project isolation violation"):
        mismatch_adapter.resolve_relation_traceability(
            project_id="proj-a", publication_id=test_env["pub_a"], group_item_id=test_env["group_id_1"]
        )

    with pytest.raises(ValueError, match="Cross-project isolation violation"):
        mismatch_adapter.resolve_publication_evidence_traceability(
            project_id="proj-a", publication_id=test_env["pub_a"], field_key="study_title"
        )


def test_qa_profile_summary_aggregation(test_env):
    qa_repo = test_env["qa_repo"]
    db_path = test_env["db_path"]
    adapter = SynthesisExtractionAdapter(test_env["extraction_repo"], qa_repo)

    # No QA repo returns None
    adapter_no_qa = SynthesisExtractionAdapter(test_env["extraction_repo"], None)
    assert adapter_no_qa.get_qa_profile_summary("proj-a", test_env["pub_a"]) is None

    # Assessment not yet saved returns None
    assert adapter.get_qa_profile_summary("proj-a", test_env["pub_a"], reviewer_id="reviewer-1") is None

    # Seed tool, template, and criterion
    catalog_repo = SqliteQualityAssessmentCatalogRepository(db_path)
    tool = QualityAssessmentTool(tool_id="casp_qa", name="CASP QA", description="CASP tool")
    catalog_repo.create_tool(tool)

    tid = uuid4()
    crit_id = uuid4()
    criterion = QualityAssessmentTemplateCriterion(
        criterion_id=crit_id,
        template_id=tid,
        display_order=1,
        question="Is the baseline energy measurement clearly reported?",
        guidance="Check table 1",
    )
    template = QualityAssessmentTemplate(
        template_id=tid,
        tool_id="casp_qa",
        template_key="lean_qa",
        name="Lean QA Template",
        version=1,
        is_active=True,
        criteria=[criterion],
    )
    catalog_repo.create_template_version(template)

    # Seed a QA assessment in Phase 8
    assessment_id = uuid4()
    assessment = QualityAssessment(
        assessment_id=assessment_id,
        project_id="proj-a",
        publication_id=test_env["pub_a"],
        reviewer_id="reviewer-1",
        template_id=tid,
        responses=[
            QualityAssessmentResponse(
                assessment_id=assessment_id,
                criterion_id=crit_id,
                question_snapshot="Is the baseline energy measurement clearly reported?",
                response_value=QualityAssessmentResponseValue.YES,
                justification="Reported in table 1 with kW values",
            )
        ],
    )
    qa_repo.save_assessment(assessment)

    # Aggregate profile via adapter
    profile = adapter.get_qa_profile_summary("proj-a", test_env["pub_a"], reviewer_id="reviewer-1")
    assert profile is not None
    assert profile.reviewer_id == "reviewer-1"
    assert len(profile.criteria_assessments) == 1
    assert profile.criteria_assessments[0].response_value == "YES"
    assert "Reported in table 1" in profile.criteria_assessments[0].justification
