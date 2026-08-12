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

### Screening Prerequisites Resolved in v0.3.1

Phase 7.5 now has a durable, auditable input path. Live search results are stored
as authoritative `SearchResultSnapshot` records and import preserves the canonical
publication metadata and provenance already obtained from providers. The
project-scoped `ScreeningInputService` derives a non-destructive canonical input
set: approved duplicate groups collapse through `PublicationMergePolicy`, rejected
groups remain separate, and pending groups or merge conflicts block readiness.

Full durable `SearchRun` history remains a separate Phase 6.8.5 concern; it does
not block Title & Abstract Screening.

### Version 0.3.8 — Screening Manual Acceptance UX Fixes 🟨

- Dark-theme select/dropdown controls across Screening with readable text,
  borders, focus/hover/disabled states, and consistent sizing.
- User-facing reviewer-team terminology replacing technical “roster” wording.
- Unified “Konflikty i rozstrzygnięcia” workflow for conflict analysis and
  adjudication, with backward-compatible routing from the former resolution
  path.
- **Manual Acceptance: PENDING AFTER PHASE 8 INTEGRATION ON DEVELOPMENT.**

### Version 0.3.9 — Quality Assessment Integration ✅

- **Quality Assessment subsystem integrated into development** — domain and
  persistence, project configuration, execution workflow, API, workspace,
  integration tests, and project-deletion lifecycle support.
- **Phase 9 Data Extraction is not part of this release and remains under active development.**

### Version 0.4.0 — Data Extraction Persistence ✅

- **Phase 9.2 — Persistence & Template Catalog** ✅ — Migration `0018`,
  immutable versioned template catalog, project-scoped extraction records,
  append-only revisions, batched hydration, and atomic project hard-delete
  integration. Phase 9.3 and later increments remain unintegrated.

### Version 0.4.1 — Data Extraction Configuration & Eligibility ✅

- **Phase 9.3 — Project Configuration & Eligibility** ✅ — Immutable template
  selection per project, configuration locking after extraction begins,
  Full-Text screening gates, and a fail-closed, reviewer-scoped read-only QA
  completion gate. QA responses are neither scored nor converted into
  exclusions. Phase 9.4 and later increments remain unintegrated.

### Version 0.3.7 — Screening Integration ✅

- **Phase 7.9 — Screening Integration and Release** ✅ — Stage eligibility
  adapter, multi-reviewer queue hydration, staleness revocation, unified
  workflow-status API, Dashboard and WorkflowStepper integration, and backend
  and frontend integration test suites.
- **Manual Acceptance: PENDING AFTER PHASE 8 INTEGRATION ON DEVELOPMENT.**

### Version 0.3.6 — Conflict Resolution and Adjudication ✅

- **Phase 7.8B — Conflict Resolution / Adjudication** ✅ — Explicit resolver
  workflow with required rationale and identity, append-only resolution
  history, deterministic decision-set concurrency, stale/current semantics,
  unified decision/resolution audit events, project-level outcome read model,
  reporting extensions, and conflict-resolution workspace.
- **Phase 7.9 was delivered in v0.3.7; manual acceptance remains pending after Phase 8 integration.**

### Version 0.3.5 — Multi-Reviewer Screening and Conflict Detection ✅

- **Phase 7.8A — Multi-Reviewer Screening and Conflict Detection** ✅ —
  Project-and-stage reviewer roster with active/inactive lifecycle, derived
  `INCOMPLETE` / `AGREEMENT` / `CONFLICT` state from latest reviewer-specific
  decisions, conflict queue, pending-reviewer visibility, agreement metrics,
  blind-aware display, and single-reviewer compatibility.
- **Phase 7.8B was delivered in v0.3.6.**

### Version 0.3.4 — Screening Audit Trail and Progress ✅

- **Phase 7.7 — Screening Audit Trail and Progress** ✅ — Unified,
  project-scoped decision audit history; reviewer-specific progress and
  pipeline transitions; Full-Text exclusion-reason aggregation; criterion
  snapshot schema v2; and paginated audit/report APIs with screening summary
  and history UI.
- **Phase 7.8A was delivered in v0.3.5.**

### Version 0.3.3 — Full-Text Screening and Dashboard/Search Polish ✅

- **Phase 7.6 — Full-Text Screening** ✅ — Reviewer-specific eligibility,
  derived queue, FULL_TEXT/BOTH criteria, availability metadata, structured
  exclusion reasons, append-only history, and executable Full-Text GUI.
