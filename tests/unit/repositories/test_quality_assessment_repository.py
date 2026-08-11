import sqlite3
from pathlib import Path
from uuid import uuid4

import pytest

from app.domain.quality_assessment import (
    QualityAssessment,
    QualityAssessmentResponse,
    QualityAssessmentResponseValue,
    QualityAssessmentTemplate,
    QualityAssessmentTemplateCriterion,
    QualityAssessmentTool,
)
from app.repositories.quality_assessment_repository import (
    QualityAssessmentCatalogRepository,
    QualityAssessmentRepository,
)
from app.repositories.sqlite_quality_assessment_repository import (
    SqliteQualityAssessmentCatalogRepository,
    SqliteQualityAssessmentRepository,
    TemplateVersionNotFoundError,
)


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "test_qa.db"


def test_repository_protocols_runtime_checkable():
    assert isinstance(SqliteQualityAssessmentCatalogRepository("dummy"), QualityAssessmentCatalogRepository)
    assert isinstance(SqliteQualityAssessmentRepository("dummy"), QualityAssessmentRepository)


def test_sqlite_repository_automatically_applies_0013_migration(tmp_path: Path):
    db = tmp_path / "auto_migration.db"
    # Instantiate repository without pre-created tables
    _ = SqliteQualityAssessmentCatalogRepository(db)

    # Check schema_migrations table contains 0013_quality_assessment.sql
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    applied = {row[0] for row in conn.execute("SELECT version FROM schema_migrations")}
    assert "0013_quality_assessment.sql" in applied

    # Check 0013 tables exist
    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "quality_assessment_tools" in tables
    assert "quality_assessment_templates" in tables
    assert "quality_assessment_template_criteria" in tables
    assert "quality_assessments" in tables
    assert "quality_assessment_responses" in tables
    conn.close()


def test_catalog_repository_tools_and_templates(db_path: Path):
    catalog_repo = SqliteQualityAssessmentCatalogRepository(db_path)

    tool = QualityAssessmentTool(
        tool_id="casp_inspired",
        name="CASP-inspired Tool",
        description="Critical Appraisal Skills Programme",
    )
    catalog_repo.create_tool(tool)

    fetched_tool = catalog_repo.get_tool("casp_inspired")
    assert fetched_tool is not None
    assert fetched_tool.name == "CASP-inspired Tool"

    tid1 = uuid4()
    c1 = QualityAssessmentTemplateCriterion(template_id=tid1, display_order=0, question="Q1?", guidance="G1")
    c2 = QualityAssessmentTemplateCriterion(template_id=tid1, display_order=1, question="Q2?", guidance=None)

    template_v1 = QualityAssessmentTemplate(
        template_id=tid1,
        tool_id="casp_inspired",
        template_key="lean_energy",
        name="Lean Energy QA v1",
        version=1,
        description="Version 1",
        is_active=True,
        criteria=[c1, c2],
    )
    catalog_repo.create_template_version(template_v1)

    fetched_tmpl = catalog_repo.get_template_version(tid1)
    assert fetched_tmpl is not None
    assert fetched_tmpl.template_key == "lean_energy"
    assert fetched_tmpl.version == 1
    assert len(fetched_tmpl.criteria) == 2
    assert fetched_tmpl.criteria[0].question == "Q1?"

    by_key = catalog_repo.get_template_version_by_key("casp_inspired", "lean_energy", 1)
    assert by_key is not None
    assert by_key.template_id == tid1


def test_template_unique_constraint_allows_multiple_templates_same_version(db_path: Path):
    catalog_repo = SqliteQualityAssessmentCatalogRepository(db_path)

    tool = QualityAssessmentTool(tool_id="casp_inspired", name="CASP Tool")
    catalog_repo.create_tool(tool)

    tid1 = uuid4()
    tid2 = uuid4()

    t_lean = QualityAssessmentTemplate(
        template_id=tid1,
        tool_id="casp_inspired",
        template_key="lean_energy",
        name="Lean Energy QA v1",
        version=1,
    )
    t_health = QualityAssessmentTemplate(
        template_id=tid2,
        tool_id="casp_inspired",
        template_key="healthcare",
        name="Healthcare QA v1",
        version=1,
    )

    catalog_repo.create_template_version(t_lean)
    catalog_repo.create_template_version(t_health)

    versions = catalog_repo.list_template_versions(tool_id="casp_inspired")
    assert len(versions) == 2
    keys = {v.template_key for v in versions}
    assert keys == {"lean_energy", "healthcare"}


