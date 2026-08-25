# SLR Platform — Project Status

_Last updated: 2026-08-25_

## Current status

Project is in active development.

Infrastructure and project architecture are considered stable.

Current branch:

development

Current version:

v0.6.4

Current release status:

Phase 9 Data Extraction is formally completed and released through v0.4.9.
Phase 10 Data Synthesis is complete in v0.5.0.
Phase 11 — Integrated GUI MVP — v0.5.4 delivers authoritative backend PRISMA
funnel metrics powering the live PRISMA 2020 flow diagram on the Exports page.
v0.5.5 restores Semantic Scholar as a fully functional Live API Provider
with rate-limited search, pagination, provenance, and PRISMA integration.
v0.5.6 adds manual import source provenance (Google Scholar, Scopus, Web of Science,
PubMed, EBSCO, ProQuest, Other) with optional labels, provenance preservation
through normalization/deduplication, and PRISMA manual source breakdown.
v0.5.7 implements canonical duplicate merge (separating reviewer decisions from
technical merge lifecycle, sqlite-based atomic merges, supersession tracking,
downstream active-only filtering, and integrity audit support).
v0.5.8 cleans up deprecated FastAPI/Starlette HTTP 422 status constants.
v0.6.1 completes Stage 9 research exports and PRISMA 2020 reporting.
v0.6.2 restores Semantic Scholar relevance-search compatibility through explicit
provider-specific plain-text query rendering with auditable lossy translation.
v0.6.3 removes the unsupported Semantic Scholar `language` response field while
retaining v0.6.2 query rendering; OpenAlex and Crossref are unchanged.
v0.6.4 fixes post-query language filtering so Semantic Scholar records with an
unknown language are no longer incorrectly discarded; unknown language is not
treated as a mismatch, language is never inferred, and known language values
remain strictly filterable.

Current development phase:

Phase 10 — Data Synthesis is complete through Tasks 10.1–10.8 and released in
v0.5.0.

Phase 10 provides researcher-controlled deterministic synthesis with
terminology classification, the Lean–EE Analytical Matrix, mechanism,
context, and Research Gap synthesis, immutable Synthesis Snapshots with
deterministic identity and JSON/CSV exports, project isolation and
traceability, COMPLETE-only eligible evidence semantics, and criterion-level
QA integration. The application has no built-in AI/LLM functionality.

Phase 6.7 & Phase 6.8 Workflow State:
- **Phase 6.7 (Modules 1–4 Functional Workflow)**: ✅ Completed (6.7.1, 6.7.2a, 6.7.2b).
- **Phase 6.8 (End-to-End Search Workflow)**: 🟨 Partial / In Progress
  - 6.8.1 Search Strategy Backend — ✅ Completed
  - 6.8.2 Provider-Specific Query Rendering — ✅ Completed (`OpenAlexQueryRenderer`, `CrossrefQueryRenderer`, `RenderedQuery` lossy tracking)
  - 6.8.3 Search Orchestrator — ✅ Completed (`SearchEngine` multi-provider execution, merging, provenance)
  - 6.8.4 Search Execution API — 🟨 Partial (`POST /executions` live execution without durable run GET by ID)
  - 6.8.5 Search Execution Persistence — 🟨 Partial (publications & strategy durable; `SearchRun` & raw response archive transient)
  - 6.8.6 Search Strategy GUI Integration — ✅ Completed
  - 6.8.7 Sources Search Execution GUI — ↪ Superseded by Search Strategy execution workflow
  - 6.8.8 GUI Import Integration — ✅ Completed (`POST /imports` RIS/BibTeX upload & history)
  - 6.8.9 Publication Intake Summary — ✅ Completed (`SourcesSummaryService` read model & GET endpoint)

Screening prerequisites resolved in v0.3.3:
- Authoritative `SearchResultSnapshot` records retain canonical provider metadata
  and provenance for new live-search imports.
- `ScreeningInputService` derives a stable, non-destructive canonical input set;
  pending duplicate groups and merge conflicts explicitly block readiness.

State of Phase 7 — Screening:
- v0.3.8 is integrated and automated verification is complete; Manual Acceptance remains pending after Phase 8 integration.
- Phase 7 — Screening implementation is complete and integrated through 7.9;
  automated verification is complete, with Manual Acceptance pending after
  Phase 8 integration on development.
