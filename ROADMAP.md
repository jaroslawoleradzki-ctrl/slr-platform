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

## Phase 6.7 — Functional Workflow for Modules 1–4 ✅

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
and survives backend restarts. Phase 6.7 is completed.

---

## Phase 6.8 — End-to-End Literature Search Workflow 🟨

The product priority from v0.1.8 is a complete literature-search workflow that
can be performed without leaving the GUI. Work on further mock-driven screens
is deferred until Search Strategy and Sources Ingestion use durable backend
capabilities.

- **6.8.1 Search Strategy Backend** ✅ — Durable strategy storage in SQLite (`0001_search_strategies.sql`), REST GET/PUT endpoints (`/projects/{project_id}/search-strategy`), provider-independent `SearchStrategy` and `SearchQuery` domain models, validation, and provider selection.
- **6.8.2 Provider-Specific Query Rendering** ✅ — Provider-specific translation of canonical `SearchQuery` expressions into physical provider queries (`OpenAlexQueryRenderer`, `CrossrefQueryRenderer`). `SearchEngine` executes exact provider queries, stores physical queries in `SearchRun` / provenance / raw response archive, and exposes `provider_queries` in REST API with lossy/lossless tracking.
- **6.8.3 Search Orchestrator** ✅ — Multi-provider execution via `SearchEngine`, separate `SearchRun` per provider, provider error isolation / partial failure handling, normalized results, result aggregation / merging (`ResultMerger`), search provenance, execution provenance, and candidate duplicate group generation (`DuplicateGroupBuilder`).
- **6.8.4 Search Execution API** 🟨 — `POST /projects/{project_id}/search-strategy/executions` executes search strategies live, returning `rendered_query`, `provider_queries`, selected providers, execution timestamp, total/returned record counts, pagination metadata (`next_cursor`, `has_more`), results list, and provider error diagnostics. Lacks a durable execution resource for subsequent GET retrieval of run status, saved execution results, or historical runs by ID.
- **6.8.5 Search Execution Persistence** 🟨 — Working Collection publications, Search Strategy, import history, normalization state, and duplicate review decisions are durable in SQLite. Full search execution history is not durable: `SearchRun` database records, complete execution history, and durable raw provider response archiving (`live_search.py` relies on transient `_InMemoryRawResponseArchive`) remain partial.
- **6.8.6 Search Strategy GUI Integration** ✅ — Search Strategy UI reads and writes the real backend resource, supports the authored form and generic Boolean preview, executes live searches, presents results and provider errors on the same page, and provides the result import workflow. **Szukaj** does not navigate to Sources & Imports.
- **6.8.7 Sources Search Execution GUI** ↪ — **Superseded by current Search Strategy execution workflow**. Search Strategy page executes searches and presents results/errors directly. Sources & Imports presents durable intake state, import history, source summaries, Working Collection summary, and bibliographic file uploads.
- **6.8.8 GUI Import Integration** ✅ — Upload of `.ris` and `.bib` files via GUI control to `POST /projects/{project_id}/imports`, reusing existing RIS/BibTeX parsers and normalizers, durable publication import into Working Collection, durable import history, and Sources Summary UI updates.
- **6.8.9 Publication Intake Summary** ✅ — `SourcesSummaryService` backend read model exposed via `GET /projects/{project_id}/sources-summary`, providing Working Collection total, source summaries (successful/warning/failed import counts, records added, last import status), and import history consumed by frontend.

### Technical Debt & Prerequisites for Executable Screening

A comprehensive reconciliation of Phase 6.8 identifies two technical prerequisites that must be addressed before Phase 7.5 (Title & Abstract Screening) can enter executable implementation:

1. **Live Search Import Metadata Loss**: The canonical `Publication` domain model supports rich metadata (`abstract`, `venue`, `publisher`, `document_type`, `language`, `keywords`, `urls`, `open_access`, `provenance`). While search providers (e.g. OpenAlex) fetch abstract and metadata, `SearchResultRecordResponse` DTO exposes a trimmed subset (`id`, `title`, `authors`, `year`, `provider`, `source_id`, `doi`). `ProjectImportService` constructs imported publications from this DTO, causing abstract and other screening-relevant metadata to be lost upon import. Preserving complete metadata (especially `abstract`) during search result import is a mandatory blocker for executable Phase 7.5.
2. **Deduplicated Screening Input Set**: Current deduplication records human `APPROVE` / `REJECT` decisions for candidate duplicate groups, but physical publication merging is deferred. Consequently, approved duplicate publications still exist as separate records in the Working Collection. Before Phase 7.5, an explicit screening input set pipeline must be established (`Working Collection` → `Duplicate Decisions` → `Canonical / Deduplicated Screening Set` → `Screening`) so a single publication is not screened multiple times.