def test_template_immutability_and_is_active_mutation_semantics(db_path: Path):
    """Verifies that published template content is immutable and only is_active can be mutated."""
    catalog_repo = SqliteQualityAssessmentCatalogRepository(db_path)

    # 1. Assert protocol interface does not expose update_template_version
    assert not hasattr(QualityAssessmentCatalogRepository, "update_template_version")
    assert not hasattr(QualityAssessmentCatalogRepository, "update_criterion")

    tool = QualityAssessmentTool(tool_id="casp_inspired", name="CASP Tool")
    catalog_repo.create_tool(tool)

    tid = uuid4()
    c1 = QualityAssessmentTemplateCriterion(template_id=tid, display_order=0, question="Original Question?")
    tmpl = QualityAssessmentTemplate(
        template_id=tid,
        tool_id="casp_inspired",
        template_key="lean_energy",
        name="Lean Energy QA v1",
        version=1,
        is_active=True,
        criteria=[c1],
    )
    catalog_repo.create_template_version(tmpl)

    # 2. Deactivate template version (mutable lifecycle metadata update)
    catalog_repo.set_template_version_active(tid, False)

    updated_tmpl = catalog_repo.get_template_version(tid)
    assert updated_tmpl is not None
    assert updated_tmpl.is_active is False
    # Content remains completely unchanged
    assert updated_tmpl.name == "Lean Energy QA v1"
    assert updated_tmpl.criteria[0].question == "Original Question?"

    # Non-existent template raises error
    with pytest.raises(TemplateVersionNotFoundError):
        catalog_repo.set_template_version_active(uuid4(), True)


def test_quality_assessment_rejects_cross_template_criterion(db_path: Path):
    """Regression test: save_assessment MUST reject criterion_id belonging to a different template."""
    catalog_repo = SqliteQualityAssessmentCatalogRepository(db_path)
    qa_repo = SqliteQualityAssessmentRepository(db_path)

    tool = QualityAssessmentTool(tool_id="casp_inspired", name="CASP Tool")
    catalog_repo.create_tool(tool)

    # Template A with criterion A1
    tid_a = uuid4()
    cid_a1 = uuid4()
    c_a1 = QualityAssessmentTemplateCriterion(criterion_id=cid_a1, template_id=tid_a, display_order=0, question="Q_A1?")
    tmpl_a = QualityAssessmentTemplate(
        template_id=tid_a,
        tool_id="casp_inspired",
        template_key="template_a",
        name="Template A v1",
        version=1,
        criteria=[c_a1],
    )
    catalog_repo.create_template_version(tmpl_a)

    # Template B with criterion B1
    tid_b = uuid4()
    cid_b1 = uuid4()
    c_b1 = QualityAssessmentTemplateCriterion(criterion_id=cid_b1, template_id=tid_b, display_order=0, question="Q_B1?")
    tmpl_b = QualityAssessmentTemplate(
        template_id=tid_b,
        tool_id="casp_inspired",
        template_key="template_b",
        name="Template B v1",
        version=1,
        criteria=[c_b1],
    )
    catalog_repo.create_template_version(tmpl_b)

    # Assessment declared with template_id = Template A, but response uses criterion_id = B1
    pid = uuid4()
    aid = uuid4()
    r_cross = QualityAssessmentResponse(
        assessment_id=aid,
        criterion_id=cid_b1, # Belongs to Template B, NOT Template A!
        question_snapshot="Q_B1?",
        response_value=QualityAssessmentResponseValue.YES,
        justification="Cross-template criterion attempt",
    )
    assessment = QualityAssessment(
        assessment_id=aid,
        project_id="lean_energy",
        publication_id=pid,
        reviewer_id="reviewer_jarek",
        template_id=tid_a, # Template A
        responses=[r_cross],
    )

    with pytest.raises(sqlite3.IntegrityError, match="belongs to template"):
        qa_repo.save_assessment(assessment)