- Phase 7.1 — Screening Criteria Domain Model is ✅ Completed (`ScreeningCriterion`, `ScreeningCriterionType`, `ScreeningCriterionStage`, validation, unit tests).
- Phase 7.2 — Screening Criteria Persistence and API is ✅ Completed (SQLite schema `0007_screening_criteria.sql`, repository, project isolation, REST API, DTOs, tests).
- Phase 7.3 — Screening Configuration GUI is ✅ Completed (ScreeningCriteriaList, ScreeningCriterionCard, ScreeningCriterionModal, projectApiService adapter, validation, 22 frontend tests).
- Phase 7.4 — Screening Decision Domain and Persistence is ✅ Completed (ScreeningDecision, CriterionAssessment, authoritative snapshot, ScreeningDecisionService, SqliteScreeningDecisionRepository, migration 0008, REST API, 22 backend tests).
- Phase 7.5A — Screening Input Prerequisites is ✅ Completed.
- Phase 7.5B — Title & Abstract Screening Backend Workflow is ✅ Completed.
- Phase 7.5C — Title & Abstract Screening GUI is ✅ Completed.
- Phase 7.5D — Automatic Metadata-Based Screening Criteria is ✅ Completed.
- Phase 7.6 — Full-Text Screening is ✅ Completed (reviewer-specific eligibility, derived queue, FULL_TEXT/BOTH criteria, availability metadata, structured exclusion reasons, append-only history, executable GUI, and project deletion integration).
- Phase 7.7 — Screening Audit Trail and Progress is ✅ Completed (unified
  decision audit history, reviewer-specific progress, reporting read models,
  exclusion-reason aggregation, and screening summary/history UI).
- Phase 7.8A — Multi-Reviewer Screening and Conflict Detection is ✅ Completed
  (project/stage reviewer roster, conflict derivation, conflict queue,
  agreement metrics, pending-reviewer visibility, and blind-aware display).
- Phase 7.8B — Conflict Resolution / Adjudication is ✅ Completed (explicit
  resolver workflow, append-only resolution history, stale/current semantics,
  unified audit events, project-level outcome read model, and optimistic
  concurrency).
- Phase 7.9 — Screening Integration and Release is ✅ Implemented and
  integrated (ScreeningEligibilityAdapter, queue hydration, staleness
  revocation, unified `GET /projects/{id}/workflow-status` endpoint, Dashboard
  and Stepper integration, and integration test suites). Automated verification
  is complete; Manual Acceptance remains pending after Phase 8 integration.

Completed in v0.3.8:
- Screening manual-acceptance UX fixes: dark-theme select controls,
  reviewer-team terminology, and unified conflicts/resolutions workflow with
  backward-compatible routing.

Completed in v0.3.9:
- Quality Assessment integration: domain and persistence, project
  configuration, execution workflow, API, workspace, integration tests, and
  project-deletion lifecycle support. Phase 9 Data Extraction remains under
  active development and is not included in this release.

Completed in v0.4.0:
- Phase 9.2 Data Extraction persistence: migration `0018`, immutable versioned
  template catalog, project-scoped records, append-only revisions, batched
  hydration, and atomic project hard-delete integration. Phase 9.3 and later
  increments remain unintegrated.

Completed in v0.4.1:
- Phase 9.3 Data Extraction project configuration and reviewer-scoped
  eligibility: Full-Text `INCLUDE` remains the upstream gate; configured
  Quality Assessment requires a persisted assessment by the same reviewer,
  without scoring, response interpretation, or automatic exclusion. Phase 9.4
  and later increments remain unintegrated.

Completed in v0.4.2:
- Phase 9.4 Data Extraction execution backend: eligibility-enforced,
  template-bound append-only revision submission, server-side validation and
  completeness calculation, provenance/reviewer attribution, and revision
  history API. Phase 9.5 and later increments remain unintegrated.

Completed in v0.4.3:
- Phase 9.5 Data Extraction workspace GUI: project routing, eligible
  publication selection, backend-driven template form controls, provenance
  and revision history drawers, save/completion feedback, and backend
  validation/error handling. Phase 9.6 and later increments remain
  unintegrated.

Completed in v0.4.4:
- Phase 9.6 Extraction Dataset View: real API-backed publication table and
  matrix views, authoritative progress/completeness reporting, filtering,
  navigation, and loading/empty/error states. Phase 9.7 and later increments
  remain unintegrated.