**Phase 7 Implementation Scope**:
- **Phases 7.1–7.4** (Screening Criteria Domain Model, Persistence & API, Configuration GUI, Screening Decision Domain & Persistence) CAN proceed independently of these open Phase 6.8 technical debts.
- **Phase 7.5 — Title & Abstract Screening** MUST NOT enter executable implementation until Metadata Preservation (1) and Deduplicated Screening Input Set (2) are resolved.
- **Provider-Specific Query Rendering (6.8.2)** is COMPLETED in v0.2.6.
- **Search Execution Persistence (6.8.5)** is important for reproducibility, but does not block Phase 7.1–7.4 domain model development.

### Version 0.3.0 — Screening Decision Domain and Persistence ✅

- **Phase 7.4 Screening Decision Domain and Persistence** ✅ — `ScreeningDecision` domain model capturing strictly required `project_id`, `publication_id`, screening stage (`TITLE_ABSTRACT` or `FULL_TEXT`), outcome decision (`INCLUDE`, `EXCLUDE`, `UNCERTAIN`), reviewer attribution, rationale, timezone-aware UTC timestamps, and criterion-level assessments (`CriterionAssessment`) containing an immutable server-side snapshot of criterion metadata (`criterion_id`, `criterion_name`, `criterion_type`, `criterion_stage`, `criterion_is_required`, `assessment_value`, `notes`). Authoritative snapshot construction, publication and criteria project ownership validation, stage compatibility validation, inactive criterion rejection, required criteria completeness validation, duplicate assessment protection, and 100% AI-free design. Synchronous SQLite persistence (`SqliteScreeningDecisionRepository`, migration `0008_screening_decisions.sql` with composite primary key `(decision_id, criterion_id)`), append-only history trail, latest decision resolution, application service (`ScreeningDecisionService`), minimal project-scoped REST API endpoints (`/projects/{project_id}/screening/decisions`), and 22 backend test cases. No GUI or screening queue.

### Version 0.2.9 — Screening Configuration GUI ✅

- **Phase 7.3 Screening Configuration GUI** ✅ — Project-scoped graphical interface for screening criteria configuration based on the real Phase 7.2 REST API. Listing criteria, Create & Edit modal forms with client-side validation (empty name, negative display order), stage targeting (`TITLE_ABSTRACT`, `FULL_TEXT`, `BOTH`), type selection (`INCLUSION` / `EXCLUSION`), required/optional toggles, active/inactive indicators, display ordering, soft deactivation (`PATCH /deactivate`), reactivation support (`PUT`), and backend persistence. Zero hardcoded criteria. 22 frontend unit and integration tests.

### Version 0.2.8 — Screening Criteria Persistence and API ✅

- **Phase 7.2 Screening Criteria Persistence and API** ✅ — Durable SQLite storage (`screening_criteria` table in `migrations/0007_screening_criteria.sql`), `ScreeningCriterionRepository` protocol contract, `SqliteScreeningCriterionRepository` adapter, project-scoped REST API endpoints (`/projects/{project_id}/screening/criteria`), payload DTOs, deactivation lifecycle (`PATCH /deactivate`), deterministic display ordering, strict project isolation, and 34 unit tests. No GUI.

### Version 0.2.7 — Screening Criteria Domain Model ✅

- **Phase 7.1 Screening Criteria Domain Model** ✅ — Infrastructure-independent `ScreeningCriterion` domain model (`criterion_id: UUID`, `project_id: str`, `name`, `description`, `criterion_type: ScreeningCriterionType` (`INCLUSION`/`EXCLUSION`), `screening_stage: ScreeningCriterionStage` (`TITLE_ABSTRACT`/`FULL_TEXT`/`BOTH`), `display_order: int`, `is_active: bool`, `is_required: bool`), domain validation rules, deterministic JSON serialization, and unit test suite. No persistence, API, or GUI.

### Version 0.2.6 — Provider-Specific Query Rendering ✅

