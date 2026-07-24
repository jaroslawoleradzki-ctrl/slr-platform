# Architectural Decisions

This document records important project decisions that do not require a full ADR.

---

## 2026-07-24

### Semantic Scholar provenance

Implemented provenance mapping support in `SemanticScholarProvider.map_paper` to record search query details in the `provenance` field, mirroring OpenAlex's provenance construction.

Key decisions:
- **Provenance Context**: The `map_paper` method accepts `search_run`, `search_query`, and `retrieved_at` as required keyword-only arguments.
- **Mandatory paperId**: `paperId` is required to populate the `source_record_id` field in the `ProvenanceEntry`. If missing or blank (including whitespace-only strings), a `ValueError` is raised.
- **Provenance Construction**: Creates a single `ProvenanceEntry` with `source="semantic_scholar"`, `source_record_id=paper_id`, and search query metadata.

Verified quality state:
- 190 tests passing
- Ruff checks passing
- mypy checks passing
- `git diff --check` passing

---

### Semantic Scholar provider mapping to Publication

Added a mapping layer from Semantic Scholar Graph API paper records to the canonical `Publication` domain model via `SemanticScholarProvider.map_paper`.

Key decisions:
- **Title Mapping**: Requires a valid non-blank title string, raising `ValueError` if missing or blank.
- **Author Mapping**: Extracts author display name (`name` field) and skips records where a non-blank name cannot be formed, preserving the API-returned order.
- **Date Conflict Resolution**: If `publicationDate` and `year` disagree, `publication_year` is preserved and `publication_date` is omitted to avoid creating an internally inconsistent `Publication`.
- **Venue and ISSN**: Mapped from `publicationVenue` dict (including name, type, and ISSN list) with fallback to the top-level string `venue` if the name is not set.
- **Publication Type**: Uses a lookup table to translate `publicationTypes` list entries to canonical `DocumentType` values, falling back to `DocumentType.OTHER` for unrecognized types, and `None` if missing.
- **Identifiers**: DOI and PMID (from `externalIds.get("PubMed")`) are mapped to canonical identifiers, and `paperId` is stored as `IdentifierType.OTHER` with `source="semanticscholar"`.
- **Roadmap Boundaries**: Provenance is explicitly left empty (`[]`) for this increment.

Verified quality state:
- 187 tests passing
- Ruff checks passing
- mypy checks passing
- `git diff --check` passing

---

### Semantic Scholar offset pagination

`SemanticScholarClient` now supports multi-page result retrieval via `iterate_papers(...)` using offset pagination.

Key decisions:
- **API Suffix**: Directly query `{base_url}/paper/search` to cleanly capture response envelope pagination metadata fields (such as `next`).
- **Pagination Source of Truth**: The iterator relies solely on the `next` value returned in the response payload to determine the next page's offset.
- **Immediate Termination**: If a response's `"data"` field is empty or missing, iteration terminates immediately without processing `next` or firing any further HTTP requests.
- **Infinite Loop Protection**: If the `next` offset matches the current offset or was already visited in the same pagination sequence, iteration is halted with a `RuntimeError`.
- **API Error Handling**: Unparseable or non-integer `next` values trigger a `RuntimeError` rather than a `ValueError` (which remains reserved for input parameter validation).
- **Result Limit**: Supports an optional `max_results` constraint, terminating iteration cleanly after yielding the specified limit.

Verified quality state:
- 178 tests passing
- Ruff checks passing
- mypy checks passing
- `git diff --check` passing

---

### Semantic Scholar basic client and single-page search

Added a low-level asynchronous client `SemanticScholarClient` in `app/providers/semantic_scholar.py` to search papers using the Semantic Scholar Graph API.

Key decisions:
- **Client Configuration**: `SemanticScholarClient` accepts `http_client`, `base_url`, and an optional `api_key`. If an API key is provided, it is sent via the `x-api-key` request header.
- **Search Suffix**: The API request is sent to the `/paper/search` endpoint relative to the configured `base_url`.
- **Search Suffix Slashes**: `base_url` trailing slashes are stripped to avoid malformed URL paths.
- **Validation**: Added validation ensuring query is non-empty, limit is positive, offset is non-negative, and fields is a non-empty list of non-blank strings. If `fields` is `None`, the fields parameter is omitted from the request.
- **Raw Records**: The `search_papers` method returns raw paper records from the response's `"data"` field as a list of dictionaries, returning `[]` if `"data"` is missing or null, without mapping them to `Publication`.
- **Error Propagation**: Standard HTTP errors are propagated via `raise_for_status()`.

