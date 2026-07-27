# SLR Platform — Project Status

_Last updated: 2026-07-24_

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
- 2.10 provenance mapping to canonical publications

Crossref now provides:

- an asynchronous low-level client for `GET /works`
- validation of query, rows, cursor, and response structure
- Tenacity retry for `httpx.RequestError` and HTTP statuses 429, 500, 502, 503, and 504
- configurable, instance-local asynchronous rate limiting before every physical HTTP attempt, including retries
- injectable monotonic clock and asynchronous sleep for deterministic tests
- cursor pagination across result pages using the standard starting cursor `*` and returning records as an asynchronous iterator
- protection against infinite loops by verifying duplicate/repeated cursor values, ending iteration normally on empty result lists or missing/null cursors, and raising a ValueError for malformed/blank cursor values
- mapping from Crossref Works JSON to the canonical `Publication` domain model
- one-page and cursor-iterator provider methods that attach provenance linked to the normalized DOI, search query, search run, rendered query, and timezone-aware retrieval timestamp
- injectable retrieval clock for deterministic provenance tests

Phase 2.10 — Crossref Provenance: Implemented.

Quality verification for Phase 2.10 must be run locally after pulling the GitHub commits because no GitHub Actions workflow is configured for these commits.

Semantic Scholar completed increments:

- 2.11 basic client and single-page search
- 2.12 offset pagination
- 2.13 provider mapping to Publication
- 2.14 provenance

Semantic Scholar now provides:

- a low-level asynchronous client (`SemanticScholarClient`) for the Graph API paper search endpoint (`/paper/search`)
- support for optional API key authorization via the `x-api-key` request header
- validation of query (non-empty), limit (positive integer), offset (non-negative integer), and fields (non-empty list of non-blank strings)
- single-page search results returned as a list of raw paper records from the response `"data"` field (returning `[]` if missing or empty)
- asynchronous pagination over all results pages using offset pagination driven by the API-returned `next` field
- infinite pagination loop protection raising a `RuntimeError` if a loop is detected
- limit parameter supporting maximum result bounds (`max_results`)
- mapping from Semantic Scholar paper records to the canonical `Publication` domain model
- search provenance metadata capturing for each mapped publication

Google Scholar Import completed increments:

- 3.1 RIS parser
- 3.2 RIS -> Publication mapping
- 3.3 Google Scholar RIS import
- ImportProvider abstraction

Google Scholar Import now provides:

- a dependency-free sequential RIS file format parser (`parse_ris`) returning dictionaries of tag-to-list-values
- multiline field continuation: plain-text lines inside a record are folded into the previous field value
- `map_ris_record(record, *, source)` — pure mapping function from one parsed RIS record to a canonical `Publication`
  - title (TI / T1 / CT precedence), abstract (AB / N2), authors (AU / A1 with comma-format name parsing)
  - publication year (PY / Y1), document type (TY → DocumentType; absent/unknown → OTHER)
  - DOI normalization via project's `normalize_doi` helper
  - provenance with DOI as `source_record_id`, title as fallback when DOI absent
- `import_ris(content)` — Google Scholar RIS import entry point; composes `parse_ris` + `map_ris_record` with `source="google_scholar"`
- `ImportProvider` — a structural contract based on `typing.Protocol`
  - exposes only `import_publications(content: str) -> list[Publication]`
  - implemented by `GoogleScholarImportProvider`
  - preserves `import_ris(content)` as a compatibility wrapper
- unchanged RIS parser and mapper responsibilities
- a contract test confirming that `GoogleScholarImportProvider` structurally satisfies `ImportProvider`

Phase 3.1 — RIS Parser: Completed.
Phase 3.2 — RIS → Publication Mapping: Completed.
Phase 3.3 — Google Scholar RIS Import: Completed.
ImportProvider abstraction: Completed.

BibTeX Import completed increments:

- 4.1 BibTeX parser
- 4.2 BibTeX -> Publication mapping
- 4.3 BibTeX ImportProvider
- 4.4 Contract tests

BibTeX Import now provides:

- `BibTeXRecord` — a `TypedDict` separating `entry_type`, `citation_key`, and the `fields` dictionary
- `parse_bibtex(content: str) -> list[BibTeXRecord]` — public API for parsing serialized BibTeX content into raw records
- deterministic character-by-character parsing supporting:
  - multiple records
  - braced and quoted values
  - nested braces and multiline values
  - `%` comments outside values and ignored `@comment` entries
  - both trailing commas and omitted trailing commas
- lowercase normalization of entry types and field names while preserving citation keys
- raw value preservation without domain interpretation or LaTeX normalization
- explicit `ValueError` failures for invalid syntax and unsupported `@string` and `@preamble` constructs
- no new dependencies and no changes to the RIS parser, domain model, or `ImportProvider`
- `map_bibtex_record(record, *, source)` — pure mapping function from one `BibTeXRecord` to a canonical `Publication`
  - required title, optional abstract, and four-digit publication year
  - personal authors split on `and` outside braces; comma and given-name-first formats supported
  - corporate authors enclosed in protective braces represented by `display_name` only
  - BibTeX entry types mapped to existing `DocumentType` values, with unknown types falling back to `OTHER`
  - DOI normalized by the existing `normalize_doi` helper
  - venue selected in `journal` → `booktitle` → `publisher` order
  - provenance records the source and `bibtex_to_publication` transformation
  - `source_record_id` uses normalized DOI, then citation key, then title
  - LaTeX text is preserved without decoding