Completed in v0.4.5:
- Phase 9.7 Lean Energy production template: idempotent E1–E14 seed over the
  generic extraction engine, system-bound E1 publication context, and 1:N
  Lean–EE relationships. Phase 9.8 is now the remaining Phase 9 increment.

Completed in v0.4.6:
- Phase 9.8 structured dataset export: generic publication and relationship
  read models with deterministic JSON/CSV exports, current COMPLETE-state
  semantics, canonical publication metadata, provenance, and template version
  traceability.

Completed in v0.3.7:
- Screening integration: stage eligibility adapter, queue hydration,
  staleness revocation, workflow-status API, Dashboard/Stepper integration,
  and backend/frontend integration test suites.

Manual Acceptance remains pending after Phase 8 integration on development.

Completed in v0.3.6:
- Conflict resolution and adjudication with explicit resolver identity and
  rationale, append-only history, stale-resolution handling, unified audit
  events, project-level outcome reporting, and resolution workspace.

Completed in v0.3.5:
- Multi-reviewer screening and conflict detection with roster lifecycle,
  derived agreement/conflict states, queue and reporting extensions, and
  single-reviewer compatibility.

Completed in v0.3.4:
- Screening audit trail and reporting read models, including reviewer-specific
  progress, pipeline transitions, criterion snapshot history, and paginated
  audit/report APIs.

Completed in v0.3.3:
- Project Management: persistent project resource, list/create/open/edit,
  archive/restore, active-project persistence and atomic hard delete.
- SearchResultSnapshot-based live-search import, metadata/provenance retention
  and canonical deduplicated screening input.
- Title & Abstract Screening backend and GUI, reviewer-specific progress and
  append-only decision resume semantics.
- Manual and deterministic metadata-rule criteria with server-authoritative
  automatic assessments.

---

# Completed

## Task 7 — CLI Integrity Check (Data Integrity Cleanup)

- Implemented thin CLI adapter in `app/tools/integrity.py` runnable via `python -m app.tools.integrity PROJECT_ID`.
- Added options for custom database path (`-d` / `--db-path`) and JSON formatting (`--json`).
- Mapped audit results to standard exit codes (`0` for OK/WARNING, `1` for ERROR, `2` for invalid CLI args).
- Added unit parser tests in `tests/unit/tools/test_cli_integrity.py` and integration tests in `tests/integration/tools/test_cli_integrity_integration.py`.

## Task 6 — Test Fixtures (Data Integrity Cleanup)

- Implemented deterministic domain object factories (`make_publication`, `make_author`, `make_import_history`, `make_normalization_execution`, `make_duplicate_decision`) in `tests/fixtures/factories.py`.
- Implemented standard isolated project fixtures (`empty_project`, `project_100`, `project_duplicates`, `project_normalized`) in `tests/fixtures/project_fixtures.py` using standard application project IDs.
- Eliminated redundant mock helpers (e.g. `InMemoryPublicationRepository`) and duplicated object construction in unit tests (`test_integrity_audit_service.py`).
- Added unit test suite `tests/unit/test_fixtures.py` verifying deterministic fixture generation.

## Task 5 — Repository Contracts (Data Integrity Cleanup)

- Clarified and standardized abstract `Protocol` interfaces for all repositories (`ProjectPublicationRepository`, `ImportHistoryRepository`, `NormalizationExecutionRepository`, `DuplicateReviewDecisionRepository`, `SearchStrategyRepository`).
- Decorated all protocol classes with `@runtime_checkable` for explicit runtime typing verification.
- Isolated database driver dependencies (`sqlite3`) from abstract `Protocol` definitions to maintain vendor independence.
- Kept optional transaction connection parameters in SQLite implementation classes to support atomic transactions managed by `SqliteTransactionManager`.
- Added a dedicated contract test suite in `tests/unit/repositories/test_repository_contracts.py`.

## Task 4 — SQLite Constraints Review (Data Integrity Cleanup)

- Completed architectural audit of foreign keys, status CHECK constraints, and query indexes across all 6 pipeline tables (`docs/SQLITE_CONSTRAINTS_REVIEW.md`). Status: ARCHITECTURE COMPLETED — IMPLEMENTATION DEFERRED.

## Version 0.2.4 — Data Consistency and Executable Deduplication

