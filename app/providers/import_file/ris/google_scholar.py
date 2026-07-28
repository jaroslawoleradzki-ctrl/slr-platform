from __future__ import annotations

from app.domain.publication import Publication
from app.normalization import normalize_publication
from app.providers.import_file.base import ImportProvider
from app.providers.import_file.ris.mapper import map_ris_record
from app.providers.import_file.ris.parser import parse_ris

_SOURCE = "google_scholar"


class GoogleScholarImportProvider:
    """Import Google Scholar RIS exports into canonical publications."""

    def import_publications(self, content: str) -> list[Publication]:
        """Parse and map all RIS records in *content*."""
        records = parse_ris(content)
        return [
            normalize_publication(map_ris_record(record, source=_SOURCE))
            for record in records
        ]


_PROVIDER: ImportProvider = GoogleScholarImportProvider()


def import_ris(content: str) -> list[Publication]:
    """Import a Google Scholar RIS export and return canonical publications.

    Parses *content* with :func:`parse_ris`, then maps every record to a
    :class:`~app.domain.publication.Publication` using
    :func:`map_ris_record` with ``source="google_scholar"``.

    Parameters
    ----------
    content:
        Full text of a RIS file exported from Google Scholar.

    Returns
    -------
    list[Publication]
        One :class:`Publication` per RIS record found in *content*.
        Returns an empty list when *content* contains no records.

    Raises
    ------
    ValueError
        Propagated from :func:`parse_ris` if the file is structurally
        malformed, or from :func:`map_ris_record` if a record has no
        resolvable title.
    """
    return _PROVIDER.import_publications(content)
