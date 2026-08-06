# SLR Platform Roadmap

## Vision

SLR Platform is an open-source application supporting the complete lifecycle of a Systematic Literature Review (SLR).

The long-term goal is to provide a transparent, reproducible and AI-assisted workflow that follows evidence-based research principles while remaining provider-independent.

The project is developed incrementally, with every phase ending in a usable and stable application.

---

# Product Roadmap

## Phase 1 — Domain Model ✅

Core domain objects.

- Publication
- Author
- Venue
- Identifiers
- Provenance
- Search Query
- Search Results

---

## Phase 2 — Search Providers 🚧

Search integration.

Current providers:

- OpenAlex
- Crossref
- Semantic Scholar

Future:

- Europe PMC
- OpenAIRE
- Lens
- CORE

---

## Phase 3 — Import Providers 🚧

Import bibliographic files.

Supported:

- BibTeX
- RIS

Future:

- EndNote XML
- CSL JSON

---

## Phase 4 — Normalization ✅

Provider-independent normalization layer.

Completed:

- DOI
- Title
- Author
- ORCID
- Publication normalization pipeline

---

## Phase 5 — Deduplication ✅

Deterministic publication deduplication.

Goals:

- duplicate detection
- merge strategy
- provenance preservation

---

## Phase 6 — GUI Foundation and Duplicate Review ✅

Establish the reusable graphical application foundation and provide the first functional review workflow for duplicate publications.

Increments:

- **6.1 GUI Foundation** ✅ — Application shell, routing, Information Architecture, SLR process funnel, Concept Group strategy builder, and state placeholders.
- **6.2 Application Versioning** ✅ — Application-wide version single source of truth in root `VERSION` file, build-time Vite injection, GUI release identity, and About dialog.
- **6.3 Duplicate Review Read API** ✅ — Backend DTO contracts, read-only REST endpoint `GET /projects/{id}/duplicate-groups`, frontend API adapter, loading/empty/error states, and hybrid data mode.
- **6.4 Duplicate Review Decisions** ✅ — In-memory decision repository (`InMemoryDuplicateReviewDecisionRepository`) with `(project_id, group_id)` composite key isolation, REST endpoints `POST` & `GET` for `APPROVE` and `REJECT` decisions, and interactive decision controls in GUI.
- **6.5 Duplicate Comparison and Review UI** ✅ — Detailed side-by-side publication comparison view, deterministic field state matching, provenance tracing, optional decision rationale with length validation, and accessible controls.
- **6.6 Integration and Contract Tests** ✅ — Backend contract tests for OpenAPI/DTO schemas, full duplicate review workflow integration, frontend integration & regression suite, determinism checks, and documentation reconciliation.

This phase does not represent the full GUI MVP. Its purpose is to establish the interface foundation and deliver the complete module supporting deduplication review.

---

## Phase 6.7 — Functional Workflow for Modules 1–4 🚧

Before extending the SLR workflow with additional product phases, the existing
user-facing workflow must become fully functional and manually verifiable.

- **6.7.1 Functional Search Strategy** ✅ — Editable years, selectable supported
  providers, fully editable concept groups, validation, Execute and Repeat
  actions, runtime application state, backend validation, and browser acceptance.
- **6.7.2a Search Results Workflow** ✅ — Controlled deterministic backend
  results, response contract, result presentation, record selection, project
  isolation, and loading/empty/error states without live provider calls or
  persistent import.
- **6.7.2b Live Search Providers & Import** ✅ — Live OpenAlex and Crossref
  execution with existing retry/rate limiting, common publication mapping,
  partial provider errors, deterministic source-record identifiers, provider
  attribution, and idempotent import of selected records into the project
  collection.

Phase 6.7.2a established the frontend/API workflow in v0.1.6. Phase 6.7.2b
connected the workflow to live providers and the project Working Collection in
v0.1.7 (historically using a process-local demonstrator collection). As of v0.2.0,
the Working Collection is fully durable in SQLite (`SqliteProjectPublicationRepository`)
and survives backend restarts.

---

## Phase 6.8 — End-to-End Literature Search Workflow 🚧

The product priority from v0.1.8 is a complete literature-search workflow that
can be performed without leaving the GUI. Work on further mock-driven screens
is deferred until Search Strategy and Sources Ingestion use durable backend
capabilities.

- **6.8.1 Search Strategy Backend** ✅ — durable strategy storage, REST GET/PUT,
  provider-independent Search Strategy and Search Query models, validation, and
  provider selection.
- **6.8.2 Query Rendering** ⬜ — OpenAlex, Crossref, and Semantic Scholar query
  renderers.
- **6.8.3 Search Orchestrator** ⬜ — multi-provider execution, result
  aggregation, partial failures, provenance, and SearchRun.
