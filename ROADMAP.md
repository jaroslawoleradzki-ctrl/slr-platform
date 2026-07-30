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
connects the workflow to live providers and the project Working Collection in
v0.1.7. The demonstrator collection is process-local and does not survive a
backend restart.

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

### Version 0.1.9 increment

The first project-scoped bibliographic upload is implemented: the Sources
upload control sends one `.ris` or `.bib` file to
`POST /projects/{project_id}/imports`, reuses the existing parsers, and stores
the parsed publications through the existing repository. This is an initial
upload slice now includes durable project-scoped import history returned
newest-first by `GET /projects/{project_id}/imports`. GUI Import Integration
(6.8.8) remains open until provider execution status and the broader Sources
ingestion workflow are implemented.

Background jobs, provider status APIs, full import history and full Sources
Ingestion remain unimplemented.

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
