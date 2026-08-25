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


def test_semantic_scholar_renderer_regression_query() -> None:
    rendered = _render(
        SearchGroup(
            operator=BooleanOperator.OR,
            children=[
                SearchTerm(value="Lean", exact_phrase=True),
                SearchTerm(
                    value="lean manufacturing energy efficiency",
                    exact_phrase=True,
                ),
            ],
        )
    )

    assert rendered.provider == "semantic_scholar"
    assert rendered.query_string == "Lean lean manufacturing energy efficiency"
    assert rendered.is_lossless is False
    assert rendered.metadata == {
        "canonical_query": '("Lean" OR "lean manufacturing energy efficiency")',
        "translation": "plain_text_best_effort",
    }
    assert any("exact-phrase syntax" in warning for warning in rendered.warnings)
    assert any("OR operators" in warning for warning in rendered.warnings)


def test_semantic_scholar_renderer_single_phrase_is_plain_text_and_lossy() -> None:
    rendered = _render(SearchTerm(value="lean manufacturing"))

    assert rendered.query_string == "lean manufacturing"
    assert rendered.is_lossless is False
    assert len(rendered.warnings) == 1
    assert "exact-phrase syntax" in rendered.warnings[0]


def test_semantic_scholar_renderer_single_term_is_lossless() -> None:
    rendered = _render(SearchTerm(value="Lean"))

    assert rendered.query_string == "Lean"
    assert rendered.is_lossless is True
    assert rendered.warnings == ()


def test_semantic_scholar_renderer_and_is_flattened_and_lossy() -> None:
    rendered = _render(
        SearchGroup(
            operator=BooleanOperator.AND,
            children=[SearchTerm(value="lean"), SearchTerm(value="energy")],
        )
    )

    assert rendered.query_string == "lean energy"
    assert rendered.is_lossless is False
    assert any("AND operators" in warning for warning in rendered.warnings)


def test_semantic_scholar_renderer_or_is_flattened_and_lossy() -> None:
    rendered = _render(
        SearchGroup(
            operator=BooleanOperator.OR,
            children=[SearchTerm(value="lean"), SearchTerm(value="kaizen")],
        )
    )

    assert rendered.query_string == "lean kaizen"
    assert rendered.is_lossless is False
    assert any("OR operators" in warning for warning in rendered.warnings)


def test_semantic_scholar_renderer_nested_grouping_and_not_are_auditable() -> None:
    rendered = _render(
        SearchGroup(
            operator=BooleanOperator.AND,
            children=[
                SearchGroup(
                    operator=BooleanOperator.OR,
                    children=[SearchTerm(value="lean"), SearchTerm(value="kaizen")],
                ),
                SearchGroup(
                    operator=BooleanOperator.NOT,
                    children=[SearchTerm(value="building")],
                ),
                SearchTerm(value="efficiency"),
            ],
        )
    )

    assert rendered.query_string == "lean kaizen efficiency"
    assert rendered.is_lossless is False
    assert any("AND operators" in warning for warning in rendered.warnings)
    assert any("OR operators" in warning for warning in rendered.warnings)
    assert any("NOT operators" in warning for warning in rendered.warnings)


def test_semantic_scholar_renderer_quotes_escapes_and_special_characters() -> None:
    rendered = _render(
        SearchGroup(
            operator=BooleanOperator.AND,
            children=[
                SearchTerm(value='\\"lean-manufacturing\\"'),
                SearchTerm(value="energy/efficiency (R&D)"),
            ],
        )
    )

    assert rendered.query_string == "lean manufacturing energy efficiency R D"
    assert rendered.is_lossless is False
    assert any("special query characters" in warning for warning in rendered.warnings)


def test_semantic_scholar_renderer_field_scope_is_explicitly_lossy() -> None:
    rendered = _render(SearchTerm(value="lean", field=SearchField.TITLE))

    assert rendered.query_string == "lean"
    assert rendered.is_lossless is False
    assert any("field scopes" in warning for warning in rendered.warnings)
