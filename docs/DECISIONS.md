# Architectural Decisions

This document records important project decisions that do not require a full ADR.

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

The next active increment is 2.4 — rate limiting.

The verified quality state at the end of the session is:

- 61 tests passing
- Ruff checks passing
- mypy checks passing
- GitHub synchronized
- HomeLab mirror synchronized

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