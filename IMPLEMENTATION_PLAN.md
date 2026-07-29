# Implementation Plan

This document contains the detailed implementation order.

Unlike ROADMAP.md, this file is intentionally technical and may change frequently.

---

# Current Status

Current milestone:

Phase 5 — Deduplication (completed)

---

# Phase 5 — Deduplication ✅

## 5.1 Deduplication Domain Model

- duplicate group and publication membership
- explicit group status
- immutable decision history
- controlled status transitions
- infrastructure-independent domain invariants

Status:

✅ Completed

---

## 5.2 Merge Policy

- deterministic merge
- provenance preservation
- metadata priority
- explicit identifier conflicts
- commutative and idempotent behavior

Status:

✅ Completed

---

## 5.3 Duplicate Groups

- grouping
- candidates based on DOI, PMID and OpenAlex identifiers
- transitive connected groups
- stable ordering
- deterministic group identity

Status:

✅ Completed

---

## 5.4 Search Engine Integration

- duplicate group analysis on normalized publications before ResultMerger
- SearchExecution duplicate group results
- no automatic decisions or publication merge

Status:

✅ Completed

---

## 5.5 Tests

- domain invariants and transitions
- merge policy determinism and conflicts
- duplicate grouping edge cases
- ResultMerger regression behavior
- SearchEngine integration and contracts
- complete Phase 5 regression suite

Status:

✅ Completed

---

# Modular Implementation Workflow

Starting with the graphical application foundation, functional phases are developed as vertical, reviewable increments.

Typical sequence:

1. architecture and scope definition
2. backend or domain implementation
3. backend review
4. API and data contract stabilization
5. frontend module implementation
6. integration review
7. automated quality checks
8. documentation
9. commit and push

Backend business rules remain authoritative.

The frontend must consume approved contracts and must not independently redefine domain rules, workflow states, provenance semantics or validation policy.

Each functional phase should end with a usable backend capability and a corresponding graphical module whenever the feature is user-facing.

---

# Phase 6 — GUI Foundation and Duplicate Review 🚧

## 6.1 GUI Foundation

Zakres:

- frontend technology and project structure
- application shell and responsive navigation
- Information Architecture and SLR process funnel
- Concept Group strategy builder
- state placeholders for downstream phases

Status:

✅ Completed

---

## 6.2 Application Versioning and GUI Release Identity

Zakres:

- application-wide single source of truth in root `VERSION` file
- build-time Vite injection of `__APP_VERSION__` constant with regex validation & fallback
- GUI release identity (Header caption, Sidebar footer, About modal)
- versioning policy documentation (`docs/VERSIONING.md`) and CHANGELOG

Status:

✅ Completed

---

## 6.3 Duplicate Review Read API

Zakres:

- backend DTO contracts (`DuplicateGroupListResponse`, `DuplicateGroupResponse`, `DuplicateRecordPreviewResponse`)
- read-only REST endpoint `GET /projects/{project_id}/duplicate-groups`
- application service (`ProjectDuplicateService`) mapping `DuplicateGroupBuilder` results to DTOs
- frontend API client adapter with CORS and `VITE_API_BASE_URL` config
- handling loading, success, empty and error states in `DeduplicationPage`
- hybrid data mode indicator in GUI

Status:

✅ Completed

---

## 6.4 Duplicate Review Decisions

Zakres:

- in-memory decision repository (`InMemoryDuplicateReviewDecisionRepository`) with `(project_id, group_id)` composite key isolation
- REST endpoints for recording (`POST`) and reading (`GET`) reviewer duplicate decisions (`APPROVE`, `REJECT`)
- service validation (checking project and group existence, invalid enum handling, decision overwrite support)
- interactive frontend decision controls (Approve, Reject, Saving..., Saved, Error, Retry)
- status badges in card header (Approved, Rejected, Pending)

Status:

✅ Completed

---

