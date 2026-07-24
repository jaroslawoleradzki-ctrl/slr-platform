# Architectural Decisions

This document records important project decisions that do not require a full ADR.

---

## 2026-07-24

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
