from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from app.domain.search import SearchQuery


@dataclass(frozen=True, slots=True)
class RenderedQuery:
    """Provider-specific physical query representation with audit metadata."""

    provider: str
    query_string: str
    physical_endpoint: str = ""
    is_lossless: bool = True
    warnings: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


class QueryRenderer(Protocol):
    """Structural protocol for provider-specific search query renderers."""

    provider: str

    def render(self, search_query: SearchQuery) -> RenderedQuery: ...
