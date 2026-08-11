# Implementation Plan

This document contains the detailed implementation order.

Unlike ROADMAP.md, this file is intentionally technical and may change frequently.

---

# Current Status

Current release:

v0.3.3 — Project Management, Screening, and Dashboard/Search Polish

Status:

✅ Completed

Release scope:

- persistent Project resource with archive, restore and atomic hard delete;
- authoritative `SearchResultSnapshot` records and preservation of provider
  metadata/provenance during live-search import;
- canonical deduplicated Screening Input Set with typed readiness;
- Title & Abstract backend workflow and reviewer-specific append-only decision
  progress;
- executable Title & Abstract Screening GUI;
- manual and metadata-rule screening criteria with server-authoritative
  automatic assessments and auditable rule/value/result snapshots.
- Full-Text Screening with reviewer-specific eligibility, availability metadata,
  structured exclusion reasons, and append-only decisions;
- Screening audit/report read models with criterion snapshot schema v2,
  reviewer-specific progress, transitions, and exclusion-reason aggregation;
- Dashboard/Search polish: corrected search import contract, provider Load More,
  append-only result pagination, local pagination, and cross-page selection.

Next milestone:

Phase 7.9 — Screening Integration and Release (Not Started)

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

# Phase 6.7 — Functional Workflow for Modules 1–4 ✅

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
- At the time of v0.1.7, the demonstrator Working Collection was process-local (in-memory). It was replaced by durable SQLite persistence in v0.2.0.
- OpenAlex and Crossref failures are isolated and reported as partial errors.
- Live result IDs use deterministic UUID5 identity based on provider and
  `source_id`.
- Re-importing the same `(project_id, provider, source_id)` is skipped and the
  response reports `imported_count`, `skipped_count`, and `total_requested`.
- The demonstrator Working Collection exists only in backend process memory
  and is reset when the server restarts.
- Modules 3 and 4 will be specified after acceptance of Modules 1 and 2.

---

# Phase 6.8 — End-to-End Literature Search Workflow 🟨

Cel:

- pełny proces Search Strategy i Sources Ingestion dostępny z GUI
- zastępowanie danych demonstracyjnych trwałymi kontraktami backendowymi
- wstrzymanie rozwoju kolejnych ekranów opartych o mocki

## 6.8.1 Search Strategy Backend

Zakres:

- trwały, projektowy model Search Strategy
- istniejący provider-independent Search Query jako wersjonowane drzewo Boolean
- pytania badawcze, grupy pojęć, terminy i operatory logiczne
- ograniczenia lat, języków, typów publikacji i dodatkowych limitów
- wybór OpenAlex, Crossref i Semantic Scholar
- migracja SQLite (`0001_search_strategies.sql`)
- `GET /projects/{project_id}/search-strategy`
- `PUT /projects/{project_id}/search-strategy`
- walidacja i pełna serializacja
- testy domeny, repozytorium i API

Status:

✅ Completed

---

## 6.8.2 Provider-Specific Query Rendering

Zakres:

- dedykowane renderery `OpenAlexQueryRenderer` oraz `CrossrefQueryRenderer` tłumaczace kanoniczny `SearchQuery` do fizycznej składni zapytań providera
- śledzenie zachowania semantyki (`is_lossless`) oraz rejestracja ostrzeżeń audytowych (`warnings`) przy uproszczeniu zapytania dla Crossref
- integracja w `SearchEngine.execute()` — każdy `SearchRun`, provenancja oraz surowe archiwum przechowują dokładnie wykonane zapytanie fizyczne
- rozszerzenie kontraktu API `POST /executions` o `provider_queries` oraz prezentacja w interfejsie użytkownika

Status:

✅ Completed

---

## 6.8.3 Search Orchestrator

Zakres:

- wielowątkowa/sekwencyjna egzekucja providerów w `SearchEngine`
- wydzielony `SearchRun` per provider z dedykowanymi znacznikami czasu i statusami
- izolacja błędów providerów (partial failure handling)
- ujednolicona normalizacja wyników i scalanie duplikatów DOI (`ResultMerger`)
- rejestracja provenancji wyszukiwania i egzekucji (`SearchExecutionProvenance`)
- generowanie kandydatów na duplikaty (`DuplicateGroupBuilder`)

Status:

✅ Completed

---

## 6.8.4 Search Execution API

Zakres:

- `POST /projects/{project_id}/search-strategy/executions` realizuje na żywo wyszukiwanie u providerów
- zwraca `rendered_query`, wybrane providery, timestamp wykonania, całkowitą i zwróconą liczbę wyników
- zwraca metadane stronicowania (`next_cursor`, `has_more`), listę wyników i błędy providerów
- ograniczenie: brak trwałego zasobu wykonania do późniejszego odczytu statusu `SearchRun` lub wyników po ID execution

Status:

🟨 Partial

---

## 6.8.5 Search Execution Persistence

Zakres:

- publikacje Working Collection, Search Strategy, historia importu, normalizacja i decyzje deduplikacji są trwałe w SQLite
- brak trwałej bazy wykonania wyszukiwań: obiekty `SearchRun` nie posiadają tabeli w DB, historia egzekucji nie jest zapisywana
- archiwum surowych odpowiedzi providerów wykorzystuje nietrwały `_InMemoryRawResponseArchive` w `live_search.py`

Status:

🟨 Partial

---

## 6.8.6 Search Strategy GUI Integration

Zakres:

- Search Strategy UI korzysta wyłącznie z backendowego `GET` i `PUT`
- stan pusty dla projektów bez strategii
- edycja pytań badawczych, grup pojęć, operatorów Boolean, ograniczeń i wyboru providerów
- generyczny podgląd wyrażenia Boolean
- stany loading, dirty, saving, saved, validation oraz failure
- akcja `Szukaj` zapisuje strategię, wykonuje search na żywo i prezentuje wyniki/błędy na tym samym ekranie bez przechodzenia do Sources

Status:

✅ Completed

---

## 6.8.7 Sources Search Execution GUI

Zakres:

- skonsolidowanie uruchamiania wyszukiwania na ekranie Search Strategy
- ekran Sources & Imports dedykowany do prezentacji trwałego stanu intake, historii importu, podsumowań źródeł oraz uploadu plików bibliograficznych (.ris / .bib)

Status:

↪ Superseded by current Search Strategy execution workflow

---

## 6.8.8 GUI Import Integration

Zakres:

- obsługa uploadu plików `.ris` i `.bib` w interfejsie użytkownika
- obsługa punktu końcowego `POST /projects/{project_id}/imports`
- ponowne wykorzystanie parserów RIS i BibTeX oraz mapperów i normalizatorów
- trwały zapis pobranych publikacji w Working Collection oraz wpisu w historii importu
- automatyczne odświeżanie widoku Sources Summary

Status:

✅ Completed

---

## 6.8.9 Publication Intake Summary

Zakres:

- dedykowany serwis read model `SourcesSummaryService`
- punkt końcowy `GET /projects/{project_id}/sources-summary`
- zagregowane metryki Working Collection, podsumowania per źródło (sukcesy, ostrzeżenia, błędy, dodane rekordy, ostatni status)
- chronologiczna historia importów zwrócona do interfejsu graficznego

Status:

✅ Completed

---

### Screening Prerequisites and 7.5 Completion

W v0.3.1 rozwiązano oba warunki wejściowe dla wykonywalnego screeningu:
`SearchResultSnapshot` zachowuje autorytatywny canonical `Publication` wraz z
provenance dla importu live search, a `ScreeningInputService` tworzy stabilny,
niedestrukcyjny canonical/deduplicated input set. Nieobsłużone grupy duplikatów
oraz konflikty merge blokują gotowość screeningu. Pełna durable historia
`SearchRun` pozostaje odrębnym zakresem 6.8.5.

---

# Phase 7 — Screening

## 7.1 Screening Criteria Domain Model

Zakres:
- `ScreeningCriterion` domain object
- criterion identifier
- project association (`project_id`)
- name, description
- type: `INCLUSION` / `EXCLUSION`
- screening stage: `TITLE_ABSTRACT` / `FULL_TEXT` / `BOTH`
- display order, active/inactive flag, required/optional flag
- domain validation rules
- deterministic JSON serialization
- unit test suite
(Bez persistence i GUI)

Status: ✅ Completed (`ScreeningCriterion`, `ScreeningCriterionType`, `ScreeningCriterionStage`, validation, unit tests)

---

## 7.2 Screening Criteria Persistence and API

Zakres:
- SQLite persistence (`SqliteScreeningCriterionRepository`)
- database migration
- abstract repository contract (`ScreeningCriterionRepository` decorated with `@runtime_checkable`)
- CRUD / lifecycle operations (`create`, `get`, `list_by_project`, `update`, `deactivate` via `PATCH /deactivate`)
- project isolation and deterministic order preservation (`ORDER BY display_order ASC, criterion_id ASC`)
- REST API (`/projects/{project_id}/screening/criteria`)
- validation and contract test suites (34 tests)

Status: ✅ Completed (SQLite schema `0007_screening_criteria.sql`, `@runtime_checkable` `ScreeningCriterionRepository` contract, `SqliteScreeningCriterionRepository` adapter, project isolation, REST API, DTOs, tests)

---

## 7.3 Screening Configuration GUI

Zakres:
- list criteria, add/edit/remove/deactivate controls
- inclusion/exclusion and stage selection
- required/optional toggles and reordering
- description / instructions input
- backend API persistence integration
- loading, empty, error, and validation states
(Zero hardcoded criteria)

Status: ✅ Completed (ScreeningCriteriaList, ScreeningCriterionCard, ScreeningCriterionModal, projectApiService 4 API methods, error/loading/empty/validation states, zero hardcoded criteria, 22 frontend tests)

---

## 7.4 Screening Decision Domain and Persistence

