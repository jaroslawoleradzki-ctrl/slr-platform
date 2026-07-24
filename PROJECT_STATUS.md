# SLR Platform — Project Status

_Last updated: 2026-07-23_

## Current status

Project is in active development.

Infrastructure and project architecture are considered stable.

Current version:

v0.1.0

Current development phase:

Phase 2 — Search Providers.

---

# Completed

## Infrastructure

- Python project initialized
- FastAPI running
- pytest configured
- development scripts
- Docker-ready architecture
- GitHub repository
- HomeLab mirror
- SSH authentication to GitHub
- single `git push` pushes to GitHub and HomeLab

## Documentation

Completed:

- ADR documents
- logging standard
- testing standard
- data model draft
- JSON schema
- project architecture

## Refactoring

Completed migration:

app/

    domain/
    providers/
    services/
    storage/
    config/

Old architecture removed.

## Phase 1 — Domain Model

Completed:

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

Phase 1 is considered complete.

## Phase 2 — Search Providers

OpenAlex completed increments:

- 2.1 client
- 2.2 cursor pagination
- 2.3 retries implemented with Tenacity
- 2.4 configurable asynchronous rate limiting
- 2.5 provenance mapping to canonical publications

OpenAlex now provides:

- an asynchronous HTTP client for the Works API
- cursor pagination across result pages
- Tenacity retry for transient request failures and retryable HTTP statuses
- configurable, instance-local asynchronous rate limiting for every physical HTTP attempt
- mapping from OpenAlex Works to `Publication` with provenance linked to the source record, search query, search run, rendered query, and retrieval timestamp

Phase 2.5 — OpenAlex Provenance: Completed.

Crossref completed increments:

- 2.6 asynchronous Works API client
- 2.7 retry and configurable asynchronous rate limiting
- 2.8 cursor pagination
- 2.9 provider mapping to Publication

Crossref now provides:

- an asynchronous low-level client for `GET /works`
- validation of query, rows, cursor, and response structure
- Tenacity retry for `httpx.RequestError` and HTTP statuses 429, 500, 502, 503, and 504
- configurable, instance-local asynchronous rate limiting before every physical HTTP attempt, including retries
- injectable monotonic clock and asynchronous sleep for deterministic tests
- cursor pagination across result pages using the standard starting cursor `*` and returning records as an asynchronous iterator
- protection against infinite loops by verifying duplicate/repeated cursor values, ending iteration normally on empty result lists or missing/null cursors, and raising a ValueError for malformed/blank cursor values
- mapping from Crossref Works JSON to the canonical `Publication` domain model

Phase 2.9 — Crossref Provider Mapping: Completed.

Quality status for the current increment:

- 154 tests passing
- Ruff checks passing
- mypy checks passing
- `git diff --check` passing

---

# Current architecture

FastAPI

↓

Workflow

↓

Services

↓

Providers

↓

Domain models

↓

Storage

---

# Development principles

The project follows:

- Clean Architecture
- Domain Driven Design (lightweight)
- provenance-first
- reproducible science
- plugin providers
- YAML configuration
- OpenAlex first

Every feature must:

- have tests
- be documented
- preserve provenance
- avoid hidden AI decisions

---

# Next milestone

Continue the incremental Crossref implementation.

Next roadmap increment:

- Crossref — provenance

After that:

- Semantic Scholar
- Google Scholar manual import

---

# Important notes

Infrastructure is considered finished.

Future work focuses on scientific functionality, not framework development.

Every larger change should be implemented as a reviewable PR-sized increment.

The roadmap is the authoritative sequence of work. Additional engineering tasks should be included within existing roadmap items unless a deliberate roadmap change is approved.
