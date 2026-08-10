from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.domain.identifiers import IdentifierType
from app.domain.publication import Publication
from app.domain.screening import (
    CriterionAssessmentValue,
    MetadataRuleField,
    MetadataRuleOperator,
    MetadataRuleValue,
    ScreeningCriterion,
    ScreeningCriterionEvaluationMode,
)


@dataclass(frozen=True, slots=True)
class MetadataRuleEvaluation:
    """Reproducible result of evaluating one metadata rule for one publication."""

    assessment_value: CriterionAssessmentValue
    evaluated_metadata_value: MetadataRuleValue | None


class ScreeningCriterionRuleEvaluator:
    """Pure deterministic evaluator for safe, allow-listed publication metadata rules."""

    def evaluate(
        self, criterion: ScreeningCriterion, publication: Publication
    ) -> MetadataRuleEvaluation:
        if criterion.evaluation_mode is not ScreeningCriterionEvaluationMode.METADATA_RULE:
            raise ValueError("only metadata_rule criteria can be evaluated automatically")
        rule = criterion.metadata_rule
        if rule is None:  # Defensive guard for callers outside Pydantic validation.
            raise ValueError("metadata_rule criterion requires a metadata rule")

        actual = self._value(publication, rule.field)
        if rule.operator is MetadataRuleOperator.EXISTS:
            return MetadataRuleEvaluation(
                CriterionAssessmentValue.MET if actual is not None else CriterionAssessmentValue.NOT_MET,
                actual,
            )
        if rule.operator is MetadataRuleOperator.NOT_EXISTS:
            return MetadataRuleEvaluation(
                CriterionAssessmentValue.MET if actual is None else CriterionAssessmentValue.NOT_MET,
                actual,
            )
        if actual is None:
            return MetadataRuleEvaluation(CriterionAssessmentValue.NOT_ASSESSED, None)

        # MetadataRule performs field/operator/type validation at construction.
        # `Any` keeps the comparison implementation readable without weakening
        # that external contract or accepting arbitrary fields/operators.
        comparable_actual: Any = actual
        expected: Any = rule.value
        if rule.operator is MetadataRuleOperator.EQUALS:
            matched = comparable_actual == expected
        elif rule.operator is MetadataRuleOperator.NOT_EQUALS:
            matched = comparable_actual != expected
        elif rule.operator is MetadataRuleOperator.IN:
            matched = comparable_actual in expected  # validated as a list by MetadataRule
        elif rule.operator is MetadataRuleOperator.NOT_IN:
            matched = comparable_actual not in expected  # validated as a list by MetadataRule
        elif rule.operator is MetadataRuleOperator.GREATER_THAN:
            matched = comparable_actual > expected
        elif rule.operator is MetadataRuleOperator.GREATER_THAN_OR_EQUAL:
            matched = comparable_actual >= expected
        elif rule.operator is MetadataRuleOperator.LESS_THAN:
            matched = comparable_actual < expected
        elif rule.operator is MetadataRuleOperator.LESS_THAN_OR_EQUAL:
            matched = comparable_actual <= expected
        else:  # MetadataRule validation makes this unreachable.
            raise ValueError(f"unsupported metadata rule operator '{rule.operator.value}'")
        return MetadataRuleEvaluation(
            CriterionAssessmentValue.MET if matched else CriterionAssessmentValue.NOT_MET,
            actual,
        )

    @staticmethod
    def _value(publication: Publication, field: MetadataRuleField) -> MetadataRuleValue | None:
        if field is MetadataRuleField.PUBLICATION_YEAR:
            return publication.publication_year
        if field is MetadataRuleField.LANGUAGE:
            return publication.language
        if field is MetadataRuleField.DOCUMENT_TYPE:
            return publication.document_type.value if publication.document_type is not None else None
        if field is MetadataRuleField.OPEN_ACCESS:
            return publication.open_access
        if field is MetadataRuleField.DOI:
            return next(
                (item.value for item in publication.identifiers if item.type is IdentifierType.DOI),
                None,
            )
        if field is MetadataRuleField.ABSTRACT:
            return publication.abstract.strip() if publication.abstract and publication.abstract.strip() else None
        raise ValueError(f"unsupported metadata rule field '{field.value}'")