Zakres:
- `ScreeningDecision` domain model
- project ID, publication ID, stage
- outcome: `INCLUDE` / `EXCLUDE` / `UNCERTAIN`
- criterion-level assessments
- decision rationale, reviewer attribution, timestamps
- decision history trail and criteria version/snapshot reference
- SQLite persistence (`SqliteScreeningDecisionRepository`) and database migration
- REST API and contract tests

Status: ✅ Completed (ScreeningDecision, CriterionAssessment, CriterionAssessmentValue, authoritative criterion snapshot, ScreeningDecisionService validation rules, SqliteScreeningDecisionRepository, migration 0008_screening_decisions.sql, REST API endpoints, 22 backend test cases, 100% AI-free)

---

## 7.5A Screening Input Prerequisites

Zakres:
- authoritative, durable snapshots of canonical live-search results
- preservation of screening-relevant metadata and provenance during import
- project-scoped canonical/deduplicated Screening Input Set
- APPROVE collapse through `PublicationMergePolicy`; REJECT records remain separate
- PENDING duplicate groups block readiness
- deterministic canonical identity and ordering without changing Working Collection
(Bez GUI, queue i decyzji screeningowych)

Status: ✅ Completed

---

## 7.5B Title & Abstract Screening Backend Workflow

Zakres:
- screening queue, eligibility and publication retrieval
- `TITLE_ABSTRACT` and `BOTH` criteria assessment
- integration with `ScreeningDecisionService`
- save/resume, latest decision, filtering and progress counters
- project-scoped backend API

Status: ✅ Completed

---

## 7.5C Title & Abstract Screening GUI

Zakres:
- title, abstract and metadata presentation
- criterion-level assessment and rationale
- INCLUDE / EXCLUDE / UNCERTAIN controls
- previous/next, save/resume, progress and state handling

Status: ✅ Completed

---

## 7.5D Automatic Metadata-Based Screening Criteria

Zakres:
- `MANUAL` i `METADATA_RULE` evaluation mode dla `ScreeningCriterion`
- bezpieczne, typed metadata rules dla roku publikacji, języka, typu dokumentu,
  open access oraz obecności DOI i abstractu
- czysty deterministic `ScreeningCriterionRuleEvaluator`
- server-authoritative automatic CriterionAssessment przy zapisie decyzji
- snapshot rule, evaluated metadata value i result w append-only historii
- konfiguracja rules w GUI oraz read-only automatyczne assessmenty w Title &
  Abstract Screening

Status: ✅ Completed

---

## 7.6 Full-Text Screening

Zakres:
- queue of publications eligible after Title & Abstract Screening
- `FULL_TEXT` and `BOTH` criteria assessment
- technical full-text availability status (URL, DOI link, external access) as workflow metadata (project-scoped criteria define whether lack of full text leads to exclusion)
- explicit exclusion reason and decision rationale
- `INCLUDE` / `EXCLUDE` / `UNCERTAIN` decision recording
- history view, save & resume, progress tracking
- GUI and backend integration
(Brak wymagania przechowywania chronionych plików PDF w aplikacji)

Status: ✅ Completed

---

## 7.7 Screening Audit Trail and Progress

Zakres:
- complete decision history audit trail
- reviewer attribution, timestamps, criteria version snapshot used
- decision change / override tracking
- stage-specific progress metrics (included, excluded, uncertain counts)
- exclusion-reason aggregation and project screening summary
- data extraction required for PRISMA flow chart
(Modyfikacja kryteriów nie powoduje utraty interpretacji decyzji historycznych)

Status: ✅ Completed

---

## 7.8A Multi-Reviewer Screening and Conflict Detection

Zakres:
- project-and-stage reviewer roster with active/inactive lifecycle history;
- derived `INCOMPLETE`, `AGREEMENT`, and `CONFLICT` status from latest reviewer-specific decisions;
- conflict queue with pending reviewers, pagination/filtering, blind-aware outcome presentation, and agreement metrics;
- reporting extension and project/stage isolation without N+1 reads.

Poza zakresem: adjudication, resolution history, majority vote, resolved
project outcome, oraz zmiany reviewer-specific eligibility Full Text/QA.

Status: ✅ Completed

---

## 7.8B Conflict Resolution / Adjudication

Zakres:
- explicit resolver workflow and rationale;
- immutable resolution history and stale-resolution detection;
- future project-level resolved outcome, without automatic majority vote.

Status: ✅ Completed

---

## 7.9 Screening Integration and Release

Zakres:
- Project Dashboard integration
- workflow stage status transitions (Deduplication → Screening → Quality Assessment)
- empty, loading, and error states
- backend and frontend integration test suites
- end-to-end verification and documentation reconciliation
- release verification

Status: ➡️ Next / Not Started

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

Status: ✅ Integrated

- persistent SQLite-backed Project resource and project-scoped REST API
- list, create, open/select, edit, archive and restore workflows
- project list/table GUI with persisted active-project selection and fallback
- destructive hard-delete confirmation and atomic cleanup of project-owned data
- cleanup includes live-search result snapshots after integration with Phase 7.5A

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
