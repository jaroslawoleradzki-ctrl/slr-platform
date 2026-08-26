from app.domain.search import BooleanOperator, SearchGroup, SearchQuery, SearchTerm
from app.rendering.crossref import CrossrefQueryRenderer


def test_crossref_renderer_single_term() -> None:
    renderer = CrossrefQueryRenderer()
    query = SearchQuery(
        name="Single Term",
        expression=SearchTerm(value="robotics"),
    )
    rendered = renderer.render(query)
    assert rendered.provider == "crossref"
    assert rendered.query_string == "robotics"
    assert rendered.physical_endpoint == "https://api.crossref.org/works"
    assert rendered.is_lossless is False
    assert "cannot execute" in rendered.warnings[0]
    assert rendered.metadata["canonical_query"] == "robotics"


def test_crossref_renderer_exact_phrase() -> None:
    renderer = CrossrefQueryRenderer()
    query = SearchQuery(
        name="Exact Phrase",
        expression=SearchTerm(value="machine learning", exact_phrase=True),
    )
    rendered = renderer.render(query)
    assert rendered.query_string == '"machine learning"'
    assert rendered.is_lossless is False


def test_crossref_renderer_and_terms() -> None:
    renderer = CrossrefQueryRenderer()
    expression = SearchGroup(
        operator=BooleanOperator.AND,
        children=[
            SearchTerm(value="lean management", exact_phrase=True),
            SearchTerm(value="energy efficiency", exact_phrase=True),
        ],
    )
    query = SearchQuery(name="AND Query", expression=expression)
    rendered = renderer.render(query)
    assert rendered.query_string == '"lean management"'
    assert rendered.metadata["candidate_queries"] == ['"lean management"']
    assert rendered.is_lossless is False


def test_crossref_renderer_or_terms_flagged_as_lossy() -> None:
    renderer = CrossrefQueryRenderer()
    expression = SearchGroup(
        operator=BooleanOperator.OR,
        children=[
            SearchTerm(value="lean management", exact_phrase=True),
            SearchTerm(value="lean manufacturing", exact_phrase=True),
        ],
    )
    query = SearchQuery(name="OR Query", expression=expression)
    rendered = renderer.render(query)
    assert rendered.query_string == '"lean management" || "lean manufacturing"'
    assert rendered.is_lossless is False
    assert len(rendered.warnings) == 2
    assert rendered.metadata["canonical_query"] == '("lean management" OR "lean manufacturing")'


def test_crossref_renderer_not_terms_flagged_as_lossy() -> None:
    renderer = CrossrefQueryRenderer()
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
    assert rendered.query_string == '"artificial intelligence"'
    assert rendered.is_lossless is False
    assert len(rendered.warnings) == 2
    assert rendered.metadata["canonical_query"] == '("artificial intelligence" AND NOT (robotics))'


def test_crossref_renderer_deterministic() -> None:
    renderer = CrossrefQueryRenderer()
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


def test_crossref_renderer_complex_boolean_query_with_or_and_not() -> None:
    renderer = CrossrefQueryRenderer()
    # ("lean manufacturing" OR "lean production") AND ("energy efficiency" OR "energy consumption") NOT ("building")
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
                children=[
                    SearchTerm(value="building", exact_phrase=True),
                ],
            ),
        ],
    )
    query = SearchQuery(name="Complex Strategy Query", expression=expression)
    rendered = renderer.render(query)

    assert rendered.provider == "crossref"
    assert rendered.query_string == '"lean manufacturing" || "lean production"'
    assert rendered.is_lossless is False
    assert len(rendered.warnings) == 2
    assert rendered.metadata["candidate_queries"] == [
        '"lean manufacturing"',
        '"lean production"',
    ]
    assert rendered.metadata["canonical_query"] == (
        '(("lean manufacturing" OR "lean production") AND '
        '("energy efficiency" OR "energy consumption") AND '
        'NOT ("building"))'
    )
