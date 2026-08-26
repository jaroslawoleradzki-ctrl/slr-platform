from collections.abc import Iterable
from typing import Any

from app.domain.identifiers import IdentifierType
from app.domain.publication import Publication
from app.normalization import normalize_doi


class ResultMerger:
    """Conservatively merge publications by their first normalized DOI, consolidating metadata and provenance."""

    def merge(
        self,
        publications: Iterable[Publication],
    ) -> list[Publication]:
        merged: list[Publication] = []
        index_by_doi: dict[str, int] = {}

        for publication in publications:
            doi = self._first_doi(publication)
            if doi is not None:
                if doi in index_by_doi:
                    index = index_by_doi[doi]
                    canonical = merged[index]
                    merged[index] = self._merge_two(canonical, publication)
                    continue
                index_by_doi[doi] = len(merged)
            merged.append(publication)

        return merged

    def _merge_two(self, canonical: Publication, incoming: Publication) -> Publication:
        updates: dict[str, Any] = {}

        # 1. Abstract
        if canonical.abstract is None and incoming.abstract is not None:
            updates["abstract"] = incoming.abstract

        # 2. Authors
        if not canonical.authors and incoming.authors:
            updates["authors"] = incoming.authors

        # 3. Venue
        if canonical.venue is None and incoming.venue is not None:
            updates["venue"] = incoming.venue

        # 4. Publication year & date
        if canonical.publication_year is None and incoming.publication_year is not None:
            updates["publication_year"] = incoming.publication_year
        if canonical.publication_date is None and incoming.publication_date is not None:
            year_to_match = updates.get("publication_year", canonical.publication_year)
            if year_to_match is None or incoming.publication_date.year == year_to_match:
                updates["publication_date"] = incoming.publication_date

        # 5. Publisher
        if canonical.publisher is None and incoming.publisher is not None:
            updates["publisher"] = incoming.publisher

        # 6. Document type
        if canonical.document_type is None and incoming.document_type is not None:
            updates["document_type"] = incoming.document_type

        # 7. Language
        if canonical.language is None and incoming.language is not None:
            updates["language"] = incoming.language

        # 8. Open access
        if canonical.open_access is None and incoming.open_access is not None:
            updates["open_access"] = incoming.open_access

        # 9. Keywords
        if incoming.keywords:
            combined_keywords = list(canonical.keywords)
            seen_kw = {k.casefold() for k in canonical.keywords}
            for kw in incoming.keywords:
                if kw.casefold() not in seen_kw:
                    combined_keywords.append(kw)
                    seen_kw.add(kw.casefold())
            if combined_keywords != canonical.keywords:
                updates["keywords"] = combined_keywords

        # 10. URLs
        if incoming.urls:
            combined_urls = list(canonical.urls)
            seen_urls = set(canonical.urls)
            for u in incoming.urls:
                if u not in seen_urls:
                    combined_urls.append(u)
                    seen_urls.add(u)
            if combined_urls != canonical.urls:
                updates["urls"] = combined_urls

        # 11. Identifiers
        if incoming.identifiers:
            combined_ids = list(canonical.identifiers)
            seen_id_keys = {
                (i.type, normalize_doi(i.value) if i.type is IdentifierType.DOI else i.value)
                for i in canonical.identifiers
            }
            for i in incoming.identifiers:
                key = (i.type, normalize_doi(i.value) if i.type is IdentifierType.DOI else i.value)
                if key not in seen_id_keys:
                    combined_ids.append(i)
                    seen_id_keys.add(key)
            if combined_ids != canonical.identifiers:
                updates["identifiers"] = combined_ids


        # 12. Provenance
        provenance = list(canonical.provenance)
        seen_provenance = {
            (entry.source.casefold(), entry.source_record_id, entry.run_id) for entry in provenance
        }
        for entry in incoming.provenance:
            key = (entry.source.casefold(), entry.source_record_id, entry.run_id)
            if key not in seen_provenance:
                provenance.append(entry)
                seen_provenance.add(key)
        if provenance != canonical.provenance:
            updates["provenance"] = provenance

        if updates:
            return canonical.model_copy(update=updates)
        return canonical

    @staticmethod
    def _first_doi(publication: Publication) -> str | None:
        for identifier in publication.identifiers:
            if identifier.type is IdentifierType.DOI:
                return normalize_doi(identifier.value)
        return None