- Repaired the historical `lean_energy` data to contain 535 OpenAlex publications and no synthetic Crossref test publication.
- Added one clearly labelled 391-record OpenAlex history backfill, aligning successful OpenAlex import history with the Working Collection.
- Confirmed Sources & Imports, Working Collection and Normalization at 535 project publications.
- Added explicit manual deduplication execution through the existing backend GET endpoint.
- Added the last execution report and separated it from candidate-group review metrics.
- Added accurate pre-run, in-progress, zero-group, pending-review, fully-reviewed and error states.
- Kept durable APPROVE/REJECT review decisions without implementing physical publication merging.
- Screening remains unavailable and is not part of this increment.

## Version 0.2.3 — Functional Project Dashboard and Sources Aggregation

- Dashboard cards for stages 1–4 are derived from real backend workflow status.
- Dashboard loading, empty, partial-data and partial-failure states are covered by frontend tests.
- Dashboard stage navigation preserves the current `projectId`.
- Search Strategy can be created from an empty state and exposes selectable OpenAlex and Crossref controls without relying on `connected`.
- Semantic Scholar remains visibly unavailable.
- Sources & Imports aggregates successful OpenAlex import deltas while preserving separate history records.
- Stages 5–8 remain unavailable; normalization and deduplication behavior is unchanged.

### Release verification

- Frontend: `npm test` — 98 passed; `npm run build` — passed; `npm run type-check` — passed.
- Backend: `uv run pytest` — 903 passed with one Starlette deprecation warning; `uv run ruff check .` — passed; `uv run mypy app/` — no issues in 80 source files.
- Repository: `git diff --check` — passed.
- Manual OpenAlex data path previously verified with two independent 100-record imports: Working Collection increased from 100 to 200 and import history retained two separate successful entries.

The remaining visual smoke-test checklist is recorded in the release preparation summary because no browser-control instance was available in the validation environment.

## Phase 6.8.1 — Search Strategy Backend

- durable project-scoped Search Strategy storage in SQLite
- migration `0001_search_strategies.sql`
- complete domain validation and JSON serialization
- provider-independent, versioned Search Query trees with AND/OR/NOT
- provider selection for OpenAlex, Crossref, and Semantic Scholar
- REST `GET` and `PUT` at `/projects/{project_id}/search-strategy`
- repository and API unit tests
- no query rendering, search execution, GUI, import, or deduplication changes

## Phase 6.8.6 — Search Strategy GUI Integration

- typed frontend GET/PUT adapter for the persistent Search Strategy resource
- backend strategy is the only source of truth for this screen
- complete editing of questions, groups, terms, operators, constraints and
  provider selection
- dynamic provider-independent Boolean preview
- loading, missing, dirty, saving, saved, validation and failure states
- production GUI restored from `development`
- working GET and PUT persistence
- `Szukaj` persists the strategy and executes the live search
- search results are presented on the Search Strategy page
- `Szukaj` does not navigate to Sources & Imports
- result import workflow is available again

## Version 0.1.9 — Bibliographic upload increment

- `POST /projects/{project_id}/imports` accepts one `.ris` or `.bib` file
- existing RIS/BibTeX parsers and mappers are reused
- parsed publications are stored through the existing project publication
  repository
- Sources uses a real file input and displays upload success/error feedback
- the current project view appends a successful import to its visible list

## Version 0.1.9 — Durable import history

- `GET /projects/{project_id}/imports` returns newest-first import history
- history stores project, filename, format, record count, status, warnings and
  timestamp in SQLite
- Sources reloads history from the backend after project changes and uploads
- provider cards use neutral states because provider executions are not
  persisted for Sources

## Version 0.2.0 — Durable Working Collection & Normalization

- runtime demo repository (`DemoProjectPublicationRepository`) is completely replaced by SQLite Working Collection (`SqliteProjectPublicationRepository`)
- project publications are stored durably in SQLite in `project_publications` table and persist across backend restarts
- shared `ProjectPublicationRepository` boundary connects:
  - import of selected live search results
  - import of RIS and BibTeX files (`POST /projects/{project_id}/imports`)
  - normalization execution reads and canonical updates (`POST/GET /projects/{project_id}/normalization`)
  - duplicate candidate generation and preview service (`GET /projects/{project_id}/duplicate-groups`)
- latest normalization execution summary and audit trail are persisted in SQLite (`SqliteNormalizationExecutionRepository`)

### Known limitations

- OpenAlex returns at most 100 records per execution response; the Search
  Strategy UI can request and append subsequent pages, while full automatic
  retrieval/import of all results remains out of scope