Verified quality state:
- 169 tests passing
- Ruff checks passing
- mypy checks passing
- `git diff --check` passing

---

### Crossref provider mapping to Publication

`CrossrefProvider` now maps raw Crossref Works API records to the canonical `Publication` domain model via `map_work`.

Key decisions:
- **Title Mapping**: Requires a list of titles; maps the first non-blank string, raising `ValueError` if missing or entirely blank. No fallback fields are used.
- **DOI Normalization**: Normalizes DOIs to lowercase and strips whitespaces. Kept in `identifiers` list, not exposed as individual fields.
- **Author Mapping**: Maps given/family names, ORCID (normalized from URLs by extracting the trailing path segment), and institutional affiliations (requires a non-empty name). Skips individual authors if a non-blank `display_name` cannot be formed, without failing the mapping of the entire publication.
- **Date Resolution**: Falls back through the hierarchy: `published-print` → `published-online` → `published` → `issued`. Parses standard date parts, mapping 3-part dates to both `publication_year` and `publication_date`, and 1/2-part dates to `publication_year` only, without introducing artificial days/months.
- **Venue and ISSN**: Mapped from the first non-empty `container-title` to `Venue`. ISSN values are mapped to `Venue.identifiers`. ISBN mapping is omitted for this increment.
- **Document Type Mapping**: Table-based mapping translates Crossref types to canonical `DocumentType` values, falling back to `DocumentType.OTHER` for unknown non-empty types, and `None` for missing ones.
- **Abstract Cleanup**: Cleans up HTML/XML/JATS tags and entity encodings from `abstract` string without external libraries, normalizing whitespaces.
- **Strict Boundary (No Provenance)**: The `provenance` field is intentionally left empty (`[]`) for this increment to respect roadmap boundaries.

Verified quality state:
- 154 tests passing
- Ruff checks passing
- mypy checks passing
- `git diff --check` passing

---

### Crossref cursor pagination

`CrossrefClient` now supports cursor-based pagination via the `iterate_works` asynchronous generator.

Key decisions:
- **Starting Cursor**: The initial request uses the standard starting cursor `*`.
- **Response Validation**: Response payloads are validated for `message.items` and `message.next-cursor` structure. A malformed `next-cursor` (present but not a string or blank) raises a `ValueError`.
- **Termination Conditions**: The iteration terminates normally when `items` is empty, when `next-cursor` is missing or null, or when the returned `next-cursor` equals the current cursor or a previously requested cursor (preventing infinite loops). Malformed cursor values (blank or non-string values) raise a `ValueError` instead of ending the iteration.
- **Optional Record Limit**: An optional `limit` parameter was introduced. If specified, the generator yields exactly up to the limit and stops without performing any unnecessary further HTTP page requests.
- **HTTP Reuse**: The pagination relies strictly on the existing `search_works` method, ensuring that rate limiting, retry semantics, and response structural validations are automatically inherited without duplicating HTTP logic.

Verified quality state:
- 134 tests passing
- Ruff checks passing
- mypy checks passing
- `git diff --check` passing

---

## 2026-07-23

### Crossref retry and asynchronous rate limiting

`CrossrefClient` uses Tenacity for retries and a small custom asynchronous limiter for request pacing.

Retry covers only physical HTTP attempts and is limited to:

- `httpx.RequestError`
- HTTP 429
- HTTP 500
- HTTP 502
- HTTP 503
- HTTP 504

Other client errors, argument validation failures, and response JSON validation failures are not retried. The last original exception is propagated after exhaustion by using `reraise=True`.

Rate limiting is configured per `CrossrefClient` instance with `requests_per_second`:

- `None` disables limiting
- a finite positive number enables limiting
- zero, negative values, booleans, `NaN`, and positive or negative infinity are rejected

The limiter enforces a minimum interval between the starts of physical HTTP attempts. It is executed before every attempt, including retry attempts. An instance-local `asyncio.Lock` serializes request-start reservations, but the lock is released before HTTP I/O begins.

The monotonic clock and asynchronous sleep function are injectable, which keeps timing tests deterministic and avoids real waiting.

The Crossref implementation intentionally follows the proven OpenAlex behavior without introducing a shared base class, retry mixin, or shared rate-limiter abstraction at this stage.

Verified quality state:

- 121 tests passing
- Ruff checks passing
- mypy checks passing
- `git diff --check` passing

---

### OpenAlex provenance mapping

`OpenAlexProvider` maps OpenAlex Works responses to canonical `Publication` models. `OpenAlexClient` remains a low-level HTTP client responsible only for communication, retry, rate limiting, response validation, and cursor pagination.

Each mapped publication receives a `ProvenanceEntry` containing:

- `source`
- `source_record_id`
- `query_id`
- `run_id`
- `rendered_query`
- `retrieved_at`

The search context is passed explicitly through `SearchRun` and `SearchQuery`. The retrieval clock is injectable so provenance timestamps remain deterministic in tests.

Archiving full raw JSON responses and storing publications or provenance are outside the scope of Phase 2.5. They remain responsibilities of later roadmap increments.

---

### OpenAlex asynchronous rate limiting

The OpenAlex provider uses a small custom asynchronous rate limiter rather than a third-party rate-limiting library.

Reasons:

- the required behavior is limited to enforcing a minimum interval between request starts
- adding a new external dependency would be disproportionate to the scope
- the limiter remains independent from Tenacity retry handling
- injected `clock` and `sleep` functions make timing behavior deterministic in tests

The limiter is configured with `requests_per_second`:

- a finite positive number enables limiting
- `None` disables limiting
- zero, negative values, `NaN`, and positive or negative infinity are rejected

The limiter state and `asyncio.Lock` belong to each `OpenAlexClient` instance. The lock serializes request-start reservations, but it is released before the HTTP response is awaited.

Rate limiting is applied immediately before every physical HTTP attempt. Therefore, it covers:

- normal search requests
- Tenacity retry attempts
- cursor-pagination requests

This preserves the existing retry and pagination semantics while ensuring that all outbound OpenAlex requests respect the configured rate.

Verified quality state:

- 73 tests passing
- Ruff checks passing
- mypy checks passing
- `git diff --check` passing

---

## 2026-07-22

### Retry implementation

The OpenAlex provider uses Tenacity for retry handling instead of a custom retry loop.

Reasons:

- retry logic will be reusable across multiple providers
- Tenacity supports asynchronous code
- exponential backoff and retry conditions are provided by a mature library
- this reduces custom infrastructure code and maintenance
- retry logic is not part of the scientific contribution of the project

The retry policy covers transient request failures and retryable HTTP statuses. Non-retryable client errors are propagated immediately.

---

### Roadmap governance

The roadmap is the authoritative sequence of implementation work.

New phases or intermediate stages should not be introduced implicitly.

Additional engineering activities, such as integration tests, should normally be treated as part of an existing roadmap item unless a deliberate decision is made to extend or change the roadmap.

---

### Phase 1 completion

Phase 1 — Domain Model is considered complete.

It includes:

- Publication
- Author
- Affiliation
- Venue
- Identifier
- SearchRun
- SearchQuery
- Provenance
- ScreeningDecision
- screening decision enum
- decision rationale
- reviewer or supporting agent attribution
- audit trail
- backward compatibility contract tests

---

### OpenAlex implementation status

Completed increments:

- 2.1 client
- 2.2 cursor pagination
- 2.3 retry with Tenacity
- 2.4 asynchronous rate limiting
- 2.5 provenance mapping

The next active increment is the Crossref provider implementation.

---

## 2026-07-21

### Infrastructure completed

The project infrastructure is considered stable.

Completed:

- GitHub repository
- HomeLab mirror
- SSH authentication
- FastAPI
- pytest
- development environment
- Docker-ready architecture

Future work should focus on scientific functionality rather than infrastructure.

---

### Architecture

The project adopts a lightweight Domain Driven Design.

Main layers:

- Domain
- Services
- Providers
- Workflow
- Storage

FastAPI acts only as the API layer.

---

### Scientific principles

The platform follows:

- provenance-first
- reproducibility
- deterministic processing
- human-in-the-loop

LLMs may assist the reviewer but must never make autonomous scientific decisions.

---

### Search strategy

The first implemented provider will be OpenAlex.

Additional providers will be added incrementally.

---

### Development strategy

Development proceeds in small reviewable increments.

Each increment should:

- pass tests
- include documentation
- preserve backward compatibility whenever practical
- be committed as an independent logical change

---

### Long-term vision

The SLR Platform is intended to become a reusable research tool rather than software dedicated only to the current PhD project.
