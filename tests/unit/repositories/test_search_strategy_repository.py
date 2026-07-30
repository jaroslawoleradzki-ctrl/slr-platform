from pathlib import Path

import pytest

from app.domain.search import (
    BooleanOperator,
    SearchConceptGroup,
    SearchConstraints,
    SearchQuery,
    SearchStrategy,
    SearchTerm,
)
from app.repositories.search_strategy_repository import (
    SearchStrategyNotFoundError,
    SqliteSearchStrategyRepository,
)


def _strategy() -> SearchStrategy:
    return SearchStrategy(
        project_id="lean_energy",
        name="Energy strategy",
        research_questions=["How does lean production reduce energy use?"],
        concept_groups=[
            SearchConceptGroup(
                group_id="lean",
                name="Lean",
                terms=["lean production", "kaizen"],
                operator=BooleanOperator.OR,
            )
        ],
        constraints=SearchConstraints(
            publication_year_from=2015,
            publication_year_to=2026,
            languages=["en", "pl"],
            publication_types=["article"],
            additional_limits={"open_access": True},
        ),
        providers=["openalex", "crossref"],
        queries=[
            SearchQuery(
                name="Core query",
                expression=SearchTerm(value="lean production", exact_phrase=True),
            )
        ],
    )


def test_sqlite_repository_round_trips_complete_strategy(tmp_path: Path) -> None:
    repository = SqliteSearchStrategyRepository(tmp_path / "slr.db")
    strategy = _strategy()

    saved = repository.save(strategy)

    assert repository.get("lean_energy") == saved
    assert repository.get("lean_energy").constraints.additional_limits == {
        "open_access": True
    }


def test_sqlite_repository_replaces_project_strategy(tmp_path: Path) -> None:
    repository = SqliteSearchStrategyRepository(tmp_path / "slr.db")
    first = _strategy()
    second = first.model_copy(
        update={"name": "Updated strategy", "version": 2}
    )

    repository.save(first)
    repository.save(second)

    assert repository.get("lean_energy") == second


def test_sqlite_repository_reports_missing_strategy(tmp_path: Path) -> None:
    repository = SqliteSearchStrategyRepository(tmp_path / "slr.db")

    with pytest.raises(SearchStrategyNotFoundError):
        repository.get("missing")