## 6.5 Duplicate Comparison and Review UI

Zakres:

- side-by-side publication comparison view for candidate group members
- deterministic field matching and difference calculation (MATCH, DIFFERENT, PARTIAL, UNAVAILABLE)
- provenance tracing per publication record
- optional reviewer decision rationale (`rationale`) with trimming and length validation (max 1000 chars)
- accessibility attributes (`aria-expanded`) and clear visual/text badge states

Status:

✅ Completed

---

## 6.6 Integration and Contract Tests

Zakres:

- backend contract tests for OpenAPI / DTO schemas and HTTP endpoints (`tests/contract/api/test_deduplication_contract.py`)
- full duplicate review workflow integration tests (`tests/integration/api/test_deduplication_workflow_integration.py`)
- frontend integration and regression test suite (`frontend/tests/DeduplicationIntegration.test.tsx`)
- automated Python DTO ↔ TypeScript types parity verification
- determinism verification and edge case handling (rationale limit, project isolation, null venue/provenance)

Status:

✅ Completed

---

# Phase 6.7 — Functional Workflow for Modules 1–4 🚧

Before extending the SLR workflow with additional product phases, the existing
user-facing workflow must become fully functional and manually verifiable.

## 6.7.1 Functional Search Strategy

Zakres:

- editable year range
- selectable providers
- editable concept groups
- validation
- Execute action
- Repeat action
- application state
- backend integration
- manual browser acceptance test

Status:

✅ Completed

## 6.7.2a Search Results Workflow

Zakres:

- search result presentation
- controlled deterministic result data
- backend response contract
- record selection
- project-scoped result state
- loading, success, empty and error states
- manual browser acceptance
- no live OpenAlex or Crossref calls
- no persistent project import

Status:

✅ Completed

## 6.7.2b Live Search Providers & Import

Zakres:

- live OpenAlex and Crossref execution
- existing retry and rate limiting
- mapping provider records to the common publication model
- partial provider errors and provider attribution
- bibliographic import
- import of selected records into one project collection
- integration tests with mocked providers
- manual verification against live APIs

Status:

✅ Completed

Notes:

- Module 2 currently does not need to repeat the complete search query.
- Selected live search records can be imported into the in-memory project
  Working Collection.
- OpenAlex and Crossref failures are isolated and reported as partial errors.
- Live result IDs use deterministic UUID5 identity based on provider and
  `source_id`.
- Re-importing the same `(project_id, provider, source_id)` is skipped and the
  response reports `imported_count`, `skipped_count`, and `total_requested`.
- The demonstrator Working Collection exists only in backend process memory
  and is reset when the server restarts.
- Modules 3 and 4 will be specified after acceptance of Modules 1 and 2.

---

# Phase 7 — Screening

## 7.1 Screening Domain and Workflow

Zakres:

- screening state
- inclusion and exclusion decisions
- screening stage
- rationale
- reviewer attribution
- decision history
- conflict representation

Status:

⬜ Planned

---

## 7.2 Screening Application Services and API

Zakres:

- screening queues
- publication assignment
- decision submission
- history retrieval
- conflict visibility
- progress information

Status:

⬜ Planned

---

## 7.3 Screening UI

Zakres:

- title and abstract screening view
- full-text screening view
- inclusion and exclusion controls
- rationale input
- publication metadata and provenance
- progress and queue navigation

Status:

⬜ Planned

---

## 7.4 Screening Conflict and Review UI

Zakres:

- conflicting decisions
- reviewer comparison
- resolution workflow
- decision history

Status:

⬜ Planned

---

## 7.5 Screening Integration and Contract Tests

Status:

⬜ Planned

---

# Phase 8 — Quality Assessment

## 8.1 Quality Assessment Domain

Zakres:

- quality criteria
- assessment forms
- rating or scoring schemes
- reviewer attribution
- rationale
- assessment history
- agreement and disagreement representation

Status:

⬜ Planned

---

## 8.2 Quality Assessment Application Services and API

Zakres:

- assessment assignment
- form retrieval
- assessment submission
- score or rating calculation where configured
- history retrieval
- progress information

Status:

⬜ Planned

---

## 8.3 Quality Assessment UI

Zakres:

- assessment workspace
- configurable criteria display
- rating and scoring controls
- rationale input
- publication context
- provenance visibility
- progress tracking

Status:

⬜ Planned

---

## 8.4 Quality Assessment Review UI

Zakres:

- reviewer comparison
- disagreement visibility
- assessment history
- review and resolution support

Status:

⬜ Planned

---

## 8.5 Quality Assessment Integration and Contract Tests

Status:

⬜ Planned

---

# Phase 9 — Data Extraction

## 9.1 Data Extraction Domain

Zakres:

- extraction forms
- extraction fields
- structured extracted values
- reviewer attribution
- extracted-value provenance
- validation
- extraction history

Status:

⬜ Planned

---

## 9.2 Data Extraction Application Services and API

Zakres:

- extraction form retrieval
- extraction assignment
- draft and final extraction handling
- validation
- history retrieval
- dataset generation

Status:

⬜ Planned

---

## 9.3 Data Extraction UI

Zakres:

- extraction workspace
- configurable forms
- structured field controls
- publication context
- validation feedback
- draft and completion states
- progress tracking

Status:

⬜ Planned

---

## 9.4 Extraction Dataset View

Zakres:

- tabular extracted data
- filtering
- completeness indicators
- traceability to publication and reviewer
- export preparation

Status:

⬜ Planned

---

## 9.5 Data Extraction Integration and Contract Tests

Status:

⬜ Planned

---

# Phase 10 — Evidence Synthesis

## 10.1 Evidence Synthesis Domain

Zakres:

- synthesis groups
- themes
- evidence tables
- research-gap representation
- traceability to extracted data and publications

Status:

⬜ Planned

---

## 10.2 Evidence Synthesis Application Services and API

Zakres:

- synthesis dataset preparation
- thematic grouping
- evidence table generation
- bibliometric data preparation
- traceability retrieval

Status:

⬜ Planned

---

## 10.3 Evidence Synthesis UI

Zakres:

- synthesis workspace
- thematic grouping interface
- evidence tables
- comparison views
- traceability navigation
- research-gap notes

Status:

⬜ Planned

---

## 10.4 Bibliometric Support UI

Zakres:

- bibliometric summaries
- publication, author and venue views
- trend views
- supporting data tables
- no AI-generated interpretation at this phase

Status:

⬜ Planned

---

## 10.5 Evidence Synthesis Integration and Contract Tests

Status:

⬜ Planned

---

# Phase 11 — Integrated GUI MVP

## 11.1 Workflow Integration

Zakres:

- connect search, import, deduplication, screening, quality assessment, data extraction and synthesis
- unified navigation
- consistent application state
- consistent error handling
- end-to-end workflow transitions

Status:

⬜ Planned

---

## 11.2 Search and Import UI Completion

Status:

⬜ Planned

---

## 11.3 Cross-Module Navigation and Context

Zakres:

- publication context shared across modules
- project and workflow context
- progress visibility
- return paths between workflow stages

Status:

⬜ Planned

---

## 11.4 Settings and Configuration UI

Status:

⬜ Planned

---

## 11.5 End-to-End User Journey Tests

Status:

⬜ Planned

---

## 11.6 GUI MVP Stabilization

Zakres:

- accessibility baseline
- usability fixes
- consistency review
- performance review
- release readiness

Status:

⬜ Planned

---

# Phase 12 — Reporting

...

---

# Phase 13 — Project Management

...

---

# Phase 14 — UX

...

---

# Phase 15 — AI

### AI Assistant

### AI Ranking

### AI Summaries

### AI Recommendations

### AI Extraction
