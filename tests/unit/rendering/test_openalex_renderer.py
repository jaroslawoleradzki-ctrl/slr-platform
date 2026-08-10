from app.domain.search import BooleanOperator, SearchGroup, SearchQuery, SearchTerm
from app.rendering.openalex import OpenAlexQueryRenderer


def test_openalex_renderer_single_term() -> None:
    renderer = OpenAlexQueryRenderer()
    query = SearchQuery(
        name="Single Term",
        expression=SearchTerm(value="robotics"),
    )
    rendered = renderer.render(query)
    assert rendered.provider == "openalex"
    assert rendered.query_string == "robotics"
    assert rendered.is_lossless is True
    assert rendered.warnings == ()


def test_openalex_renderer_exact_phrase() -> None:
    renderer = OpenAlexQueryRenderer()
    query = SearchQuery(
        name="Exact Phrase",
        expression=SearchTerm(value="machine learning", exact_phrase=True),
    )
    rendered = renderer.render(query)
    assert rendered.query_string == '"machine learning"'
    assert rendered.is_lossless is True


def test_openalex_renderer_nested_and_or() -> None:
    renderer = OpenAlexQueryRenderer()
    expression = SearchGroup(
        operator=BooleanOperator.AND,
        children=[
            SearchGroup(
                operator=BooleanOperator.OR,
                children=[
                    SearchTerm(value="lean management", exact_phrase=True),
                    SearchTerm(value="lean manufacturing", exact_phrase=True),
                ],
            ),
            SearchGroup(
                operator=BooleanOperator.OR,
                children=[
                    SearchTerm(value="energy efficiency", exact_phrase=True),
                    SearchTerm(value="sustainability"),
                ],
            ),
        ],
    )
    query = SearchQuery(name="Nested Query", expression=expression)
    rendered = renderer.render(query)
    assert (
        rendered.query_string
        == '(("lean management" OR "lean manufacturing") AND ("energy efficiency" OR sustainability))'
    )
    assert rendered.is_lossless is True


def test_openalex_renderer_not_operator() -> None:
    renderer = OpenAlexQueryRenderer()
    expression = SearchGroup(
        operator=BooleanOperator.AND,
        children=[
            SearchTerm(value="artificial intelligence", exact_phrase=True),
            SearchGroup(
                operator=BooleanOperator.NOT,
                children=[SearchTerm(value="robotics")],
            ),
        ],
    )
    query = SearchQuery(name="NOT Query", expression=expression)
    rendered = renderer.render(query)
    assert rendered.query_string == '("artificial intelligence" AND NOT (robotics))'
    assert rendered.is_lossless is True


def test_openalex_renderer_deterministic() -> None:
    renderer = OpenAlexQueryRenderer()
    query = SearchQuery(
        name="Deterministic Test",
        expression=SearchGroup(
            operator=BooleanOperator.AND,
            children=[
                SearchTerm(value="systematic review"),
                SearchTerm(value="automation"),
            ],
        ),
    )
    rendered1 = renderer.render(query)
    rendered2 = renderer.render(query)
    assert rendered1 == rendered2