- **Dashboard and Search Polish** ✅ — Corrected Search → Import contract,
  provider pagination with append semantics, local pagination of loaded results,
  and selection preserved across local pages.
- **Phase 7.7 was delivered in v0.3.4.**
- **Phase 7.8B was delivered in v0.3.6.**
- **Phase 7.9 was delivered in v0.3.7; manual acceptance remains pending after Phase 8 integration.**

### Version 0.3.1 — Project Management and Title & Abstract Screening ✅

- **Project Management** ✅ — Persistent project resource with list, create,
  open, edit, archive, restore and atomic hard delete. Active-project selection
  persists in the GUI; deletion also cleans project-scoped live-search snapshots.
- **Phase 7.5A — Screening Input Prerequisites** ✅ — Authoritative snapshots,
  metadata/provenance preservation, canonical deduplicated input and typed
  readiness.
- **Phase 7.5B — Title & Abstract Screening Backend Workflow** ✅ — reviewer-specific records, statuses and progress derived from latest append-only decisions; eligibility, filtering, pagination and decision API.
- **Phase 7.5C — Title & Abstract Screening GUI** ✅ — Reviewer identity, readiness states, progress, filtering, record navigation, criterion assessment, Save and Save & Next.
- **Phase 7.5D — Automatic Metadata-Based Screening Criteria** ✅ — Manual or deterministic metadata-rule evaluation, authoritative server-side assessments, and auditable rule/value/result snapshots.
- **Phase 7.6 — Full-Text Screening** ✅ — Reviewer-specific eligibility, derived queue, FULL_TEXT/BOTH criteria, availability metadata, structured exclusion reasons, append-only history, executable GUI.
- **Phase 7.7 — Screening Audit Trail and Progress** ✅ — Reviewer-scoped audit pages, decision timeline, previous decision comparison, and reporting repositories.
- **Phase 7.8A — Multi-Reviewer Screening + Conflict Detection** ✅ — Active reviewer rosters, agreement/disagreement outcome calculation, and conflict state tracking.
- **Phase 7.8B — Conflict Resolution / Adjudication** ✅ — Adjudicator override resolutions, decision set key validation, and resolution persistence (`0017_screening_conflict_resolutions.sql`).
- **Phase 7.9 — Screening Integration and Release** ✅ — Stage eligibility adapter (`ScreeningEligibilityAdapter`), multi-reviewer queue hydration, staleness revocation on vote change, unified GET /projects/{id}/workflow-status REST endpoint, Dashboard cards & Stepper integration, and integration test suites.

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
- **7.5C — Title & Abstract Screening GUI** ✅ — Project-scoped executable UI with explicit reviewer identity, typed readiness blocking states, progress, filtering, deterministic record navigation, criterion-level assessment, manual decisions, Save / Save & Next, and resume from persisted decisions.
- **7.5D — Automatic Metadata-Based Screening Criteria** ✅ — Configurable `MANUAL` and `METADATA_RULE` criteria; deterministic safe rules over publication metadata; server-authoritative automatic assessments with historical rule/value/result snapshots. The final screening outcome remains a human reviewer decision.
- **7.6 — Full-Text Screening** ✅ — Reviewer-specific derived eligibility from current canonical input plus latest `TITLE_ABSTRACT=INCLUDE`; `FULL_TEXT`/`BOTH` criteria, server-authoritative automatic assessments, full-text availability/reference workflow metadata, structured exclusion reasons linked to immutable criterion-assessment snapshots, append-only decisions, current progress/filtering and executable GUI. Loss of eligibility removes a record from the current queue without deleting history.
- **7.7 — Screening Audit Trail and Progress** ✅ — Unified, project-scoped read models for immutable Title & Abstract and Full-Text decision history; reviewer-specific stage progress and pipeline transitions; Full-Text exclusion-reason aggregation from criterion snapshots; legacy v1 and description-complete v2 criterion snapshots; paginated audit/report API and screening summary/history UI. No project-wide reviewer reconciliation.
- **7.8A — Multi-Reviewer Screening and Conflict Detection** ✅ — Project-and-stage reviewer roster with active/inactive lifecycle, derived `INCOMPLETE` / `AGREEMENT` / `CONFLICT` state from latest reviewer-specific decisions, conflict queue, pending-reviewer visibility, agreement metrics, and blind-aware display. Single-reviewer workflows remain compatible; no adjudication or resolved project outcome.
- **7.8B — Conflict Resolution / Adjudication** ✅ — Explicit resolver workflow, resolution rationale/history, stale-resolution detection, unified decision/resolution audit trail, and a project-level outcome read model. No automatic majority vote; no stage-transition integration.
- **7.9 — Screening Integration and Release** ✅ — Implemented and integrated;
  automated verification is complete. Manual Acceptance remains pending after
  Phase 8 integration on development.

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

