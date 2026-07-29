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

# Phase 6 — GUI Foundation and Duplicate Review

## 6.1 Frontend Architecture and Application Shell

Zakres:

- frontend technology and project structure
- application shell
- routing
- navigation
- common layout
- shared component conventions
- configuration handling

Status:

⬜ Planned

---

## 6.2 API Client and Shared UI States

Zakres:

- API client boundary
- request and response handling
- loading states
- empty states
- error states
- validation feedback
- reusable table and form patterns

Status:

⬜ Planned

---

## 6.3 Deduplication Backend Integration

Zakres:

- expose completed deduplication capabilities through an application or API boundary
- preserve duplicate groups, comparison data and provenance
- provide deterministic contracts for the frontend
- no new deduplication logic beyond Phase 5

Status:

⬜ Planned

---

## 6.4 Duplicate Groups UI

Zakres:

- duplicate group list
- group status
- record counts
- filtering and navigation
- provenance summary

Status:

⬜ Planned

---

## 6.5 Duplicate Comparison and Review UI

Zakres:

- side-by-side publication comparison
- identifier and metadata differences
- provenance visibility
- duplicate confirmation
- merge candidate review
- decision rationale where required

Status:

⬜ Planned

---

## 6.6 Integration and Contract Tests

Zakres:

- backend–frontend contract verification
- duplicate workflow integration
- loading, empty and failure cases
- deterministic review behavior

Status:

⬜ Planned

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
