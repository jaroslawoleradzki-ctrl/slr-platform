from collections.abc import Iterable

from app.domain.identifiers import IdentifierType
from app.domain.publication import Publication
from app.normalization import normalize_doi


class ResultMerger:
    """Conservatively merge publications by their first normalized DOI."""

    def merge(
        self,
        publications: Iterable[Publication],
    ) -> list[Publication]:
        merged: list[Publication] = []
        seen_dois: set[str] = set()

        for publication in publications:
            doi = self._first_doi(publication)
            if doi is not None:
                if doi in seen_dois:
                    continue
                seen_dois.add(doi)
            merged.append(publication)

        return merged

    @staticmethod
    def _first_doi(publication: Publication) -> str | None:
        for identifier in publication.identifiers:
            if identifier.type is IdentifierType.DOI:
                return normalize_doi(identifier.value)
        return None
