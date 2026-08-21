# Semantic Scholar Integration

## Status

Planned for a future SLR Platform release, tentatively v0.5.5.

Semantic Scholar should be restored as a Live API Provider alongside:

- OpenAlex
- Crossref
- Semantic Scholar

There is currently no identified technical reason to permanently disable Semantic Scholar.

## Rationale

Semantic Scholar provides an additional scholarly discovery source and may improve literature retrieval coverage compared with relying only on OpenAlex and Crossref.

Different scholarly databases/APIs have partially different coverage.

SLR Platform already contains normalization and deduplication stages, so overlap between providers is expected and should be handled downstream rather than used as a reason to disable an additional provider.

## API

Use the official Semantic Scholar Academic Graph API.

Before implementation, verify the current official API documentation because limits and endpoint behavior may change.

Preferred integration should support:

- paper search
- pagination/bulk retrieval where appropriate
- controlled selection of returned fields
- provider-specific identifiers
- DOI when available
- title
- authors
- year/publication date
- venue
- abstract when available
- citation-related metadata only if useful to the existing canonical record model

Do not collect fields merely because the API exposes them.

## Authentication

Support an optional backend environment variable:

SEMANTIC_SCHOLAR_API_KEY

The API key must remain backend-only.

Never expose it in frontend code, browser requests, repository files, logs, or committed configuration.

Use the official authentication header required by Semantic Scholar (currently x-api-key), but verify this against current official documentation during implementation.

## Rate limiting and resilience

Semantic Scholar must be treated as a rate-limited external provider.

Implementation must include:

- explicit request timeout
- handling of HTTP 429
- bounded retries
- exponential backoff
- useful error reporting
- no infinite retry loops
- graceful provider failure without corrupting the SLR project
- preservation of already retrieved records if a later page/request fails, consistent with existing ingestion semantics

Use bulk/batch endpoints where appropriate instead of unnecessary per-record requests.

Do not hardcode assumptions about current rate limits without verifying official documentation.

## Result limits

Verify current Semantic Scholar search result limits during implementation.

If normal search cannot retrieve the complete requested result set, use the appropriate bulk search/pagination mechanism where supported.

SLR Platform must not silently truncate results.

If an API limit prevents complete retrieval, this must be visible to the researcher and recorded in ingestion metadata/audit information where supported by the existing architecture.

## Normalization

Semantic Scholar results must enter the SAME normalization pipeline as other providers.

Do not create a Semantic-Scholar-specific parallel publication model.

Expected flow:

Semantic Scholar API
    ->
provider ingestion
    ->
raw/provider record
    ->
existing normalization pipeline
    ->
canonical record
    ->
existing deduplication pipeline

## Deduplication

Overlap with OpenAlex, Crossref and manual imports is expected.

Use the existing deduplication architecture.

DOI should be used where available, together with the existing identifier/metadata matching rules.

Do not deduplicate records inside the Semantic Scholar provider using a separate incompatible mechanism.

## PRISMA implications

Semantic Scholar must be counted as a Live API Provider in PRISMA identification metrics.

PRISMA should preserve provider-level provenance so the researcher can determine how many records were identified through:

- OpenAlex
- Crossref
- Semantic Scholar
- manual imports

The aggregate recordsIdentifiedProviders metric must remain consistent with these provider-level counts.

Deduplication must then be reflected separately in later PRISMA stages.

## Reproducibility

For each Semantic Scholar search/import run, preserve as much of the following as the existing ingestion architecture supports:

- provider
- search query
- execution timestamp
- result count
- retrieval completeness
- relevant API/search mode
- errors or truncation
- provider record identifiers

The objective is to make the SLR search process auditable and reproducible.

## Scope proposed for v0.5.5

Tentative implementation scope:

1. Restore Semantic Scholar as an available provider.
2. Add backend API client/provider implementation.
3. Add optional API-key configuration.
4. Implement pagination/bulk retrieval.
5. Implement rate-limit handling and retry/backoff.
6. Map results into the existing ingestion/normalization pipeline.
7. Preserve provider provenance.
8. Integrate Semantic Scholar counts with Live PRISMA metrics.
9. Add backend tests using mocked Semantic Scholar responses.
10. Add frontend/provider-selection tests where necessary.
11. Update documentation and environment-variable examples.

## Explicitly out of scope

Do not add:

- AI/LLM functionality
- automatic relevance assessment
- AI-assisted screening
- Semantic Scholar recommendation algorithms unless separately approved
- a separate Semantic Scholar database
- frontend exposure of the API key

## Pre-implementation verification

Before starting v0.5.5, inspect the current repository and verify:

- why Semantic Scholar was previously disabled
- whether partial implementation already exists
- existing provider interface
- OpenAlex implementation
- Crossref implementation
- ingestion audit model
- normalization contracts
- PRISMA metrics introduced in v0.5.4

Reuse existing architecture wherever possible.

Status: IMPLEMENTED (working tree; not yet committed/released)
Target: v0.5.5
Dependency: v0.5.4 Live PRISMA Metrics
Implementation decision: restored via the existing SemanticScholarClient/SemanticScholarProvider and
wired into LiveSearchService; search_with_raw with offset pagination, deterministic record identity,
rate-limit handling (1 req/s), bounded retries with exponential backoff and Retry-After support,
explicit truncation warnings, optional SEMANTIC_SCHOLAR_API_KEY (backend-only), frontend provider
selection enabled, PRISMA counted through existing provider import history. API facts verified against
official Semantic Scholar Academic Graph documentation: GET /graph/v1/paper/search with query/limit/
offset/fields params, x-api-key header, offset-based pagination (total/offset/next), 1000-result cap on
relevance search, ~1 req/s with an API key.