## Phase 8 — Quality Assessment 🟨

Support methodological quality assessment of included studies.

Increments:
- **8.1 — Quality Assessment Domain Models & Persistence** ✅ — Infrastructure-independent Pydantic v2 models (`QualityAssessmentTool`, `QualityAssessmentTemplate`, `QualityAssessmentTemplateCriterion`, `QualityAssessment`, `QualityAssessmentResponse`), SQLite migration (`0013_quality_assessment.sql`), repository protocols (`QualityAssessmentCatalogRepository`, `QualityAssessmentRepository`), template content immutability contract, authoritative response criterion ownership validation, append-only history trail, and unit test suite.
- **8.2 — Quality Assessment Tool Catalog & Project Configuration** ✅ — Deterministic code-defined tool/template catalog seeding (`casp_inspired`), active/inactive tool & template version lifecycle metadata semantics, project-scoped active configuration persistence (`ProjectQualityAssessmentConfiguration`, migration `0014_quality_assessment_configuration.sql`), application service (`QualityAssessmentConfigurationService`), REST API (`GET /quality-assessment/tools`, `GET/PUT /projects/{id}/quality-assessment/configuration`), typed DTOs, project hard delete integration, cross-tool mismatch validation, and test suite. No execution workflow, GUI, or unverified template criteria.
- **8.3 — Quality Assessment Execution Backend** ✅ — Reviewer-specific Full-Text `INCLUDE` decision eligibility pipeline, loss & restoration of eligibility mechanics, project active configuration readiness gate, append-only assessment recording (`YES`, `NO`, `CANNOT_DETERMINE`), mandatory justification & required criteria completeness validation, authoritative backend question/guidance snapshot construction, application service (`QualityAssessmentExecutionService`), REST API (`GET /overview`, `GET /records`, `POST /assessments`, `GET /records/{id}`, `GET /records/{id}/history`), typed DTOs, reviewer & project isolation, and unit/integration test suite. No GUI or scoring schemes.
- **8.4 — Quality Assessment Interface (GUI)** ✅ — Full-featured execution & configuration React interface, reviewer-specific progress overview bar (`Eligible`, `Assessed`, `Remaining`), status filters (`UNASSESSED`, `ALL`, `ASSESSED`), readiness alerts & blocking states (`NO_QUALITY_ASSESSMENT_CONFIGURATION`, `NO_ELIGIBLE_PUBLICATIONS`), tool & template version config selector with explicit template change confirmation prompt, publication context & abstract view, segmented response choice controls (`TAK`, `NIE`, `NIE MOŻNA OKREŚLIĆ`), criterion-level mandatory justification textareas, `Save` & `Save & Next` actions with `UNASSESSED` pagination invariant preservation, append-only history audit trail drawer, dirty draft warning, frontend service (`qualityAssessmentApi`), and Vitest test suite (`160/160 PASS`).
- **8.5 — Lean Energy QA v1 Production Template & E2E** ✅ — First production quality assessment template (`lean_energy` v1) seeded under `casp_inspired` tool by `seed_built_in_catalog()`, derived exclusively from SLR Protocol v0.10 Chapter IX. Exactly 7 required criteria (QA1–QA7) with Polish-language questions and structured YES/CANNOT_DETERMINE/NO response guidance. Stable deterministic UUIDs (`LEAN_ENERGY_TEMPLATE_ID`, criterion IDs `e2e85001-...-11` through `-17`). Idempotent INSERT-only seed semantics with `SeedCatalogConflictError` on content drift. No scoring engine, no total score, no quality class, no automatic exclusion, no Full-Text decision modification. Comprehensive E2E integration test suite (23 tests): catalog seed verification, 7-criteria order/content assertion, full assessment workflow (configure → overview → record detail → 7-response submit → progress update → append-only history), Full-Text decision immutability invariant, negative validation (missing required, blank justification, duplicate criterion, non-template criterion, ineligible publication). Frontend `getTools` enriched with template data. All quality gates green (1158 backend, 163 frontend, ruff, mypy, tsc, build clean).
- **Next increment: 8.6 — Template Builder GUI / Additional Assessment Tools** ➡️

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

Status: ✅ Completed (persistent project resource, list/create/open/edit,
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