- **QueryRenderer Contract** ✅ — Clean, decoupled protocol (`QueryRenderer`) and value object (`RenderedQuery`) supporting physical query strings, lossy/lossless flags (`is_lossless`), explicit limitation warnings (`warnings`), and diagnostic metadata (`metadata`).
- **OpenAlexQueryRenderer** ✅ — Translates canonical `SearchQuery` into OpenAlex `search` string syntax with exact phrase quotes `"..."`, uppercase Boolean operators (`AND`, `OR`, `NOT`), and nested grouping `()`.
- **CrossrefQueryRenderer** ✅ — Translates canonical `SearchQuery` into Crossref free-text keyword string syntax with exact phrase quotes `"..."`, space-separated terms, explicit lossy tracking (`is_lossless=False`), and audit warnings for unsupported `NOT` / `OR` operators.
- **SearchEngine Integration** ✅ — Provider-specific query rendering integrated into `SearchEngine.execute()`, ensuring `SearchRun.rendered_query`, `ProvenanceEntry.rendered_query`, and raw response archive entries store the exact physical query executed per provider.
- **API & GUI Contract** ✅ — REST API `POST /projects/{project_id}/search-strategy/executions` exposes `provider_queries`, and frontend presents physical provider queries alongside canonical preview.

### Version 0.2.5 — Data Integrity Cleanup ✅

- **Task 1 — Integrity Audit Service** ✅ — Deterministic data integrity audit engine (`ProjectIntegrityAuditService`) verifying provenance completeness, record_id uniqueness, import history record count alignment, and orphaned review decisions.
- **Task 2 — Transaction Boundary** ✅ — Explicit `SqliteTransactionManager` enforcing atomic multi-repository write operations during search/import ingestion.
- **Task 3 — Backend Read Models** ✅ — Isolated `SourcesSummaryService` read model decorrelating GUI intake summaries from raw persistence models.
- **Task 4 — SQLite Constraints Review** ✅ — Complete DDL review of foreign keys, CHECK constraints, and indexes across all 6 pipeline tables (ARCHITECTURE COMPLETED — IMPLEMENTATION DEFERRED).
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

## Phase 7 — Screening 🟨

Support systematic review screening through a backend workflow and a dedicated user interface.

### Key Architectural Principles

- **Universal Application**: SLR Platform is a domain-agnostic tool. Screening criteria are never hardcoded for any specific literature review (e.g. Lean Management or energy efficiency).
- **Project-Scoped Criteria**: Every research project defines its own custom, user-configurable screening criteria.
- **Workflow Position**:
  Working Collection → Normalization → Deduplication → **Title & Abstract Screening** → **Full-Text Screening** → Quality Assessment → Data Extraction
- **Historical Interpretation Stability**: Modifying screening criteria must preserve full interpretability of historical decisions by recording criteria snapshots or version references alongside decision audit records.
- **No Copyrighted PDF Storage Requirement**: Full-text screening architecture treats full-text availability and status (URL, DOI link, external access status) as technical publication/workflow metadata rather than a built-in qualification criterion. A project's configurable `ScreeningCriterion` defines whether lack of full text leads to exclusion, without requiring local storage of copyrighted PDF documents.
- **Reviewer Model Flexibility**: Single-reviewer mode is fully supported as the operational default, with multi-reviewer agreement and conflict resolution built as an optional extension layer.
- **PRISMA Readiness**: Screening decisions and exclusion rationale aggregations natively record all metrics required for subsequent PRISMA flow diagram generation.

### Increments