- Crossref is selectable in Search Strategy but has not been manually verified across the complete save, search, import and Sources workflow
- Semantic Scholar remains inactive
- Sources provider status is derived from durable import history; there is no separate persisted provider-status API
- initial project metadata remains demo-backed
- workflow stages 5–8 are not implemented

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

- 731 tests passing
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
- 5.3 Cross-provider normalization consistency
- 5.4 Shared mapper utilities
- 5.5 Cross-provider mapping contract tests

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

Cross-provider normalization consistency now provides:

- one canonical DOI policy across OpenAlex, Crossref, and Semantic Scholar
- one bare ORCID policy for OpenAlex and Crossref authors
- consistent ISSN trimming, final-`X` casing, deduplication, and ordering
- canonical provider-native identifier sources and preserved identifier casing
- consistent whitespace, blank, malformed optional value, and collection-order behavior
- case-insensitive HTTP(S) URL handling without network checks or domain rewriting
- language trimming with lowercase and validation retained by the canonical model
- consistent known/unknown/missing document-type behavior
- consistent OpenAlex and Semantic Scholar venue-type behavior
- faithful provider-ordered author names without entity matching or invented name parts
- consistent year/date validation, inference, and conflict handling
- normalized Crossref DOI provenance identifiers
- provider-local normalization helpers intentionally retained for Phase 5.4
- no global title/author/organization normalization, record merging, or deduplication
- no domain-model changes, shared mapper framework, or new dependencies

Phase 5.3 — Cross-provider Normalization Consistency: Completed.

Shared mapper utilities now provide:

- `app/providers/search/mapping_utils.py` as the single implementation source
- pure `clean_string`, `normalize_doi`, `normalize_orcid`, `normalize_issn`, and `normalize_url` functions
- direct unit tests for every shared normalization contract
- unchanged Phase 5.3 canonical values and provider collection ordering
- unchanged public provider method signatures, provenance, and error messages
- provider-specific dates, authors, abstracts, venue structures, type maps, and provenance retained locally
- no mapper framework, base class, HTTP-client coupling, or new dependency
- no global normalization, record merging, or deduplication

Phase 5.4 — Shared Mapper Utilities: Completed.

Cross-provider mapping contract tests now provide:

- `tests/unit/providers/test_cross_provider_mapping_contract.py`
- a test-only adapter for OpenAlex, Crossref, and Semantic Scholar mappers
- rich provider-native fixtures and stable canonical snapshots
- shared runtime invariants for title, abstract, authors, dates, identifiers, venue, document type, language, URLs, optional defaults, ordering, and malformed optional data
- explicit assertions for provider-data-dependent author, identifier, publisher, and venue-type differences
- complete provider-specific provenance with fixed query, run, retrieval time, rendered query, and normalized source record IDs
- direct mapping tests without HTTP clients, transport mocks, search, or iteration
- filtered snapshots that exclude generated `record_id`, `created_at`, and other model-owned metadata
- no production-code or dependency changes

Phase 5.5 — Cross-provider Mapping Contract Tests: Completed.

Harmonization — Phases 5.1–5.5: Completed.

---

## Phase 3 — Search Engine

Phase 3.1 — Execute queries through a single provider: Completed.

Phase 3.2 — Multi-provider orchestration: Completed.

The provider-independent Search Engine provides:

- `async SearchEngine.execute(search_query: SearchQuery) -> SearchExecution` as its
  asynchronous public entry point
- an ordered sequence of `SearchProvider` instances supplied explicitly to the
  engine constructor
- a minimal structural provider contract consisting of `name` and asynchronous
  `search(*, search_run, search_query) -> list[Publication]`
- sequential provider execution in constructor order
- creation of one separate pending `SearchRun` per provider from the canonical
  query, provider name, generic Boolean rendering, and an injectable run ID
  factory
- a named `SearchExecution` result containing ordered `ProviderSearchResult`
  entries, each associating one run with either the exact publication list
  returned by its provider or the original provider exception
- preservation of provider and publication ordering, list and publication
  identity, and empty results
- isolation of provider errors without wrapping; one failure remains visible in
  its result and does not prevent later providers from running
- focused orchestration tests using a fake provider with no HTTP client,
  transport mock, or concrete search provider
- successes and failures kept separate per provider, with no merge or raw
  response archive
- no deduplication, aggregated provenance, persistence, fallback, retry, or
  parallel execution
- no provider, mapper, HTTP client, domain model, or dependency changes

Phase 3.3 — Raw response archive: Completed.

Raw response archiving now provides:

