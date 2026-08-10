from __future__ import annotations

from app.domain.search import BooleanOperator, SearchExpression, SearchGroup, SearchQuery, SearchTerm
from app.rendering.base import RenderedQuery


class OpenAlexQueryRenderer:
    """Renderer converting canonical SearchQuery to OpenAlex search syntax."""

    provider: str = "openalex"

    def render(self, search_query: SearchQuery) -> RenderedQuery:
        query_string = self._render_expression(search_query.expression)
        return RenderedQuery(
            provider=self.provider,
            query_string=query_string,
            is_lossless=True,
            warnings=(),
        )

    def _render_expression(self, expression: SearchExpression) -> str:
        if isinstance(expression, SearchTerm):
            val = expression.value
            if expression.exact_phrase or " " in val:
                return f'"{val}"'
            return val

        if isinstance(expression, SearchGroup):
            if expression.operator is BooleanOperator.NOT:
                child_rendered = self._render_expression(expression.children[0])
                return f"NOT ({child_rendered})"

            op_str = f" {expression.operator.value.upper()} "
            children_rendered = [
                self._render_expression(child) for child in expression.children
            ]
            return f"({op_str.join(children_rendered)})"

        raise TypeError(f"Unsupported search expression type: {type(expression)}")
