from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol
from uuid import UUID, uuid4

from app.domain.deduplication import DuplicateGroup
from app.domain.publication import Publication
from app.domain.search import SearchQuery, SearchRun, SearchRunStatus
from app.domain.search_provenance import (
    PublicationSearchProvenance,
    SearchExecutionProvenance,
)
from app.normalization import normalize_publication
from app.providers.search.base import ProviderSearchOutput
from app.rendering import get_query_renderer
from app.services.canonical_query_validator import (
    CanonicalMatchStatus,
    validate_canonical_query,
)
from app.services.duplicate_group_builder import DuplicateGroupBuilder
from app.services.metadata_enrichment import MetadataEnrichmentService
from app.services.result_merger import ResultMerger
from app.storage.raw_response_archive import (
    RawResponseArchive,
    RawResponseArchiveEntry,
    RawResponseStatus,
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class SearchProvider(Protocol):
    """Minimal structural contract for one canonical search execution."""

    name: str

    async def search_with_raw(
        self,
        *,
        search_run: SearchRun,
        search_query: SearchQuery,
        cursor: str = "*",
    ) -> ProviderSearchOutput: ...


@dataclass(frozen=True, slots=True)
class ProviderSearchResult:
    """One provider run with either canonical results or its original error."""

    search_run: SearchRun
    publications: list[Publication] | None
    error: Exception | None
    total_count: int | None = None
    next_cursor: str | None = None
    has_more: bool = False

    def __post_init__(self) -> None:
        if (self.publications is None) == (self.error is None):
            raise ValueError("ProviderSearchResult must contain either publications or an error")

    @property
    def duration_seconds(self) -> float:
        if self.search_run.started_at is None or self.search_run.finished_at is None:
            raise ValueError("completed provider results require run timestamps")
        return (self.search_run.finished_at - self.search_run.started_at).total_seconds()


@dataclass(frozen=True, slots=True)
class SearchExecution:
    """Ordered, separate results from one sequential provider execution."""

    canonical_query: SearchQuery
    provider_results: list[ProviderSearchResult]
    normalized_publications: list[Publication]
    merged_publications: list[Publication]
    duplicate_groups: list[DuplicateGroup]
    result_provenance: list[PublicationSearchProvenance]
    execution_provenance: SearchExecutionProvenance


class SearchEngine:
    """Orchestrate one canonical query through explicit providers."""

    def __init__(
        self,
        *,
        providers: Sequence[SearchProvider],
        raw_response_archive: RawResponseArchive,
        run_id_factory: Callable[[], UUID] = uuid4,
        archive_id_factory: Callable[[], UUID] = uuid4,
        clock: Callable[[], datetime] = _utc_now,
        result_merger: ResultMerger | None = None,
        duplicate_group_builder: DuplicateGroupBuilder | None = None,
        metadata_enricher: MetadataEnrichmentService | None = None,
    ) -> None:
        self._providers = tuple(providers)
        self._raw_response_archive = raw_response_archive
        self._run_id_factory = run_id_factory
        self._archive_id_factory = archive_id_factory
        self._clock = clock
        self._result_merger = result_merger if result_merger is not None else ResultMerger()
        self._duplicate_group_builder = (
            duplicate_group_builder if duplicate_group_builder is not None else DuplicateGroupBuilder()
        )
        self._metadata_enricher = metadata_enricher


    async def execute(
        self,
        search_query: SearchQuery,
        *,
        cursor: str = "*",
    ) -> SearchExecution:
        """Execute providers sequentially and preserve separate result identity."""

        execution_started_at = self._clock()
        provider_results: list[ProviderSearchResult] = []
        result_provenance: list[PublicationSearchProvenance] = []
        known_abstracts: dict[str, tuple[str, str]] = {}
        for provider in self._providers:
            provider_started_at = self._clock()
            renderer = get_query_renderer(provider.name)
            rendered_query_obj = renderer.render(search_query)
            search_run = SearchRun(
                run_id=self._run_id_factory(),
                query_id=search_query.query_id,
                query_version=search_query.version,
                provider=provider.name,
                rendered_query=rendered_query_obj.query_string,
                canonical_hash=search_query.canonical_hash,
                physical_endpoint=rendered_query_obj.physical_endpoint or None,
                is_lossless=rendered_query_obj.is_lossless,
                warnings=list(rendered_query_obj.warnings),
                status=SearchRunStatus.RUNNING,
                started_at=provider_started_at,
            )
            try:
                output = await provider.search_with_raw(
                    search_run=search_run,
                    search_query=search_query,
                    cursor=cursor,
                )
            except Exception as error:
                await self._raw_response_archive.save(
                    RawResponseArchiveEntry(
                        archive_id=self._archive_id_factory(),
                        search_run_id=search_run.run_id,
                        provider=search_run.provider,
                        rendered_query=search_run.rendered_query,
                        captured_at=self._clock(),
                        status=RawResponseStatus.FAILED,
                        responses=[],
                        error_type=type(error).__name__,
                        error_message=str(error),
                    )
                )
                final_search_run = self._finish_search_run(
                    search_run,
                    status=SearchRunStatus.FAILED,
                    finished_at=self._clock(),
                    records_retrieved=0,
                    canonical_accepted_count=0,
                    canonical_rejected_count=0,
                    canonical_indeterminate_count=0,
                    errors=[f"{type(error).__name__}: {error}"],
                )
                provider_results.append(
                    ProviderSearchResult(
                        search_run=final_search_run,
                        publications=None,
                        error=error,
                    )
                )
            else:
                await self._raw_response_archive.save(
                    RawResponseArchiveEntry(
                        archive_id=self._archive_id_factory(),
                        search_run_id=search_run.run_id,
                        provider=search_run.provider,
                        rendered_query=search_run.rendered_query,
                        captured_at=self._clock(),
                        status=RawResponseStatus.SUCCESS,
                        responses=output.raw_responses,
                    )
                )
                retrieved_publications = [normalize_publication(publication) for publication in output.publications]
                for pub in retrieved_publications:
                    if pub.abstract is not None:
                        doi = MetadataEnrichmentService.extract_doi(pub)
                        if doi:
                            known_abstracts[doi] = (pub.abstract, provider.name)

                if self._metadata_enricher is not None:
                    enriched_publications = await self._metadata_enricher.enrich_batch(
                        retrieved_publications,
                        known_abstracts=known_abstracts,
                    )
                else:
                    enriched_publications = retrieved_publications

                validations = [
                    validate_canonical_query(search_query, publication) for publication in enriched_publications
                ]
                normalized_publications = [
                    publication
                    for publication, validation in zip(enriched_publications, validations, strict=True)
                    if validation.status is not CanonicalMatchStatus.NON_MATCH
                ]
                rejected_count = len(retrieved_publications) - len(normalized_publications)
                accepted_count = sum(validation.status is CanonicalMatchStatus.MATCH for validation in validations)
                indeterminate_count = sum(
                    validation.status is CanonicalMatchStatus.INDETERMINATE for validation in validations
                )

                combined_warnings = list(search_run.warnings)
                for w in output.warnings:
                    if w not in combined_warnings:
                        combined_warnings.append(w)
                is_lossless = search_run.is_lossless
                if output.is_lossless is False:
                    is_lossless = False
                if any(validation.status is CanonicalMatchStatus.INDETERMINATE for validation in validations):
                    combined_warnings.append(
                        "Some candidates could not be fully evaluated because a canonically scoped field was missing; they were retained to protect recall."
                    )

                search_run_with_output_metadata = search_run.model_copy(
                    update={
                        "warnings": combined_warnings,
                        "is_lossless": is_lossless,
                    }
                )
                final_search_run = self._finish_search_run(
                    search_run_with_output_metadata,
                    status=SearchRunStatus.COMPLETED,
                    finished_at=self._clock(),
                    records_retrieved=len(retrieved_publications),
                    canonical_accepted_count=accepted_count,
                    canonical_rejected_count=rejected_count,
                    canonical_indeterminate_count=indeterminate_count,
                    errors=[],
                )
                provider_results.append(
                    ProviderSearchResult(
                        search_run=final_search_run,
                        publications=normalized_publications,
                        error=None,
                        total_count=output.total_count,
                        next_cursor=output.next_cursor,
                        has_more=output.has_more,
                    )
                )
                result_provenance.extend(
                    PublicationSearchProvenance(
                        publication=publication,
                        search_run=final_search_run,
                        provider=final_search_run.provider,
                    )
                    for publication in normalized_publications
                )
        normalized_publications = [
            publication
            for provider_result in provider_results
            if provider_result.publications is not None
            for publication in provider_result.publications
        ]
        merged_publications = self._result_merger.merge(normalized_publications)
        post_merge_validations = [
            validate_canonical_query(search_query, publication) for publication in merged_publications
        ]
        final_merged_publications = [
            publication
            for publication, validation in zip(merged_publications, post_merge_validations, strict=True)
            if validation.status is not CanonicalMatchStatus.NON_MATCH
        ]
        execution_finished_at = self._clock()
        duplicate_groups = self._duplicate_group_builder.build(
            normalized_publications,
            created_at=execution_finished_at,
        )
        return SearchExecution(
            canonical_query=search_query,
            provider_results=provider_results,
            normalized_publications=normalized_publications,
            merged_publications=final_merged_publications,
            duplicate_groups=duplicate_groups,
            result_provenance=result_provenance,
            execution_provenance=SearchExecutionProvenance(
                started_at=execution_started_at,
                finished_at=execution_finished_at,
                provider_run_ids=tuple(result.search_run.run_id for result in provider_results),
                total_provider_results=sum(
                    len(result.publications) for result in provider_results if result.publications is not None
                ),
                merged_result_count=len(final_merged_publications),
            ),
        )

    @staticmethod
    def _finish_search_run(
        search_run: SearchRun,
        *,
        status: SearchRunStatus,
        finished_at: datetime,
        records_retrieved: int,
        canonical_accepted_count: int,
        canonical_rejected_count: int,
        canonical_indeterminate_count: int,
        errors: list[str],
    ) -> SearchRun:
        data = search_run.model_dump()
        data.update(
            status=status,
            finished_at=finished_at,
            records_retrieved=records_retrieved,
            canonical_accepted_count=canonical_accepted_count,
            canonical_rejected_count=canonical_rejected_count,
            canonical_indeterminate_count=canonical_indeterminate_count,
            error_count=len(errors),
            errors=errors,
        )
        return SearchRun.model_validate(data)