- `ProviderSearchOutput` as the minimal provider boundary carrying canonical
  publications and ordered raw response pages from the same request
- compatible OpenAlex and Crossref `search()` methods backed by
  `search_with_raw()`, so each HTTP response is fetched once and used for both
  mapping and archiving
- one `RawResponseArchiveEntry` per `SearchRun`, containing archive and run IDs,
  provider, rendered query, timezone-aware capture timestamp, execution status,
  and ordered raw responses
- successful and failed archive entries, with failed entries retaining the
  exception type and message while the original exception remains isolated in
  `ProviderSearchResult`
- an explicit asynchronous `RawResponseArchive` storage protocol injected into
  `SearchEngine`, without a production persistence implementation
- deterministic archive ID and clock injection
- propagation of archive storage failures without wrapping or continuing to a
  later provider
- no merge, deduplication, global search provenance, database persistence, or
  parallel provider execution

Current provider orchestration methods fetch one response page per execution,
which is archived as one ordered page. Existing multi-page record iterators do
not expose page payloads to the Search Engine. If a provider fails before
returning `ProviderSearchOutput`, no safe partial-page channel currently exists;
the failed archive entry therefore stores an empty response list plus error
diagnostics rather than reconstructing raw data.

Phase 3.4 — Merge provider results: Completed.

Provider result merging now provides:

- a separate, stateless `ResultMerger` invoked once after all sequential
  provider executions and required raw-response archive writes complete
- `SearchExecution.merged_publications` alongside unchanged ordered
  `provider_results`
- merge input drawn only from successful provider results, in provider order
  and then publication order
- conservative duplicate detection using only the first DOI identifier on each
  publication, normalized with the existing provider-boundary DOI helper
- preservation of the first publication object encountered for a normalized
  DOI, without copying it or combining any metadata
- preservation of every publication without a DOI as a separate result
- deterministic first-occurrence ordering and a new result list containing the
  original `Publication` objects
- unchanged provider error isolation and raw-response archive behavior
- no title, author, year, venue, PMID, OpenAlex ID, similarity, ranking,
  metadata-field, or provenance merging

Phase 3.5 — Search provenance tracking: Completed.

Search execution provenance now provides:

- final immutable `SearchRun` records with `COMPLETED` or `FAILED` status,
  timezone-aware start and finish timestamps, canonical result counts, and
  stable provider error diagnostics
- provider duration exposed as `ProviderSearchResult.duration_seconds`, derived
  from the final run timestamps without storing duplicate timing state
- one immutable `PublicationSearchProvenance` per publication returned by each
  successful provider, retaining the original publication object and its own
  completed provider `SearchRun`
- separate provenance entries for DOI duplicates from different providers,
  even when DOI-only merge retains only the first publication
- `SearchExecutionProvenance` with execution start, finish, derived duration,
  ordered provider run IDs, total canonical results before merge, and merged
  result count
- deterministic ordering matching provider order and publication order
- an injected clock used for all Search Engine timestamps
- unchanged provider error isolation, required raw-response archiving, DOI-only
  merge, and archive-failure propagation
- no SearchRun persistence, metadata-field provenance, telemetry framework, or
  provenance merging

Phase 3.6 — Search Engine contract tests: Completed.

The Search Engine contract suite now verifies the complete public
`SearchEngine.execute()` orchestration path using the real engine, DOI merger,
domain models, raw archive entry model, and provenance models. Controlled fakes
replace only providers, archive storage, clocks, and UUID factories.

Contract coverage includes:

- single-provider and ordered multi-provider success
- isolated partial provider failure with later-provider continuation
- successful and failed raw-response archive entries
- propagation of archive failures after provider success and provider failure
- DOI-only merge across providers with first-object identity
- separate provenance for every original per-provider publication, including
  DOI duplicates omitted from the merged list
- final provider runs and aggregate execution provenance
- deterministic timestamp and UUID consumption
- empty successful providers and no configured providers
- consistent query, run, archive, result, and provenance associations
- no network clients, local servers, concrete providers, or real HTTP requests

Phase 3 — Search Engine: Completed.

This completion means the planned provider-independent orchestration layer and
its tests are complete. It does not represent deployment of production runtime
storage or external infrastructure.

## Phase 4 — Normalization

Phase 4.1 — Normalization contract and architecture: Completed.

The normalization layer now provides:

- a minimal provider-independent `Normalizer[InputT, OutputT]` structural
  protocol for one canonical value or object
