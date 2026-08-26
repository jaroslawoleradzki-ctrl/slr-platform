"""Metadata enrichment for search candidates missing abstracts or key fields (v0.6.7)."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone

from app.domain.identifiers import IdentifierType
from app.domain.provenance import ProvenanceEntry
from app.domain.publication import Publication
from app.normalization.doi import normalize_doi
from app.providers.openalex import OpenAlexClient
from app.providers.search.openalex import _reconstruct_abstract
from app.providers.semantic_scholar import SemanticScholarClient


@dataclass
class EnrichmentStats:
    attempted: int = 0
    succeeded: int = 0
    failed: int = 0
    reused_internal: int = 0


class MetadataEnrichmentService:
    """Enriches candidate publications with missing abstracts via internal cache and external DOI lookups."""

    def __init__(
        self,
        *,
        openalex_client: OpenAlexClient | None = None,
        semantic_scholar_client: SemanticScholarClient | None = None,
        max_lookups: int = 100,
        concurrency: int = 5,
        timeout: float = 10.0,
    ) -> None:
        self._openalex_client = openalex_client
        self._semantic_scholar_client = semantic_scholar_client
        self._max_lookups = max_lookups
        self._semaphore = asyncio.Semaphore(concurrency)
        self._timeout = timeout
        self.stats = EnrichmentStats()
        self._lookups_performed = 0

    @staticmethod
    def extract_doi(publication: Publication) -> str | None:
        for identifier in publication.identifiers:
            if identifier.type is IdentifierType.DOI:
                return normalize_doi(identifier.value) or identifier.value.strip()
        return None

    async def enrich_single(
        self,
        publication: Publication,
        *,
        known_abstracts: dict[str, tuple[str, str]] | None = None,
    ) -> tuple[Publication, bool]:
        """Enrich one publication if its abstract is missing and a DOI is present."""
        if publication.abstract is not None:
            return publication, False

        doi = self.extract_doi(publication)
        if not doi:
            return publication, False

        # Phase 1: Internal reuse from already-retrieved/known results
        if known_abstracts and doi in known_abstracts:
            cached_abstract, cached_source = known_abstracts[doi]
            if cached_abstract:
                self.stats.attempted += 1
                self.stats.succeeded += 1
                self.stats.reused_internal += 1
                provenance = list(publication.provenance)
                provenance.append(
                    ProvenanceEntry(
                        source=cached_source,
                        source_record_id=doi,
                        retrieved_at=datetime.now(timezone.utc),
                        transformation="enrichment:internal_abstract",
                    )
                )
                return publication.model_copy(update={"abstract": cached_abstract, "provenance": provenance}), True

        # Phase 2: External DOI lookup
        if self._lookups_performed >= self._max_lookups:
            return publication, False

        self.stats.attempted += 1
        async with self._semaphore:
            if self._lookups_performed >= self._max_lookups:
                self.stats.failed += 1
                return publication, False
            self._lookups_performed += 1

            # 2a. Try OpenAlex
            if self._openalex_client is not None:
                try:
                    work = await asyncio.wait_for(
                        self._openalex_client.get_work_by_doi(doi),
                        timeout=self._timeout,
                    )
                    if work:
                        abstract = _reconstruct_abstract(work.get("abstract_inverted_index"))
                        if abstract:
                            self.stats.succeeded += 1
                            if known_abstracts is not None:
                                known_abstracts[doi] = (abstract, "openalex")
                            provenance = list(publication.provenance)
                            provenance.append(
                                ProvenanceEntry(
                                    source="openalex",
                                    source_record_id=work.get("id", f"doi:{doi}"),
                                    retrieved_at=datetime.now(timezone.utc),
                                    transformation="enrichment:abstract",
                                )
                            )
                            return publication.model_copy(update={"abstract": abstract, "provenance": provenance}), True
                except Exception:
                    pass  # Failover to Semantic Scholar

            # 2b. Try Semantic Scholar
            if self._semantic_scholar_client is not None:
                try:
                    paper = await asyncio.wait_for(
                        self._semantic_scholar_client.get_paper_by_doi(doi, fields=["paperId", "title", "abstract"]),
                        timeout=self._timeout,
                    )
                    if paper:
                        abstract = paper.get("abstract")
                        if abstract and isinstance(abstract, str) and abstract.strip():
                            self.stats.succeeded += 1
                            if known_abstracts is not None:
                                known_abstracts[doi] = (abstract.strip(), "semantic_scholar")
                            provenance = list(publication.provenance)
                            provenance.append(
                                ProvenanceEntry(
                                    source="semantic_scholar",
                                    source_record_id=paper.get("paperId", f"doi:{doi}"),
                                    retrieved_at=datetime.now(timezone.utc),
                                    transformation="enrichment:abstract",
                                )
                            )
                            return publication.model_copy(update={"abstract": abstract.strip(), "provenance": provenance}), True
                except Exception:
                    pass

        self.stats.failed += 1
        return publication, False

    async def enrich_batch(
        self,
        publications: list[Publication],
        *,
        known_abstracts: dict[str, tuple[str, str]] | None = None,
    ) -> list[Publication]:
        """Enrich a list of publications concurrently."""
        tasks = [
            self.enrich_single(pub, known_abstracts=known_abstracts)
            for pub in publications
        ]
        results = await asyncio.gather(*tasks)
        return [pub for pub, _ in results]