- **6.8.4 Search Execution API** ⬜ — execute search, search status, and search
  results.
- **6.8.5 Persistence** ⬜ — SearchRun, publications, provenance, and search
  history.
- **6.8.6 Search Strategy GUI Integration — Completed (functional)** ✅ — Search Strategy reads and
  writes the real backend resource, no longer uses project mocks as strategy
  data, supports the complete authored form and generic Boolean preview,
  executes live searches, presents results on the same page, and provides the
  result import workflow. **Szukaj** does not navigate to Sources & Imports.
- **6.8.7 Sources Ingestion GUI Integration** ⬜ — start searches, show
  progress, record counts, and provider errors.
- **6.8.8 GUI Import Integration** ⬜ — RIS and BibTeX through the existing
  import providers.
- **6.8.9 Publication Intake Summary** ⬜ — summarize every intake source and
  provide the transition to later workflow stages.

Phase 6.8.1 and the functional Search Strategy workflow are available. Further
work before Phase 2 focuses on result completeness and presentation quality.

### Version 0.2.5 — Data Integrity Cleanup ✅

- **Task 1 — Integrity Audit Service** ✅ — Deterministic data integrity audit engine (`ProjectIntegrityAuditService`) verifying provenance completeness, record_id uniqueness, import history record count alignment, and orphaned review decisions.
- **Task 2 — Transaction Boundary** ✅ — Explicit `SqliteTransactionManager` enforcing atomic multi-repository write operations during search/import ingestion.
- **Task 3 — Backend Read Models** ✅ — Isolated `SourcesSummaryService` read model decorrelating GUI intake summaries from raw persistence models.
- **Task 4 — SQLite Constraints Review** ✅ — Complete DDL review of foreign keys, CHECK constraints, and indexes across all 6 pipeline tables.
- **Task 5 — Repository Contracts** ✅ — Standardized `Protocol` definitions decorated with `@runtime_checkable`, vendor-agnostic method signatures, and a dedicated contract test suite.
- **Task 6 — Test Fixtures** ✅ — Deterministic domain object factories (`factories.py`) and isolated standard project fixtures (`empty_project`, `project_100`, `project_duplicates`, `project_normalized`).
- **Task 7 — CLI Integrity Check** ✅ — Thin CLI tool (`python -m app.tools.integrity PROJECT_ID`) supporting terminal text and JSON output formats with standard process exit codes (`0` for OK/WARNING, `1` for ERROR, `2` for argument errors).
- **Next Phase:** Phase 7 — Screening (not yet started).

### Version 0.2.4 — Data Consistency and Executable Deduplication ✅

- Working Collection, Sources & Imports and Normalization are aligned to the same project publication set.
- Historical `lean_energy` data is repaired to 535 OpenAlex publications, with the synthetic Crossref test record removed and a clearly labelled 391-record OpenAlex history backfill.
- Deduplication can be run manually through the existing duplicate-groups endpoint.
- The UI reports the last deduplication execution separately from the candidate-group review summary.
- Candidate review distinguishes not-run, zero-group, pending and fully reviewed states.
- APPROVE and REJECT decisions remain durable; physical publication merging is not implemented.
- Screening remains unavailable and is not implemented by this increment.

### Version 0.2.3 — Functional Project Dashboard and Sources Aggregation ✅

- Project Dashboard uses real workflow data for stages 1–4, including loading, empty, partial-data and partial-failure states.
- Search Strategy has a functional empty state and can persist the first strategy.
- OpenAlex is the verified provider in the current search and import workflow.
- Crossref remains selectable in the UI but is not marked as fully verified end to end; Semantic Scholar remains unavailable.
- Sources & Imports presents accumulated successful record counts per available provider and retains the individual import history below the aggregate.
- Workflow stages 5–8 remain unavailable.
- Normalization and deduplication behavior is unchanged; the Dashboard reads their existing statuses only.

This increment does not add new provider integrations, background jobs, screening, quality assessment, data extraction, exports, normalization rules, or deduplication behavior.

### Version 0.1.9 increment

The first project-scoped bibliographic upload is implemented: the Sources
upload control sends one `.ris` or `.bib` file to
`POST /projects/{project_id}/imports`, reuses the existing parsers, and stores
the parsed publications through the existing repository. This initial
upload slice now includes durable project-scoped import history returned
newest-first by `GET /projects/{project_id}/imports`. Selected OpenAlex result
imports also create provider history records, which are shown on Sources
alongside file imports. GUI Import Integration (6.8.8) remains open for
provider execution status and the broader Sources ingestion workflow.

Background jobs, provider status APIs, full import history and full Sources
Ingestion remain unimplemented.

Normalization integration is now available as a synchronous, project-scoped
endpoint and GUI workflow. The latest execution summary and audit trail are
durable in SQLite; full multi-run history, ISSN validation, full provenance and
background execution remain future work.

