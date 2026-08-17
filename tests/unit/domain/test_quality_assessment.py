from datetime import timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.domain.quality_assessment import (
    QualityAssessment,
    QualityAssessmentResponse,
    QualityAssessmentResponseValue,
    QualityAssessmentTemplate,
    QualityAssessmentTemplateCriterion,
    QualityAssessmentTool,
)


def test_quality_assessment_response_values():
    assert QualityAssessmentResponseValue.YES == "YES"
    assert QualityAssessmentResponseValue.NO == "NO"
    assert QualityAssessmentResponseValue.CANNOT_DETERMINE == "CANNOT_DETERMINE"


def test_quality_assessment_tool_valid():
    tool = QualityAssessmentTool(
        tool_id="casp_inspired",
        name="CASP-inspired Quality Assessment",
        description="Critical Appraisal Skills Programme based assessment tool",
    )
    assert tool.tool_id == "casp_inspired"
    assert tool.name == "CASP-inspired Quality Assessment"
    assert tool.created_at.tzinfo == timezone.utc


def test_quality_assessment_tool_rejects_blank_fields():
    with pytest.raises(ValidationError, match="text fields must not be blank"):
        QualityAssessmentTool(tool_id="  ", name="Tool")

    with pytest.raises(ValidationError, match="text fields must not be blank"):
        QualityAssessmentTool(tool_id="casp", name="  ")


def test_quality_assessment_template_criterion_validation():
    tid = uuid4()
    c = QualityAssessmentTemplateCriterion(
        template_id=tid,
        display_order=1,
        question="Did the study address a clearly focused issue?",
        guidance="Look for population, intervention, outcomes.",
        is_required=True,
    )
    assert c.template_id == tid
    assert c.display_order == 1
    assert c.is_required is True

    with pytest.raises(ValidationError, match="question must not be blank"):
        QualityAssessmentTemplateCriterion(template_id=tid, question="   ")


def test_quality_assessment_template_ownership_and_uniqueness():
    tid = uuid4()
    c1 = QualityAssessmentTemplateCriterion(template_id=tid, display_order=1, question="Q1?")
    c2 = QualityAssessmentTemplateCriterion(template_id=tid, display_order=2, question="Q2?")

    tmpl = QualityAssessmentTemplate(
        template_id=tid,
        tool_id="casp_inspired",
        template_key="lean_energy",
        name="Lean Energy QA v1",
        version=1,
        criteria=[c1, c2],
    )
    assert len(tmpl.criteria) == 2

    # Wrong template_id in criterion
    other_tid = uuid4()
    c_wrong = QualityAssessmentTemplateCriterion(template_id=other_tid, display_order=3, question="Q3?")
    with pytest.raises(ValidationError, match="does not match template_id"):
        QualityAssessmentTemplate(
            template_id=tid,
            tool_id="casp_inspired",
            template_key="lean_energy",
            name="Lean Energy QA v1",
            version=1,
            criteria=[c1, c_wrong],
        )

    # Duplicate display_order
    c_dup_order = QualityAssessmentTemplateCriterion(template_id=tid, display_order=1, question="Q3?")
    with pytest.raises(ValidationError, match="Duplicate display_order"):
        QualityAssessmentTemplate(
            template_id=tid,
            tool_id="casp_inspired",
            template_key="lean_energy",
            name="Lean Energy QA v1",
            version=1,
            criteria=[c1, c_dup_order],
        )


def test_quality_assessment_response_and_assessment_validation():
    aid = uuid4()
    cid1 = uuid4()
    cid2 = uuid4()
    pid = uuid4()
    tid = uuid4()

    r1 = QualityAssessmentResponse(
        assessment_id=aid,
        criterion_id=cid1,
        question_snapshot="Did the study address a clearly focused issue?",
        guidance_snapshot="Check population and outcome",
        is_required_snapshot=True,
        response_value=QualityAssessmentResponseValue.YES,
        justification="The research question is explicitly stated in Section 1.2.",
    )
    r2 = QualityAssessmentResponse(
        assessment_id=aid,
        criterion_id=cid2,
        question_snapshot="Was the cohort recruited in an acceptable way?",
        guidance_snapshot=None,
        is_required_snapshot=True,
        response_value=QualityAssessmentResponseValue.NO,
        justification="Recruitment protocol had severe selection bias.",
    )

    assessment = QualityAssessment(
        assessment_id=aid,
        project_id="lean_energy",
        publication_id=pid,
        reviewer_id="reviewer_jarek",
        template_id=tid,
        responses=[r1, r2],
    )
    assert assessment.project_id == "lean_energy"
    assert len(assessment.responses) == 2

    # Duplicate criterion_id response in same assessment
    r_dup = QualityAssessmentResponse(
        assessment_id=aid,
        criterion_id=cid1,
        question_snapshot="Q1",
        response_value=QualityAssessmentResponseValue.YES,
        justification="Duplicate",
    )
    with pytest.raises(ValidationError, match="Duplicate response for criterion_id"):
        QualityAssessment(
            assessment_id=aid,
            project_id="lean_energy",
            publication_id=pid,
            reviewer_id="reviewer_jarek",
            template_id=tid,
            responses=[r1, r_dup],
        )


def test_quality_assessment_justification_rules():
    aid = uuid4()
    cid = uuid4()

    # 1. YES with empty justification is valid
    r_yes_empty = QualityAssessmentResponse(
        assessment_id=aid,
        criterion_id=cid,
        question_snapshot="Is there a clear objective?",
        response_value=QualityAssessmentResponseValue.YES,
        justification="",
    )
    assert r_yes_empty.justification == ""

    # 2. YES with default justification is valid
    r_yes_default = QualityAssessmentResponse(
        assessment_id=aid,
        criterion_id=cid,
        question_snapshot="Is there a clear objective?",
        response_value=QualityAssessmentResponseValue.YES,
    )
    assert r_yes_default.justification == ""

    # 3. NO with empty justification raises ValidationError
    with pytest.raises(ValidationError, match="Non-blank justification required"):
        QualityAssessmentResponse(
            assessment_id=aid,
            criterion_id=cid,
            question_snapshot="Is there a clear objective?",
            response_value=QualityAssessmentResponseValue.NO,
            justification="",
        )

    # 4. CANNOT_DETERMINE with empty justification raises ValidationError
    with pytest.raises(ValidationError, match="Non-blank justification required"):
        QualityAssessmentResponse(
            assessment_id=aid,
            criterion_id=cid,
            question_snapshot="Is there a clear objective?",
            response_value=QualityAssessmentResponseValue.CANNOT_DETERMINE,
            justification="   ",
        )

    # 5. NO with non-blank justification is valid
    r_no = QualityAssessmentResponse(
        assessment_id=aid,
        criterion_id=cid,
        question_snapshot="Is there a clear objective?",
        response_value=QualityAssessmentResponseValue.NO,
        justification="No objective found.",
    )
    assert r_no.justification == "No objective found."
