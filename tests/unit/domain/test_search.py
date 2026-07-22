from datetime import date, datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.domain.search import (
    BooleanOperator,
    SearchField,
    SearchGroup,
    SearchQuery,
    SearchRun,
    SearchRunStatus,
    SearchStrategy,
    SearchTerm,
)


def build_large_query() -> SearchQuery:
    lean = SearchGroup(
        operator=BooleanOperator.OR,
        children=[
            SearchTerm(value="lean manufacturing", exact_phrase=True),
            SearchTerm(value="lean production", exact_phrase=True),
            SearchTerm(value="lean management", exact_phrase=True),
        ],
    )
    energy = SearchGroup(
        operator=BooleanOperator.OR,
        children=[
            SearchTerm(value="energy efficiency", exact_phrase=True),
            SearchTerm(value="energy consumption", exact_phrase=True),
            SearchTerm(value="energy performance", exact_phrase=True),
        ],
    )
    exclusion = SearchGroup(
        operator=BooleanOperator.NOT,
        children=[SearchTerm(value="healthcare", field=SearchField.TITLE)],
    )
    return SearchQuery(
        name="Lean and energy master query",
        expression=SearchGroup(
            operator=BooleanOperator.AND,
            children=[lean, energy, exclusion],
        ),
    )


def test_query_can_combine_multiple_boolean_blocks() -> None:
    query = build_large_query()

    assert query.to_boolean_query() == (
        '(("lean manufacturing" OR "lean production" OR "lean management") '
        'AND ("energy efficiency" OR "energy consumption" OR '
        '"energy performance") AND NOT (title:healthcare))'
    )


def test_not_group_requires_exactly_one_child() -> None:
    with pytest.raises(ValidationError):
        SearchGroup(
            operator=BooleanOperator.NOT,
            children=[SearchTerm(value="a"), SearchTerm(value="b")],
        )


def test_and_group_requires_at_least_two_children() -> None:
    with pytest.raises(ValidationError):
        SearchGroup(
            operator=BooleanOperator.AND,
            children=[SearchTerm(value="lean")],
        )


def test_strategy_can_store_multiple_queries() -> None:
    first = build_large_query()
    second = SearchQuery(
        name="Focused title query",
        expression=SearchGroup(
            operator=BooleanOperator.AND,
            children=[
                SearchTerm(value="lean", field=SearchField.TITLE),
                SearchTerm(value="energy", field=SearchField.TITLE),
            ],
        ),
    )

    strategy = SearchStrategy(name="Primary strategy", queries=[first, second])

    assert len(strategy.queries) == 2


def test_strategy_rejects_duplicate_query_ids() -> None:
    query = build_large_query()

    with pytest.raises(ValidationError):
        SearchStrategy(name="Invalid strategy", queries=[query, query])


def test_completed_run_preserves_rendered_query_snapshot() -> None:
    query = build_large_query()
    started_at = datetime(2026, 7, 22, 8, 0, tzinfo=timezone.utc)
    finished_at = datetime(2026, 7, 22, 8, 5, tzinfo=timezone.utc)

    run = SearchRun(
        query_id=query.query_id,
        query_version=query.version,
        provider="openalex",
        provider_version="v1",
        rendered_query=query.to_boolean_query(),
        date_from=date(2000, 1, 1),
        date_to=date(2026, 7, 22),
        status=SearchRunStatus.COMPLETED,
        records_retrieved=382,
        started_at=started_at,
        finished_at=finished_at,
        config_hash="sha256:abc",
        git_commit="d43a834",
    )

    assert run.rendered_query == query.to_boolean_query()
    assert run.records_retrieved == 382


def test_running_run_requires_started_at() -> None:
    with pytest.raises(ValidationError):
        SearchRun(
            query_id=uuid4(),
            query_version=1,
            provider="openalex",
            rendered_query="lean AND energy",
            status=SearchRunStatus.RUNNING,
        )


def test_error_count_must_match_errors() -> None:
    with pytest.raises(ValidationError):
        SearchRun(
            query_id=uuid4(),
            query_version=1,
            provider="openalex",
            rendered_query="lean AND energy",
            error_count=1,
            errors=[],
        )
