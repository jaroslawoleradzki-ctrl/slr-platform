from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Any

from app.domain.identifiers import IdentifierType
from app.domain.publication import Publication


def _stable_json(value: Any) -> str:
    """Serialize parser records deterministically without losing order-sensitive values."""

    def normalize(item: Any) -> Any:
        if isinstance(item, Mapping):
            return {str(key): normalize(item[key]) for key in sorted(item, key=str)}
        if isinstance(item, (list, tuple)):
            return [normalize(entry) for entry in item]
        return item

    return json.dumps(normalize(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def fingerprint_raw_record(record: object) -> str:
    """Hash one parser record, independent of file position.

    The parser record contains the original import evidence.  This makes the
    fingerprint stable when an unchanged record moves to another index in a
    revised file, while still distinguishing records whose metadata changed.
    """

    return hashlib.sha256(_stable_json(record).encode("utf-8")).hexdigest()


def fingerprint_publication(publication: Publication) -> str:
    """Fallback fingerprint for callers that do not supply raw parser records.

    This is a *record fingerprint*, never an automatic deduplication authority.
    It includes complete bibliographic evidence, not just the title.
    """

    identifiers: list[tuple[str, str, str | None]] = []
    invalid_dois: list[str] = []
    for identifier in publication.identifiers:
        if identifier.type is IdentifierType.OTHER and identifier.source == "invalid_doi":
            invalid_dois.append(identifier.value.strip())
        else:
            identifiers.append(
                (identifier.type.value, identifier.value.strip(), identifier.source)
            )
    payload = {
        "title": publication.title.strip(),
        "authors": [
            (
                author.display_name.strip(),
                author.family_name,
                author.given_name,
            )
            for author in publication.authors
        ],
        "year": publication.publication_year,
        "document_type": (
            publication.document_type.value if publication.document_type else None
        ),
        "abstract": publication.abstract,
        "identifiers": sorted(identifiers),
        "invalid_dois": sorted(invalid_dois),
    }
    return hashlib.sha256(_stable_json(payload).encode("utf-8")).hexdigest()


def normalize_source_label(value: str | None) -> str:
    return (value or "").strip().casefold()


def source_occurrence_id(
    *,
    project_id: str,
    source_label: str | None,
    filename: str | None,
    record_fingerprint: str,
    ordinal: int,
) -> str:
    """Deterministic source occurrence identity.

    The occurrence is scoped by project, source label, filename, record content
    and the ordinal of identical records inside that file.  It intentionally
    does NOT use the current file hash or record index, so unchanged records
    remain stable across file revisions while a changed record gets a new
    identity.
    """

    payload = "|".join(
        (
            project_id.strip(),
            normalize_source_label(source_label),
            (filename or "").strip().casefold(),
            record_fingerprint,
            str(max(1, ordinal)),
        )
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def raw_record_fingerprints(records: Sequence[object] | None) -> list[str] | None:
    if records is None:
        return None
    return [fingerprint_raw_record(record) for record in records]