- **7.1 — Screening Criteria Domain Model** ✅ — Infrastructure-independent `ScreeningCriterion` domain model (`criterion_id: UUID`, `project_id: str`, `name`, `description`, `criterion_type: ScreeningCriterionType` (`INCLUSION`/`EXCLUSION`), `screening_stage: ScreeningCriterionStage` (`TITLE_ABSTRACT`/`FULL_TEXT`/`BOTH`), `display_order: int`, `is_active: bool`, `is_required: bool`), domain validation rules, deterministic JSON serialization, and unit test suite. No persistence, API, or GUI.
- **7.2 — Screening Criteria Persistence and API** ✅ — Durable SQLite persistence layer (`SqliteScreeningCriterionRepository`), database migration (`0007_screening_criteria.sql`), abstract repository contract (`ScreeningCriterionRepository` decorated with `@runtime_checkable`), full CRUD and lifecycle management (`PATCH /deactivate`), strict project isolation, order preservation (`ORDER BY display_order ASC, criterion_id ASC`), REST API endpoints (`/projects/{project_id}/screening/criteria`), payload validation DTOs, and test suites. No GUI.
- **7.3 — Screening Configuration GUI** ✅ — Graphical management interface for screening criteria based on real Phase 7.2 API: listing criteria, create/edit/deactivate actions, inclusion vs. exclusion selection, stage targeting (`TITLE_ABSTRACT` / `FULL_TEXT` / `BOTH`), required/optional toggles, reordering controls, description/instruction fields, backend API persistence integration, and full loading, empty, error, and validation state handling. Zero hardcoded criteria. 22 frontend tests.
- **7.4 — Screening Decision Domain and Persistence** ✅ — `ScreeningDecision` domain model capturing project ID, publication ID, screening stage, outcome decision (`INCLUDE` / `EXCLUDE` / `UNCERTAIN`), criterion-level assessments (`CriterionAssessment`) with authoritative server-side snapshot of criterion metadata, decision rationale, reviewer attribution, timestamps, append-only history trail, and latest decision resolution. Synchronous SQLite persistence (`SqliteScreeningDecisionRepository`, migration `0008_screening_decisions.sql`), application service (`ScreeningDecisionService`), REST API endpoints (`/projects/{project_id}/screening/decisions`), and test suite. 100% AI-free. No GUI or screening queue.
- **7.5A — Screening Input Prerequisites** ✅ — Preserve authoritative canonical live-search metadata and provenance during import, and derive a project-scoped canonical/deduplicated screening input set. APPROVE groups collapse through the existing merge policy, REJECT records remain separate, and unresolved groups block readiness. No queue, GUI, or screening decisions.
- **7.5B — Title & Abstract Screening Backend Workflow** ✅ — Deterministic project-scoped records read model, typed readiness reasons, reviewer-specific status/progress derived from batch-loaded latest decisions, active `TITLE_ABSTRACT`/`BOTH` criteria, canonical publication eligibility, stable pagination/filtering, and append-only decision writes delegated to `ScreeningDecisionService`. No GUI or queue persistence.
- **7.5C — Title & Abstract Screening GUI** ➡️ **Next** — Title, abstract and metadata presentation, criteria and criterion-level assessment, INCLUDE/EXCLUDE/UNCERTAIN decisions, rationale, previous/next, save/resume, progress, and loading/error/empty states.
- **7.6 — Full-Text Screening** ⬜ — Queue management for publications eligible after Title & Abstract Screening, evaluation against `FULL_TEXT` and `BOTH` criteria (with technical full-text availability/status presented as workflow metadata, and project-scoped criteria determining whether unretrievable full text leads to exclusion), explicit selection of exclusion reasons, decision recording (`INCLUDE` / `EXCLUDE` / `UNCERTAIN`) with rationale, history view, save & resume, progress metrics, and GUI & backend integration. No requirement for local storage of copyrighted PDF files.
- **7.7 — Screening Audit Trail and Progress** ⬜ — Complete decision audit trail capturing reviewer, timestamps, exact criteria version used, decision changes, stage-specific progress metrics (included, excluded, uncertain counts), exclusion-reason aggregations, overall project screening summary, and structured data extraction necessary for subsequent PRISMA flow charts. Changes to criteria do not invalidate or obscure historical decisions.
- **7.8 — Multi-Reviewer Screening and Conflict Detection** ⬜ — Independent multi-reviewer decision recording for the same publication and stage, conflict detection algorithm identifying reviewer disagreements, dedicated conflict resolution queue, resolution workflow with reviewer agreement metrics, resolution rationale recording, and audit trail. Single-reviewer workflow remains fully operational.
- **7.9 — Screening Integration and Release** ⬜ — Integration into Project Dashboard, workflow stage status transitions (Deduplication → Screening and Screening → Quality Assessment), handling empty/loading/error states, backend integration test suite, frontend integration test suite, end-to-end verification, documentation reconciliation, and release verification.

### Definition of Done for Phase 7

Phase 7 is complete when a user can:
1. Create arbitrary, custom screening criteria for a project.
2. Assign criteria to Title & Abstract, Full-Text, or both screening stages.
3. Perform Title & Abstract Screening on post-deduplication records.
4. Perform Full-Text Screening on eligible studies.
5. Record `INCLUDE`, `EXCLUDE`, or `UNCERTAIN` decisions with explicit rationale.
6. Resume screening seamlessly after application restarts.
7. Inspect the complete historical audit trail of screening decisions.
8. Monitor real-time progress for both screening stages.
9. Work efficiently in single-reviewer mode.
10. Optionally utilize multi-reviewer screening and conflict resolution workflows.
11. Retrieve aggregated decision and exclusion-reason data ready for PRISMA reporting.

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

Status: ✅ Integrated on `development` (persistent project resource, list/create/open/edit,
archive/restore, active-project persistence and atomic hard delete).

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