### Version 0.2.0 increment

The 0.2.0 increment completely replaces the runtime demonstration publication
repository (`DemoProjectPublicationRepository`) with `SqliteProjectPublicationRepository`,
storing all project publications durably in SQLite (`project_publications` table).

The single, unified `ProjectPublicationRepository` persistence boundary connects:
- import of selected live search results,
- import of RIS and BibTeX files (`POST /projects/{project_id}/imports`),
- normalization execution reads and canonical record updates (`POST/GET /projects/{project_id}/normalization`),
- duplicate candidate generation and preview service (`GET /projects/{project_id}/duplicate-groups`).

The existing `PublicationNormalizer` is backed by durable latest-run
storage in SQLite (`SqliteNormalizationExecutionRepository`). Summary fields and
audit trail remain available after backend restart.

Deduplication, screening, background jobs and full provenance remain open.

### Version 0.2.1 increment — Durable Duplicate Review Integration

The 0.2.1 increment connects the backend deduplication review decisions and frontend GUI with durable SQLite storage (`SqliteDuplicateReviewDecisionRepository` and migration `0006_duplicate_review_decisions.sql`).

Key outcomes:
- `group_id` generation is verified deterministic across input reordering, SQLite re-reads, unrelated publication additions, and normalization executions.
- Human review decisions (`APPROVE`, `REJECT`) and optional rationale persist across application restarts and page reloads.
- `GET /projects/{project_id}/duplicate-groups` returns the current decision status and rationale for every group, eliminating N+1 decision requests per group card.
- `DeduplicationPage` maintains a single state source of truth and recalculates summary metrics (Total, Pending, Approve, Reject) dynamically from backend data.
- GUI clearly informs users that decisions are stored in SQLite and physical publication merging remains deferred to a subsequent increment.

### Polish before Phase 2

- analyze the OpenAlex result count
- improve Search Results UX
- expose backend `rendered_query`
- display executed-search information
- citations
- journal
- Open Access
- PDF
- sorting
- improved import panel

---

## Phase 7 — Screening

Support systematic review screening through a backend workflow and a dedicated user interface.

Features:

- inclusion and exclusion decisions
- screening criteria
- screening rationale
- title and abstract screening
- full-text screening
- screening history
- conflict detection
- multiple reviewers
- screening queue and progress view
- screening decision interface

---

## Phase 8 — Quality Assessment

Support methodological quality assessment of included studies.

Features:

- configurable quality criteria
- assessment forms
- scoring or rating schemes
- reviewer attribution
- assessment rationale
- assessment history
- reviewer agreement and disagreement visibility
- quality assessment interface
- assessment progress view

---

## Phase 9 — Data Extraction

Support structured extraction of research data from included studies.

Features:

- configurable extraction forms
- structured extraction fields
- extracted-value provenance
- reviewer attribution
- extraction history
- validation of extracted data
- extraction workspace
- tabular and form-based extraction views
- exportable structured datasets

---

## Phase 10 — Evidence Synthesis

Support organization, analysis and synthesis of extracted evidence.

Features:

- qualitative synthesis support
- thematic grouping
- evidence tables
- bibliometric analysis support
- research-gap identification
- synthesis traceability
- synthesis workspace
- comparison and aggregation views

---

## Phase 11 — Integrated GUI MVP

Integrate the previously developed graphical modules into the first complete end-to-end application.

Features:

- unified workflow navigation
- integrated search and import views
- integrated deduplication workflow
- integrated screening workflow
- integrated quality assessment workflow
- integrated data extraction workflow
- integrated evidence synthesis workflow
- common state management
- consistent validation and error handling
- basic settings
- complete end-to-end user journey

The GUI MVP is not built from scratch. It integrates, unifies and completes the graphical modules developed in earlier phases.

---

## Phase 12 — Reporting & Export

Generate research outputs.

Examples:

- PRISMA flow
- CSV
- BibTeX
- RIS
- Excel
- JSON

---

## Phase 13 — Project Management

Research project management.

Examples:

- saved searches
- protocols
- search history
- project metadata
- audit trail

---

## Phase 14 — User Experience

Application refinement.

Examples:

- UX
- accessibility
- performance
- responsive layouts
- keyboard shortcuts

---

## Phase 15 — AI Assistance

AI features built on top of a stable platform.

Potential capabilities:

- article summarization
- relevance suggestions
- duplicate suggestions
- keyword extraction
- quality assessment support
- evidence synthesis support

AI is intentionally scheduled after the core platform to ensure transparency, reproducibility and provider independence.

---

# Release Strategy

The project follows incremental releases.

Typical flow:

Feature
→ Tests
→ Documentation
→ Stable Release

Every completed phase results in a usable application.