- `BibTeXImportProvider` — thin orchestration layer implementing `ImportProvider` structurally
  - exposes `import_publications(content: str) -> list[Publication]`
  - accepts keyword-only `source`, defaulting to `"bibtex"`
  - composes `parse_bibtex` → `map_bibtex_record` → `list[Publication]`
  - preserves input record order and returns `[]` for empty input
  - propagates parser and mapper errors without wrapping, skipping, or partial success
  - performs no I/O and keeps no per-import state
  - adds no dependencies and changes neither parser, mapper, RIS, domain models, nor `ImportProvider`
- shared, parameterized `ImportProvider` contract tests covering `GoogleScholarImportProvider` and `BibTeXImportProvider`
  - structural compatibility through the public `import_publications` API
  - empty and whitespace-only input
  - single and multiple records, including ordering and `Publication` result types
  - stateless consecutive calls
  - error propagation without partial success
  - stable domain equivalence across repeated imports, excluding dynamic timestamps and generated record metadata
  - no production-code, protocol, domain-model, or dependency changes

Phase 4.1 — BibTeX Parser: Completed.
Phase 4.2 — BibTeX -> Publication Mapping: Completed.
Phase 4.3 — BibTeX ImportProvider: Completed.
Phase 4.4 — ImportProvider Contract Tests: Completed.

BibTeX Import — Phase 4: Completed.

Quality status:

- 435 tests passing
- Ruff checks passing
- mypy checks passing
- `git diff --check` passing

Harmonization plan:

- align canonical mapping quality before the Search Engine and review workflow
- begin with a field-by-field parity specification for OpenAlex, Crossref, and Semantic Scholar
- use Crossref as the richest current reference without treating it as the sole specification
- extend OpenAlex mapping for fields actually available from that provider
- include Semantic Scholar in the cross-provider consistency assessment
- limit normalization work to the provider → canonical model boundary
- extract shared mapper helpers only after real duplication has been identified
- introduce no new product functionality
- exclude deduplication, screening, and the later global Normalization phase

Harmonization completed increments:

- 5.1 Canonical mapping parity specification
- 5.2 OpenAlex provider mapping parity

Canonical mapping parity specification now provides:

- `docs/MAPPING_PARITY.md` as the decision source for provider → canonical `Publication` quality
- coverage of OpenAlex, Crossref, and Semantic Scholar
- a 29-row canonical field matrix with required, provider-data-dependent, generated, and deferred classifications
- a code-confirmed baseline for each provider and an explicit target after Harmonization
- required title and complete search provenance expectations
- explicit OpenAlex parity gaps for 5.2
- normalization decisions deferred to 5.3 and evidence-based helper candidates deferred to 5.4
- lightweight completeness and consistency tests with no xfail cases
- no production-code or dependency changes

Phase 5.1 — Canonical Mapping Parity Specification: Completed.

OpenAlex provider mapping parity now provides:

- public, deterministic `OpenAlexProvider.map_work()` mapping without I/O or search context
- separate provenance orchestration used by `search()` and `iterate()`
- title mapping with a `display_name` fallback
- deterministic abstract reconstruction from `abstract_inverted_index`
- provider-ordered authors, OpenAlex and ORCID author identifiers, and institutional affiliations
- publication year/date mapping with invalid optional values omitted and explicit-year conflict handling
- DOI and provider-native OpenAlex work identifiers
- venue name/type and ordered, deduplicated ISSN-L/ISSN identifiers
- document type, language, valid HTTP(S) URLs, and explicit open-access status
- no inferred publisher from host organization and no inferred keywords from topics/concepts
- malformed optional fields omitted without rejecting an otherwise valid publication
- OpenAlex-specific helpers kept local, with no shared mapper utilities or new dependencies
- no domain-model, HTTP-client, Crossref, or Semantic Scholar changes

Phase 5.2 — OpenAlex Provider Mapping Parity: Completed.

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

Harmonization — Phase 5.3 Cross-provider normalization consistency.

Future architectural work:

- Harmonization
  - 5.1 Canonical mapping parity specification
  - 5.2 OpenAlex provider mapping parity
  - 5.3 Cross-provider normalization consistency
  - 5.4 Shared mapper utilities
  - 5.5 Cross-provider mapping contract tests

---

# Important notes

Infrastructure is considered finished.

Future work focuses on scientific functionality, not framework development.

Every larger change should be implemented as a reviewable PR-sized increment.

The roadmap is the authoritative sequence of work. Additional engineering tasks should be included within existing roadmap items unless a deliberate roadmap change is approved.
