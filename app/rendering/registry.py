from __future__ import annotations

from app.domain.search import SearchQuery
from app.rendering.base import QueryRenderer, RenderedQuery
from app.rendering.crossref import CrossrefQueryRenderer
from app.rendering.openalex import OpenAlexQueryRenderer
from app.rendering.semantic_scholar import SemanticScholarQueryRenderer


class GenericBooleanQueryRenderer:
    """Fallback renderer for generic or test providers using canonical Boolean query string."""

    def __init__(self, provider: str = "generic") -> None:
        self.provider = provider

    def render(self, search_query: SearchQuery) -> RenderedQuery:
        return RenderedQuery(
            provider=self.provider,
            query_string=search_query.to_boolean_query(),
            is_lossless=True,
            warnings=(),
        )


_DEFAULT_RENDERERS: dict[str, QueryRenderer] = {
    "openalex": OpenAlexQueryRenderer(),
    "crossref": CrossrefQueryRenderer(),
    "semantic_scholar": SemanticScholarQueryRenderer(),
}


def get_query_renderer(provider: str) -> QueryRenderer:
    provider_key = provider.strip().casefold()
    if provider_key in _DEFAULT_RENDERERS:
        return _DEFAULT_RENDERERS[provider_key]
    return GenericBooleanQueryRenderer(provider=provider)