- a documented behavioral contract requiring deterministic, idempotent, and
  non-mutating implementations
- an explicit boundary that excludes record comparison, duplicate decisions,
  merging, ranking, similarity, and collection filtering
- specification tests demonstrating `str → str` and immutable
  `Publication → Publication` implementations
- preservation of canonical record identity fields, provenance, and timestamps
  in the test-domain normalization example
- no concrete production normalizers or additional result models

Existing provider mapping helpers remain in
`app/providers/search/mapping_utils.py` and continue to clean external data at
the provider boundary. They have not been migrated, and `ResultMerger` remains
unchanged. Provider-independent production DOI normalization begins in Phase
4.2. No deduplication behavior is introduced in Phase 4.1.

Phase 4.2 — DOI normalization: Completed.

DOI normalization now provides:

- one provider-independent `DoiNormalizer` implementation and `normalize_doi`
  convenience function as the single source of DOI normalization behavior
- trimming, blank and non-string handling, lowercase output, and
  case-insensitive removal of supported DOI prefixes only at the start
- deterministic and idempotent normalization without strict syntax validation
  or external DOI existence checks
- a compatibility re-export from the provider mapping utilities, so existing
  provider imports keep the same behavior
- direct use of the provider-independent API by `ResultMerger`, with its
  existing DOI-only merge behavior unchanged
- unit and regression coverage for the public normalizer contract, supported
  prefixes, edge cases, idempotence, determinism, protocol compatibility, and
  the legacy provider-layer API
- no title, author, publication-pipeline, fuzzy-matching, similarity,
  confidence-scoring, or new deduplication behavior

Phase 4.3 — Title normalization: Completed.

Title normalization now provides:

- one provider-independent implementation in `app/normalization/title.py`,
  exposed through `TitleNormalizer` and the `normalize_title` convenience
  function
- preservation of the established algorithm: Unicode NFKC normalization,
  case folding, punctuation and symbol replacement with spaces, whitespace
  collapsing, and trimming
- safe `None` results for non-string, blank, and punctuation-only inputs
- deterministic, idempotent, and non-mutating behavior without transliteration
  or language-specific processing
- a compatibility re-export from `app.modules.normalize.service`, allowing the
  legacy `normalize_record` pipeline to use the canonical implementation
- focused unit and regression coverage for normalization behavior, the
  structural protocol, old API compatibility, and legacy record normalization
- no author normalization, publication normalization pipeline, fuzzy matching,
  similarity scoring, stop-word removal, stemming, or lemmatization

Phase 4.4 — Author normalization: Completed.

Author normalization now provides:

- a provider-independent `AuthorNormalizer` in
  `app/normalization/author.py`, accepting and returning one canonical `Author`
- normalization limited to collapsing and trimming whitespace in
  `display_name`, `given_name`, and `family_name`
- preservation of capitalization, diacritics, punctuation, initials, name
  order, institutional names, and absent optional name parts
- a new deeply copied `Author` result without mutation or shared mutable
  identifier and affiliation lists
- no parsing or reconstruction of `display_name`, identity resolution,
  matching, disambiguation, deduplication, or author merging
- unchanged provider and import-file mapping semantics; those layers remain
  responsible for source schemas and BibTeX/RIS name-format parsing
- provider-independent ORCID normalization in `app/normalization/orcid.py`,
  with the provider mapping utility retained only as a compatibility re-export
- unchanged ORCID behavior without checksum validation, existence checks, or
  identity resolution
- deferred systematic application of author normalization to publications
  until Phase 4.5

Phase 4.5 — Publication normalization pipeline: Completed.

Publication normalization now provides:

- one provider-independent `PublicationNormalizer` in
  `app/normalization/publication.py`, accepting and returning one complete
  canonical `Publication`
- composition of the existing title, author, DOI, and ORCID normalizers
  without introducing additional normalization algorithms
- preservation of the original title while populating `title_normalized`
- normalization of every author, publication DOI value, and author ORCID
  value while preserving all other identifier types unchanged
- a new deeply copied publication without input mutation or shared mutable
  collections
- preservation of record identity, schema version, timestamps, provenance,
  collection order, and all fields outside the explicit normalization scope
- no filtering or deduplication; repeated identifiers remain repeated after
  normalization, with Phase 5 retaining responsibility for deduplication
- execution as a separate post-mapping stage in Search Engine and import
  providers, before downstream result provenance and merge
- unchanged mapper and `ResultMerger` semantics

