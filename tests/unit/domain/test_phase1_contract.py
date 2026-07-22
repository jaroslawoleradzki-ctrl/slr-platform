from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.domain import (
    AIRecommendation,
    Affiliation,
    Author,
    BooleanOperator,
    DocumentType,
    Identifier,
    IdentifierType,
    ProvenanceEntry,
    Publication,
    ScreeningDecision,
    ScreeningOutcome,
    ScreeningStage,
    SearchGroup,
    SearchQuery,
    SearchTerm,
    Venue,
)


def test_canonical_publication_round_trips_through_json() -> None:
    publication = Publication(
        title="Lean manufacturing and energy efficiency",
        authors=[
            Author(
                display_name="Jane Doe",
                affiliations=[Affiliation(name="Example University")],
            )
        ],
        identifiers=[Identifier(type=IdentifierType.DOI, value="10.1000/example")],
        venue=Venue(name="Journal of Cleaner Production"),
        document_type=DocumentType.JOURNAL_ARTICLE,
        provenance=[ProvenanceEntry(source="openalex", source_record_id="W123")],
    )

    restored = Publication.model_validate_json(publication.model_dump_json())

    assert restored == publication
    assert restored.record_id == publication.record_id


def test_nested_search_query_round_trips_and_keeps_boolean_meaning() -> None:
    expression = SearchGroup(
        operator=BooleanOperator.AND,
        children=[
            SearchGroup(
                operator=BooleanOperator.OR,
                children=[
                    SearchTerm(value="lean manufacturing", exact_phrase=True),
                    SearchTerm(value="lean production", exact_phrase=True),
                ],
            ),
            SearchGroup(
                operator=BooleanOperator.OR,
                children=[
                    SearchTerm(value="energy efficiency", exact_phrase=True),
                    SearchTerm(value="energy consumption", exact_phrase=True),
                ],
            ),
            SearchGroup(
                operator=BooleanOperator.NOT,
                children=[SearchTerm(value="healthcare")],
            ),
        ],
    )
    query = SearchQuery(name="Lean and energy", expression=expression)

    restored = SearchQuery.model_validate_json(query.model_dump_json())

    assert restored == query
    assert restored.to_boolean_query() == (
        '(("lean manufacturing" OR "lean production") AND '
        '("energy efficiency" OR "energy consumption") AND NOT (healthcare))'
    )


def test_human_screening_decision_and_ai_recommendation_remain_separate() -> None:
    recommendation = AIRecommendation(
        outcome=ScreeningOutcome.EXCLUDE,
        confidence=0.82,
        model_name="screening-model",
        rationale="The abstract does not concern manufacturing.",
    )
    decision = ScreeningDecision(
        publication_id=Publication(title="Example").record_id,
        stage=ScreeningStage.TITLE_ABSTRACT,
        human_outcome=ScreeningOutcome.INCLUDE,
        reviewer_id="reviewer-1",
        ai_recommendation=recommendation,
    )

    restored = ScreeningDecision.model_validate_json(decision.model_dump_json())

    assert restored.human_outcome is ScreeningOutcome.INCLUDE
    assert restored.ai_recommendation is not None
    assert restored.ai_recommendation.outcome is ScreeningOutcome.EXCLUDE


def test_domain_models_reject_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        Publication(title="Example", unsupported_field="value")

    with pytest.raises(ValidationError):
        SearchTerm(value="lean", unsupported_field="value")

    with pytest.raises(ValidationError):
        AIRecommendation(
            outcome=ScreeningOutcome.INCLUDE,
            confidence=0.9,
            model_name="model",
            unsupported_field="value",
        )


def test_audit_timestamps_are_timezone_aware_by_default() -> None:
    publication = Publication(title="Example")
    recommendation = AIRecommendation(
        outcome=ScreeningOutcome.INCLUDE,
        confidence=0.9,
        model_name="model",
    )

    assert publication.created_at.tzinfo is not None
    assert publication.created_at.utcoffset() is not None
    assert recommendation.created_at.tzinfo is not None
    assert recommendation.created_at.utcoffset() is not None
    assert publication.created_at <= datetime.now(timezone.utc)
