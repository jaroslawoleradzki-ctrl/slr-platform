from app.domain.search import (
    BooleanOperator,
    SearchField,
    SearchGroup,
    SearchQuery,
    SearchTerm,
)
from app.rendering.semantic_scholar import SemanticScholarQueryRenderer


def _render(expression: SearchTerm | SearchGroup):
    return SemanticScholarQueryRenderer().render(
        SearchQuery(name="Semantic Scholar renderer test", expression=expression)
    )


def test_semantic_scholar_bulk_preserves_boolean_syntax() -> None:
    rendered = _render(
        SearchGroup(
            operator=BooleanOperator.AND,
            children=[
                SearchGroup(
                    operator=BooleanOperator.OR,
                    children=[
                        SearchTerm(value="lean management", exact_phrase=True),
                        SearchTerm(value="kaizen", exact_phrase=True),
                    ],
                ),
                SearchTerm(value="energy efficiency", exact_phrase=True),
            ],
        )
    )

    assert rendered.provider == "semantic_scholar"
    assert rendered.physical_endpoint.endswith("/paper/search/bulk")
    assert rendered.query_string == '(("lean management" | "kaizen") + "energy efficiency")'
    assert rendered.is_lossless is True
    assert rendered.warnings == ()
    assert rendered.metadata["translation"] == "semantic_scholar_bulk_boolean"


def test_semantic_scholar_bulk_renders_not_and_grouping() -> None:
    rendered = _render(
        SearchGroup(
            operator=BooleanOperator.AND,
            children=[
                SearchTerm(value="lean"),
                SearchGroup(
                    operator=BooleanOperator.NOT,
                    children=[SearchTerm(value="building")],
                ),
            ],
        )
    )
    assert rendered.query_string == "(lean + -(building))"
    assert rendered.is_lossless is True


def test_semantic_scholar_bulk_quotes_phrases_and_normalizes_punctuation() -> None:
    rendered = _render(SearchTerm(value="lean-manufacturing energy/efficiency"))
    assert rendered.query_string == '"lean manufacturing energy efficiency"'
    assert rendered.is_lossless is False
    assert any("normalized punctuation" in warning for warning in rendered.warnings)


def test_semantic_scholar_hyphenated_term_is_lossy() -> None:
    rendered = _render(SearchTerm(value="Energy-Efficiency", exact_phrase=True))
    assert rendered.query_string == '"Energy Efficiency"'
    assert rendered.is_lossless is False
    assert any("normalized punctuation in 'Energy-Efficiency'" in warning for warning in rendered.warnings)


def test_semantic_scholar_micro_chp_hyphenated_term_is_lossy() -> None:
    rendered = _render(SearchTerm(value="micro-CHP", exact_phrase=True))
    assert rendered.query_string == '"micro CHP"'
    assert rendered.is_lossless is False
    assert any("normalized punctuation in 'micro-CHP'" in warning for warning in rendered.warnings)


def test_semantic_scholar_field_scope_is_explicitly_lossy() -> None:
    rendered = _render(SearchTerm(value="lean", field=SearchField.TITLE))
    assert rendered.query_string == "lean"
    assert rendered.is_lossless is False
    assert any("field scopes" in warning for warning in rendered.warnings)
