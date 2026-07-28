from __future__ import annotations

from app.domain.publication import Publication
from app.normalization import normalize_publication
from app.providers.import_file.bibtex.mapper import map_bibtex_record
from app.providers.import_file.bibtex.parser import parse_bibtex


class BibTeXImportProvider:
    """Import BibTeX content into canonical publications."""

    def __init__(self, *, source: str = "bibtex") -> None:
        self._source = source

    def import_publications(self, content: str) -> list[Publication]:
        """Parse and map all BibTeX records in *content*."""
        records = parse_bibtex(content)
        return [
            normalize_publication(
                map_bibtex_record(record, source=self._source)
            )
            for record in records
        ]