Phase 4 — Normalization: Completed.

---

## Phase 5 — Deduplication

Phase 5.1 — Deduplication Domain Model: Completed.

The deduplication domain model now provides:

- infrastructure-independent potential duplicate groups containing at least
  two distinct publication identifiers
- explicit pending, confirmed, rejected, and merged group statuses
- immutable confirm, reject, and mark-merged decision records with optional
  reviewer attribution and rationale
- controlled pending → confirmed, pending → rejected, and confirmed → merged
  transitions
- immutable chronological decision history and timezone-aware audit timestamps
- terminal rejected and merged states
- no duplicate detection, similarity scoring, merge policy, repository, API,
  database, or GUI behavior

Cross-group publication membership remains a later repository or domain-service
invariant and is not falsely enforced by an individual duplicate group.

Phase 5.2 — Merge Policy: Completed.

The publication merge policy now provides:

- deterministic and commutative merging of two publications already known to
  represent the same work
- stable technical identity and collection ordering independent of argument
  order
- explicit metadata selection rules for scalar values, ordered authors,
  bibliographic dates, and venues
- complete, deduplicated identifier and provenance collections
- explicit conflicts for incompatible DOI, PMID, OpenAlex, and open-access
  values
- a new validated `Publication` without mutating either input
- no candidate detection, grouping, similarity scoring, repository, API,
  database, or GUI behavior

The existing DOI-only `ResultMerger` remains unchanged and continues to retain
the first search result for compatibility. It does not invoke the new merge
policy in this increment.

Phase 5.3 — Duplicate Groups: Completed.

The duplicate group builder now provides:

- deterministic candidate groups based only on shared DOI, PMID, and OpenAlex
  identifiers
- DOI normalization and exact PMID/OpenAlex value comparison
- transitive connected groups with stable publication ordering
- deterministic group identifiers and explicit group creation timestamps
- pending groups without decisions or automatic merge
- omission of unmatched publications and groups with fewer than two distinct
  publication IDs
- no title matching, fuzzy matching, scoring, Search Engine integration,
  repository, API, database, or GUI behavior

Phase 5.4 — Search Engine Integration: Completed.

`DuplicateGroupBuilder` is now invoked once by Search Engine on the complete
ordered `normalized_publications` collection before records are removed by
`ResultMerger`. `SearchExecution` exposes that complete collection, candidate
`duplicate_groups`, and the existing `merged_publications`.

Every publication referenced by a duplicate group therefore remains available
in `normalized_publications`. ResultMerger still produces
`merged_publications` with its conservative DOI-only, first-record-wins
behavior and unchanged ordering.

No group is confirmed or rejected automatically, and no publication metadata is
merged. `PublicationMergePolicy` remains available only as an explicit,
separate operation and is not invoked by Search Engine.

Phase 5.5 — Tests: Completed.

The Phase 5 regression suite now verifies:

- duplicate-group invariants, legal and illegal transitions, append-only
  decision history, chronology, timestamps, and immutability
- publication merge determinism, commutativity, idempotence, conflicts,
  collection stability, and provenance preservation
- duplicate-builder strong-identifier behavior, transitive and disjoint
  groups, repeated record IDs, weak-metadata exclusions, stable UUID5 identity,
  and timestamp contracts
- unchanged ResultMerger DOI-only, first-record-wins behavior without automatic
  metadata merge
- SearchEngine and SearchExecution contracts for normalized publications,
  merged publications, candidate groups, provenance, empty results, and partial
  provider failures

No duplicate decision or publication merge is performed automatically.

Phase 5 — Deduplication: Completed.
Phase 6 — GUI Foundation and Duplicate Review: Completed.
Version 0.2.5 — Data Integrity Cleanup: Completed.
Version 0.2.6 — Provider-Specific Query Rendering: Completed.
Version 0.2.7 — Screening Criteria Domain Model: Completed.
Version 0.2.8 — Screening Criteria Persistence and API: Completed.

The next planned implementation increment is Phase 7.6 — Full-Text Screening (Phase 7 — Screening remains in progress).

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

Phase 11 — Integrated GUI MVP.

---

# Important notes

Infrastructure is considered finished.

Future work focuses on scientific functionality, not framework development.

Every larger change should be implemented as a reviewable PR-sized increment.

The roadmap is the authoritative sequence of work. Additional engineering tasks should be included within existing roadmap items unless a deliberate roadmap change is approved.
