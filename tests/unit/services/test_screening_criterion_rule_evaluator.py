from uuid import UUID

import pytest
from pydantic import ValidationError

from app.domain.identifiers import Identifier, IdentifierType
from app.domain.publication import DocumentType, Publication
from app.domain.screening import (
    CriterionAssessmentValue,
    MetadataRule,
    ScreeningCriterion,
    ScreeningCriterionEvaluationMode,
    ScreeningCriterionStage,
    ScreeningCriterionType,
)
from app.services.screening_criterion_rule_evaluator import ScreeningCriterionRuleEvaluator


def _criterion(rule: MetadataRule) -> ScreeningCriterion:
    return ScreeningCriterion(
        criterion_id=UUID("00000000-0000-0000-0000-000000000001"),
        project_id="lean_energy",
        name="Automatic metadata rule",
        criterion_type=ScreeningCriterionType.INCLUSION,
        screening_stage=ScreeningCriterionStage.TITLE_ABSTRACT,
        evaluation_mode=ScreeningCriterionEvaluationMode.METADATA_RULE,
        metadata_rule=rule,
    )


@pytest.mark.parametrize(
    ("rule", "expected"),
    [
        (MetadataRule(field="publication_year", operator="greater_than", value=2021), CriterionAssessmentValue.MET),
        (MetadataRule(field="publication_year", operator="greater_than_or_equal", value=2024), CriterionAssessmentValue.MET),
        (MetadataRule(field="publication_year", operator="less_than", value=2025), CriterionAssessmentValue.MET),
        (MetadataRule(field="publication_year", operator="equals", value=2024), CriterionAssessmentValue.MET),
        (MetadataRule(field="publication_year", operator="not_equals", value=2024), CriterionAssessmentValue.NOT_MET),
        (MetadataRule(field="language", operator="in", value=["en", "pl"]), CriterionAssessmentValue.MET),
        (MetadataRule(field="language", operator="not_in", value=["de"]), CriterionAssessmentValue.MET),
        (MetadataRule(field="abstract", operator="exists"), CriterionAssessmentValue.MET),
        (MetadataRule(field="abstract", operator="not_exists"), CriterionAssessmentValue.NOT_MET),
        (MetadataRule(field="doi", operator="exists"), CriterionAssessmentValue.MET),
        (MetadataRule(field="open_access", operator="equals", value=True), CriterionAssessmentValue.MET),
        (MetadataRule(field="document_type", operator="equals", value="journal_article"), CriterionAssessmentValue.MET),
    ],
)
def test_evaluator_supports_allow_listed_metadata_rules(rule: MetadataRule, expected: CriterionAssessmentValue) -> None:
    publication = Publication(
        title="Record",
        publication_year=2024,
        language="en",
        abstract="Stored abstract",
        identifiers=[Identifier(type=IdentifierType.DOI, value="10.1000/example")],
        open_access=True,
        document_type=DocumentType.JOURNAL_ARTICLE,
    )
    result = ScreeningCriterionRuleEvaluator().evaluate(_criterion(rule), publication)
    assert result.assessment_value is expected


def test_missing_metadata_is_not_assessed_and_not_silently_met() -> None:
    result = ScreeningCriterionRuleEvaluator().evaluate(
        _criterion(MetadataRule(field="publication_year", operator="greater_than", value=2021)),
        Publication(title="No year"),
    )
    assert result.assessment_value is CriterionAssessmentValue.NOT_ASSESSED
    assert result.evaluated_metadata_value is None


@pytest.mark.parametrize(
    "payload",
    [
        {"field": "publication_year", "operator": "greater_than", "value": "2021"},
        {"field": "language", "operator": "greater_than", "value": "en"},
        {"field": "abstract", "operator": "equals", "value": "anything"},
        {"field": "open_access", "operator": "equals", "value": "true"},
        {"field": "not_a_publication_field", "operator": "equals", "value": "x"},
    ],
)
def test_rule_validation_rejects_invalid_field_operator_type_combinations(payload: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        MetadataRule.model_validate(payload)


def test_criterion_type_does_not_reverse_automatic_result() -> None:
    rule = MetadataRule(field="publication_year", operator="greater_than", value=2021)
    criterion = _criterion(rule).model_copy(update={"criterion_type": ScreeningCriterionType.EXCLUSION})
    result = ScreeningCriterionRuleEvaluator().evaluate(criterion, Publication(title="Record", publication_year=2024))
    assert result.assessment_value is CriterionAssessmentValue.MET


def test_manual_and_automatic_criterion_configuration_is_mutually_exclusive() -> None:
    rule = MetadataRule(field="abstract", operator="exists")
    with pytest.raises(ValidationError):
        ScreeningCriterion(
            project_id="lean_energy",
            name="Invalid manual rule",
            criterion_type=ScreeningCriterionType.INCLUSION,
            screening_stage=ScreeningCriterionStage.TITLE_ABSTRACT,
            evaluation_mode=ScreeningCriterionEvaluationMode.MANUAL,
            metadata_rule=rule,
        )
