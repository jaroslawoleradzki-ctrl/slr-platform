from __future__ import annotations

from app.domain.search import BooleanOperator, SearchGroup, SearchQuery, SearchTerm
from app.rendering.crossref import (
    MAX_CROSSREF_CANDIDATE_QUERIES,
    CrossrefQueryRenderer,
    build_crossref_candidate_plan,
    build_crossref_candidate_queries,
)


def _diagnosed_lean_energy_query() -> SearchQuery:
    """The canonical Lean/Energy 7 x 6 x 4 strategy from diagnosis."""
    lean_terms = [
        "Lean Management",
        "Lean Manufacturing",
        "Lean Production",
        "Toyota Production System",
        "Kaizen",
        "Continuous Improvement",
        "Just-in-Time",
    ]
    energy_terms = [
        "Energy Efficiency",
        "Energy Consumption",
        "Energy Performance",
        "Energy Saving",
        "Energy Management",
        "Energy Use",
    ]
    mfg_terms = [
        "Manufacturing",
        "Production",
        "Industrial",
        "Factory",
    ]
    return SearchQuery(
        name="Lean Energy Manufacturing",
        expression=SearchGroup(
            operator=BooleanOperator.AND,
            children=[
                SearchGroup(
                    operator=BooleanOperator.OR,
                    children=[SearchTerm(value=t, exact_phrase=True) for t in lean_terms],
                ),
                SearchGroup(
                    operator=BooleanOperator.OR,
                    children=[SearchTerm(value=t, exact_phrase=True) for t in energy_terms],
                ),
                SearchGroup(
                    operator=BooleanOperator.OR,
                    children=[SearchTerm(value=t, exact_phrase=True) for t in mfg_terms],
                ),
            ],
        ),
    )


def test_diagnosed_7x6x4_budget_6_hard_bound_and_combinations() -> None:
    query = _diagnosed_lean_energy_query()
    plan = build_crossref_candidate_plan(query.expression)

    assert plan.possible_combinations == 168
    assert len(plan.queries) == MAX_CROSSREF_CANDIDATE_QUERIES
    assert len(set(plan.queries)) == MAX_CROSSREF_CANDIDATE_QUERIES


def test_diagnosed_7x6x4_all_four_third_axis_alternatives_represented() -> None:
    """Eliminates the diagnosis defect: all 4 manufacturing-context terms must be represented."""
    query = _diagnosed_lean_energy_query()
    queries = build_crossref_candidate_queries(query.expression)

    mfg_alternatives = ["Manufacturing", "Production", "Industrial", "Factory"]
    represented_mfg = {alt for alt in mfg_alternatives if any(f'"{alt}"' in q for q in queries)}

    assert represented_mfg == set(mfg_alternatives)
    assert len(represented_mfg) == 4


def test_diagnosed_7x6x4_lean_and_energy_axes_sensible_representation() -> None:
    query = _diagnosed_lean_energy_query()
    plan = build_crossref_candidate_plan(query.expression)

    # Group 0 (Lean, 7 alternatives): budget 6 allows at most 6 distinct
    lean_cov = plan.axis_coverage[0]
    assert lean_cov["available_alternatives"] == 7
    assert lean_cov["represented_alternatives"] == 6
    assert lean_cov["coverage_ratio"] == round(6 / 7, 4)

    # Group 1 (Energy, 6 alternatives): 100% representation
    energy_cov = plan.axis_coverage[1]
    assert energy_cov["available_alternatives"] == 6
    assert energy_cov["represented_alternatives"] == 6
    assert energy_cov["coverage_ratio"] == 1.0

    # Group 2 (Manufacturing, 4 alternatives): 100% representation
    mfg_cov = plan.axis_coverage[2]
    assert mfg_cov["available_alternatives"] == 4
    assert mfg_cov["represented_alternatives"] == 4
    assert mfg_cov["coverage_ratio"] == 1.0


def test_diagnosed_7x6x4_no_duplicate_physical_queries() -> None:
    query = _diagnosed_lean_energy_query()
    queries = build_crossref_candidate_queries(query.expression)

    assert len(queries) == len(set(queries))


def test_diagnosed_7x6x4_identical_input_produces_identical_ordered_plan() -> None:
    query = _diagnosed_lean_energy_query()
    plan1 = build_crossref_candidate_plan(query.expression)
    plan2 = build_crossref_candidate_plan(query.expression)

    assert plan1.queries == plan2.queries
    assert plan1.possible_combinations == plan2.possible_combinations
    assert plan1.axis_coverage == plan2.axis_coverage


def test_full_cartesian_product_preserved_when_within_budget() -> None:
    # 2 x 2 = 4 combinations <= 6
    expr_2x2 = SearchGroup(
        operator=BooleanOperator.AND,
        children=[
            SearchGroup(operator=BooleanOperator.OR, children=[SearchTerm(value="a1"), SearchTerm(value="a2")]),
            SearchGroup(operator=BooleanOperator.OR, children=[SearchTerm(value="b1"), SearchTerm(value="b2")]),
        ],
    )
    plan_2x2 = build_crossref_candidate_plan(expr_2x2)
    assert plan_2x2.possible_combinations == 4
    assert plan_2x2.queries == ("a1 b1", "a1 b2", "a2 b1", "a2 b2")
    assert all(cov["coverage_ratio"] == 1.0 for cov in plan_2x2.axis_coverage)

    # 2 x 3 = 6 combinations == 6 (exact bound)
    expr_2x3 = SearchGroup(
        operator=BooleanOperator.AND,
        children=[
            SearchGroup(operator=BooleanOperator.OR, children=[SearchTerm(value="a1"), SearchTerm(value="a2")]),
            SearchGroup(
                operator=BooleanOperator.OR,
                children=[SearchTerm(value="b1"), SearchTerm(value="b2"), SearchTerm(value="b3")],
            ),
        ],
    )
    plan_2x3 = build_crossref_candidate_plan(expr_2x3)
    assert plan_2x3.possible_combinations == 6
    assert len(plan_2x3.queries) == 6
    assert plan_2x3.queries == ("a1 b1", "a1 b2", "a1 b3", "a2 b1", "a2 b2", "a2 b3")
    assert all(cov["coverage_ratio"] == 1.0 for cov in plan_2x3.axis_coverage)


