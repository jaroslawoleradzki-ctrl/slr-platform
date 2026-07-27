from __future__ import annotations

from typing import Protocol

from app.domain.publication import Publication


class ImportProvider(Protocol):
    """Contract for importing publications from serialized content."""

    def import_publications(self, content: str) -> list[Publication]:
        """Import serialized content into canonical publications."""
        ...