def test_quality_assessment_append_only_history_and_snapshots(db_path: Path):
    catalog_repo = SqliteQualityAssessmentCatalogRepository(db_path)
    qa_repo = SqliteQualityAssessmentRepository(db_path)

    tool = QualityAssessmentTool(tool_id="casp_inspired", name="CASP Tool")
    catalog_repo.create_tool(tool)

    tid = uuid4()
    cid1 = uuid4()
    c1 = QualityAssessmentTemplateCriterion(
        criterion_id=cid1,
        template_id=tid,
        display_order=0,
        question="Did the study address a clearly focused issue?",
        guidance="Check population and outcome",
        is_required=True,
    )
    tmpl = QualityAssessmentTemplate(
        template_id=tid,
        tool_id="casp_inspired",
        template_key="lean_energy",
        name="Lean Energy QA v1",
        version=1,
        criteria=[c1],
    )
    catalog_repo.create_template_version(tmpl)

    pid = uuid4()
    aid1 = uuid4()
    r1 = QualityAssessmentResponse(
        assessment_id=aid1,
        criterion_id=cid1,
        question_snapshot="Did the study address a clearly focused issue?",
        guidance_snapshot="Check population and outcome",
        is_required_snapshot=True,
        response_value=QualityAssessmentResponseValue.YES,
        justification="First assessment: Explicit question in intro.",
    )
    assessment1 = QualityAssessment(
        assessment_id=aid1,
        project_id="lean_energy",
        publication_id=pid,
        reviewer_id="reviewer_jarek",
        template_id=tid,
        responses=[r1],
    )
    qa_repo.save_assessment(assessment1)

    latest = qa_repo.get_latest_assessment("lean_energy", pid, "reviewer_jarek")
    assert latest is not None
    assert latest.assessment_id == aid1
    assert latest.responses[0].response_value == QualityAssessmentResponseValue.YES

    # Save a second assessment (append-only update)
    aid2 = uuid4()
    r2 = QualityAssessmentResponse(
        assessment_id=aid2,
        criterion_id=cid1,
        question_snapshot="Did the study address a clearly focused issue?",
        guidance_snapshot="Check population and outcome",
        is_required_snapshot=True,
        response_value=QualityAssessmentResponseValue.NO,
        justification="Second assessment: Revised decision after methodology review.",
    )
    assessment2 = QualityAssessment(
        assessment_id=aid2,
        project_id="lean_energy",
        publication_id=pid,
        reviewer_id="reviewer_jarek",
        template_id=tid,
        responses=[r2],
    )
    qa_repo.save_assessment(assessment2)

    # Latest should now be assessment 2
    latest2 = qa_repo.get_latest_assessment("lean_energy", pid, "reviewer_jarek")
    assert latest2 is not None
    assert latest2.assessment_id == aid2
    assert latest2.responses[0].response_value == QualityAssessmentResponseValue.NO

    # History list should return both assessments ordered newest-first
    history = qa_repo.list_assessments_for_publication("lean_energy", pid, "reviewer_jarek")
    assert len(history) == 2
    assert history[0].assessment_id == aid2
    assert history[1].assessment_id == aid1


def test_quality_assessment_foreign_key_and_project_hard_delete(db_path: Path):
    catalog_repo = SqliteQualityAssessmentCatalogRepository(db_path)
    qa_repo = SqliteQualityAssessmentRepository(db_path)

    tool = QualityAssessmentTool(tool_id="casp_inspired", name="CASP Tool")
    catalog_repo.create_tool(tool)

    tid = uuid4()
    cid = uuid4()
    c1 = QualityAssessmentTemplateCriterion(criterion_id=cid, template_id=tid, display_order=0, question="Q1?")
    tmpl = QualityAssessmentTemplate(
        template_id=tid,
        tool_id="casp_inspired",
        template_key="lean_energy",
        name="Lean Energy QA v1",
        version=1,
        criteria=[c1],
    )
    catalog_repo.create_template_version(tmpl)

    pid = uuid4()
    aid = uuid4()
    r1 = QualityAssessmentResponse(
        assessment_id=aid,
        criterion_id=cid,
        question_snapshot="Q1?",
        response_value=QualityAssessmentResponseValue.YES,
        justification="Valid FK criterion_id",
    )
    assessment = QualityAssessment(
        assessment_id=aid,
        project_id="lean_energy",
        publication_id=pid,
        reviewer_id="reviewer_jarek",
        template_id=tid,
        responses=[r1],
    )
    qa_repo.save_assessment(assessment)

    # Test FK constraint failure when criterion_id does not exist
    aid_bad = uuid4()
    r_bad = QualityAssessmentResponse(
        assessment_id=aid_bad,
        criterion_id=uuid4(), # non-existent criterion_id
        question_snapshot="Q_bad",
        response_value=QualityAssessmentResponseValue.YES,
        justification="Invalid FK",
    )
    bad_assessment = QualityAssessment(
        assessment_id=aid_bad,
        project_id="lean_energy",
        publication_id=pid,
        reviewer_id="reviewer_jarek",
        template_id=tid,
        responses=[r_bad],
    )
    with pytest.raises(sqlite3.IntegrityError):
        qa_repo.save_assessment(bad_assessment)

    # Test delete_for_project cleans project assessments without affecting catalog tools/templates
    qa_repo.delete_for_project("lean_energy")
    assert qa_repo.get_latest_assessment("lean_energy", pid, "reviewer_jarek") is None
    # Catalog tool and template remain intact
    assert catalog_repo.get_template_version(tid) is not None
    assert catalog_repo.get_tool("casp_inspired") is not None