def test_one_group_query_single_term_and_or() -> None:
    # Single term
    single_term = SearchTerm(value="robotics")
    plan_single = build_crossref_candidate_plan(single_term)
    assert plan_single.possible_combinations == 1
    assert plan_single.queries == ("robotics",)
    assert plan_single.axis_coverage[0]["coverage_ratio"] == 1.0

    # Single OR group exceeding bound (10 terms)
    ten_terms = SearchGroup(
        operator=BooleanOperator.OR,
        children=[SearchTerm(value=f"term_{i}") for i in range(10)],
    )
    plan_ten = build_crossref_candidate_plan(ten_terms)
    assert plan_ten.possible_combinations == 10
    assert len(plan_ten.queries) == 6
    assert len(set(plan_ten.queries)) == 6
    assert plan_ten.axis_coverage[0]["available_alternatives"] == 10
    assert plan_ten.axis_coverage[0]["represented_alternatives"] == 6
    assert plan_ten.axis_coverage[0]["coverage_ratio"] == 0.6


def test_uneven_group_sizes() -> None:
    # Axis 0: 10 alternatives; Axis 1: 2 alternatives (total 20 > 6)
    expr = SearchGroup(
        operator=BooleanOperator.AND,
        children=[
            SearchGroup(operator=BooleanOperator.OR, children=[SearchTerm(value=f"a_{i}") for i in range(10)]),
            SearchGroup(operator=BooleanOperator.OR, children=[SearchTerm(value=f"b_{i}") for i in range(2)]),
        ],
    )
    plan = build_crossref_candidate_plan(expr)
    assert plan.possible_combinations == 20
    assert len(plan.queries) == 6
    assert len(set(plan.queries)) == 6

    # Both alternatives of Axis 1 must be represented
    assert plan.axis_coverage[1]["available_alternatives"] == 2
    assert plan.axis_coverage[1]["represented_alternatives"] == 2
    assert plan.axis_coverage[1]["coverage_ratio"] == 1.0

    # 6 distinct alternatives of Axis 0 must be represented
    assert plan.axis_coverage[0]["available_alternatives"] == 10
    assert plan.axis_coverage[0]["represented_alternatives"] == 6
    assert plan.axis_coverage[0]["coverage_ratio"] == 0.6


def test_more_positive_groups_than_three() -> None:
    # 5 positive groups of 2 alternatives: 2^5 = 32 > 6
    expr_5 = SearchGroup(
        operator=BooleanOperator.AND,
        children=[
            SearchGroup(operator=BooleanOperator.OR, children=[SearchTerm(value=f"g{j}_{i}") for i in range(2)])
            for j in range(5)
        ],
    )
    plan_5 = build_crossref_candidate_plan(expr_5)
    assert plan_5.possible_combinations == 32
    assert len(plan_5.queries) == 6
    assert len(set(plan_5.queries)) == 6
    # Every group of 2 alternatives should have both alternatives represented
    for cov in plan_5.axis_coverage:
        assert cov["available_alternatives"] == 2
        assert cov["represented_alternatives"] == 2
        assert cov["coverage_ratio"] == 1.0


def test_complex_or_and_not_structures() -> None:
    # (A OR B) AND (C OR D) AND NOT (E)
    expr = SearchGroup(
        operator=BooleanOperator.AND,
        children=[
            SearchGroup(operator=BooleanOperator.OR, children=[SearchTerm(value="lean"), SearchTerm(value="kaizen")]),
            SearchGroup(operator=BooleanOperator.OR, children=[SearchTerm(value="energy"), SearchTerm(value="power")]),
            SearchGroup(operator=BooleanOperator.NOT, children=[SearchTerm(value="waste")]),
        ],
    )
    plan = build_crossref_candidate_plan(expr)
    # 2 x 2 = 4 combinations, NOT child ignored in positive plan
    assert plan.possible_combinations == 4
    assert len(plan.queries) == 4
    assert all("waste" not in q for q in plan.queries)
    assert len(plan.axis_coverage) == 2


def test_renderer_metadata_reports_audit_coverage() -> None:
    query = _diagnosed_lean_energy_query()
    rendered = CrossrefQueryRenderer().render(query)
    metadata = rendered.metadata

    assert "axis_coverage" in metadata
    assert "min_axis_coverage_ratio" in metadata
    assert metadata["physical_query_bound"] == 6
    assert metadata["possible_candidate_combinations"] == 168
    assert metadata["planned_candidate_combinations"] == 6

    coverage = metadata["axis_coverage"]
    assert len(coverage) == 3
    assert coverage[0]["available_alternatives"] == 7
    assert coverage[0]["represented_alternatives"] == 6
    assert coverage[0]["coverage_ratio"] == round(6 / 7, 4)

    assert coverage[1]["available_alternatives"] == 6
    assert coverage[1]["represented_alternatives"] == 6
    assert coverage[1]["coverage_ratio"] == 1.0

    assert coverage[2]["available_alternatives"] == 4
    assert coverage[2]["represented_alternatives"] == 4
    assert coverage[2]["coverage_ratio"] == 1.0

    assert metadata["min_axis_coverage_ratio"] == round(6 / 7, 4)
