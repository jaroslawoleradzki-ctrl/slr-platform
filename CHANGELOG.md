# Changelog

## [0.5.8] — 2026-08-24

### Fixed

- **HTTP 422 Deprecation Cleanup**:
  - Replaced deprecated `HTTP_422_UNPROCESSABLE_ENTITY` constant with `HTTP_422_UNPROCESSABLE_CONTENT` across all API router modules.
  - Preserved numeric HTTP 422 status behavior and all existing API contracts.
  - Reduced backend test validation warnings from 12 to 1.
  - Deferred Starlette TestClient/httpx2 migration to a dedicated dependency-maintenance release.

## [0.5.7] — 2026-08-24

### Added

- **Canonical Duplicate Merge**:
  - Separates reviewer APPROVE/REJECT decisions from the technical merge lifecycle.
  - Explicit canonical merge operation.
  - Deterministic canonical record selection.
  - Preservation of all original publication records.
  - `superseded_by` relationships instead of destructive deletion.
  - Durable merge history and pre-merge snapshots.
  - Atomic SQLite merge transaction.
  - Protection against merging already-superseded members.
  - Active-canonical-only downstream processing.
  - PRISMA-compatible pre/post-deduplication accounting.
  - Explicit frontend APPROVE -> MERGE -> MERGED workflow.
  - Project deletion cleanup.
  - Integrity/audit support.

## [0.5.6] — 2026-08-21

### Added

- **Manual Import Source Provenance**: Explicit bibliographic source tracking for manual file imports (RIS/BibTeX). Researchers can now record the true source database: Google Scholar (Publish or Perish), Scopus, Web of Science, PubMed, EBSCO, ProQuest, or Other.
- **Optional Source Labels**: Free-text source labels (e.g., "Google Scholar search 2026-08-21") for additional context on manual imports.
- **Provenance Preservation**: Source database metadata preserved through normalization pipeline and deduplication merge. Merged publications retain all source provenance entries.
- **Import History Metadata**: Import history records now store `source_database` and `source_label` fields, displayed in the Sources & Imports UI.
- **PRISMA Manual Source Breakdown**: PRISMA funnel metrics now include `manual_source_breakdown` showing per-source record counts (e.g., `google_scholar_pop: 312, scopus: 180`) while preserving aggregate `records_identified_imports`.
- **Import History UI**: FileDropzone now shows source database badges with icons and optional source labels in the import history table.
- **PRISMA Flow Diagram Enhancement**: LivePrismaFlowChart now displays manual import source breakdown with per-source counts.
- **Database Migration**: Added `source_database` and `source_label` columns to `import_history` table (migration 0021).

### Known Limitations

- Google Scholar remains an external workflow via Publish or Perish → RIS/BibTeX → SLR Platform import; no direct API integration.
- `source_label` remains optional; UI does not enforce it for `other` source.

## [0.5.5] — 2026-08-21

### Added

- **Semantic Scholar Live API Provider**: Restored Semantic Scholar as a fully functional live search provider alongside OpenAlex and Crossref.
- **Official Academic Graph API Integration**: Implemented `SemanticScholarClient` for the Graph API paper search endpoint (`GET /graph/v1/paper/search`) with query, limit, offset, and fields parameters.
- **Optional Backend API Key**: Added `SEMANTIC_SCHOLAR_API_KEY` environment variable (backend-only, sent via `x-api-key` header, never exposed to frontend).
- **Rate-Limit Handling & Resilience**: Tenacity-based retries for HTTP 429/500/502/503/504, exponential backoff, `Retry-After` header support (seconds and HTTP-date), bounded attempts (default 3), in-process throttling at 1 request/second.
- **Pagination & Completeness Handling**: Offset-based pagination using API's `total`/`offset`/`next` fields; explicit truncation warnings when the relevance search endpoint caps results at 1000; `next_cursor`/`has_more` metadata for load-more flow.
- **Canonical Mapping & Provenance**: Semantic Scholar paper records mapped to canonical `Publication` via existing normalization pipeline; paperId preserved as provenance `source_record_id` and identifier; DOI/PMID extracted from `externalIds`; abstract mapped when available (no fabrication).
- **Filter Transparency**: Strategy filters (year range, languages, publication types, open access) not applied by endpoint generate explicit warnings (`is_lossless=False`) rather than silently dropping constraints.
- **Frontend Provider Selection**: Semantic Scholar enabled in Search Strategy provider selector; checkbox no longer disabled.
- **Live PRISMA Integration**: Semantic Scholar provider imports counted in `records_identified_providers` via existing import history aggregation (provider-agnostic).
- **Comprehensive Test Coverage**: 50 new backend tests covering client resilience, pagination, deterministic record IDs, truncation warnings, filter warnings, live search wiring, and PRISMA integration; frontend test updated for enabled provider.

### Known Limitation

- Semantic Scholar relevance search has an upstream result ceiling (1000 records); SLR Platform reports retrieval completeness/truncation via warnings and `total_count`/`has_more` rather than silently presenting incomplete retrieval as complete.

## [0.5.4] — 2026-08-20

### Added

- **Live PRISMA Metrics**: Added authoritative backend PRISMA project metrics.
- **Live PRISMA diagram**: The PRISMA flow diagram now reflects actual live
  workflow counts computed from the project's persisted ingestion,
  deduplication, and screening state.
- **Partial workflow support**: Metrics are reported independently per stage, so
  partially completed SLR workflows show real counts for completed stages while
  later stages remain zero until decisions exist.
- **Persisted state**: Metrics use persisted ingestion, deduplication and
  screening state as the single source of truth.
- **Removed placeholder behavior**: Removed the placeholder zero-only PRISMA
  behavior in favor of real backend-provided funnel metrics.
- **Improved Exports & PRISMA reporting accuracy**: `GET
  /projects/{project_id}/prisma/metrics` exposes the authoritative funnel read
  model to the Exports page, with loading, error, and live-data states.

## [0.5.3] — 2026-08-20

### Added

- **Functional Exports & PRISMA UI**: CSV and JSON exports now download the
  publications extraction dataset through the existing extraction export
  endpoint. BibTeX, RIS, and Excel exports remain clearly disabled as "Not yet
  available" until a backend implementation exists.
- **Live PRISMA 2020 Flow Diagram**: The existing `LivePrismaFlowChart` is now
  integrated into the Exports page, rendering from project metrics. PRISMA
  SVG/PNG/PDF export remains intentionally unavailable, and backend-provided
  PRISMA funnel metrics are not yet available, so the diagram currently depends
  on existing project metrics.

## [0.5.2] — 2026-08-18

### Fixed & Improved

- **Crossref REST API Hardening**: Production-grade Crossref search integration
  achieving parity with OpenAlex and adhering to Crossref polite pool guidelines.
- **Bounded Cursor Pagination**: Deep cursor pagination (`cursor=*`, `next-cursor`)
  with configurable `max_results` bound, cycle prevention for repeating cursors,
  and accurate `total_count`, `next_cursor`, and `has_more` response metadata.
- **Filter Mapping & Audit Warnings**: Mapped publication year range and supported
  document types to Crossref API filters; explicit audit warnings and lossy state
  tracking (`is_lossless=False`) for unsupported filters (`languages`, `open_access`, `review`).
- **Boolean Syntax Handling**: Flattened OR terms to keywords and excluded NOT clauses
  from physical query string with preserved canonical query audit metadata and warnings.
- **Polite Access & Resilient Retries**: Dynamic `User-Agent` with application version,
  `mailto:` identification, polite rate limiting (20 rps), exponential backoff for 429,
  5xx, and timeouts, `Retry-After` header parsing (seconds and HTTP-date), and immediate
  failure without retrying permanent 4xx errors.
- **Metadata Mapping & Collective Authors**: Faithful mapping of individual and
  collective/corporate authors (`name` field), robust date hierarchy with year fallback
  on invalid day parts, clean abstract sanitization, and deterministic fallback `source_record_id`
  and UUID5 `record_id` for works lacking DOI.

## [0.5.1] — 2026-08-17

### Fixed

- **Reviewer Identity Persistence**: Reviewer identity now persists across page
  refreshes through canonical `useReviewerIdentity()`, eliminating duplicate
  page-level persistence state.
- **Quality Assessment Justification Rules**: Assessment justification is now
  optional for `YES` responses while remaining strictly required for `NO` and
  `CANNOT_DETERMINE`.
- **Quality Assessment Save & Next Progression**: `Save and Next` now advances
  deterministically to the next publication in sequence without resetting to the
  first publication or jumping backward at the end of the unassessed queue.
- **Quality Assessment Filtering**: Standardized on canonical `status` query
  parameter for QA filtering, maintaining backwards compatibility for legacy
  `status_filter`, and returning HTTP 422 if conflicting values are supplied.
- **Workflow & Dashboard State Synchronization**: Dashboard and Sidebar navigation
  now use shared workflow status derivation reflecting actual project stage
  readiness instead of duplicated stale page state.
- **Exports & PRISMA Actionable Semantics**: Exports and PRISMA availability is
  derived as actionable/pending_action once upstream stages are satisfied,
  preventing false premature completed status.

## [0.5.0] — 2026-08-16

### Added

- Completed Phase 10 Data Synthesis: researcher-controlled deterministic
  terminology classification, Lean–EE Analytical Matrix, mechanism and
  context synthesis, Research Gap synthesis, and immutable Synthesis
  Snapshots with deterministic identity and JSON/CSV exports.
- Preserved project isolation and traceability, COMPLETE-only eligible
  evidence semantics, and criterion-level QA integration across synthesis.
- Confirmed that SLR Platform provides no built-in AI/LLM functionality.

## [0.4.9] — 2026-08-15

### Fixed

- Added the ADR-0007 Extraction Correctness Foundation, including explicit
  `UNASSESSED` field state, server-authoritative completion validation, narrow
  legacy hydration compatibility, and safe revision/value identity handling.

## [0.4.8] — 2026-08-15

### Added

- Added project-level Data Extraction template configuration workflow with
  explicit template/version selection, field preview, and eligibility refresh.

## [0.4.7] — 2026-08-15

### Fixed

- Data Extraction now retains and displays the backend eligibility population
  when a project has no extraction configuration. Blocked publications expose
  the `no_extraction_configuration` reason in the default table view instead
  of appearing as an unexplained empty list.

## [0.4.6] — 2026-08-12

### Added

- Completed Phase 9 Data Extraction: configurable persistence, QA-aware
  eligibility, validated execution, append-only revisions, provenance,
  dynamic GUI, table/matrix/progress workflows, and Lean Energy E1–E14
  template support.
- Added system-bound E1 canonical publication context and preservation of
  multiple Lean–EE relationships.
- Added deterministic JSON and CSV exports with separate publication and
  relationship datasets, current-state completeness semantics, provenance,
  and template version traceability.
- Formalized the completed Phase 7 Screening and Phase 8 Quality Assessment
  release scope.

### Validation

- Backend: 1291 tests passed; frontend: 184 tests passed.
- Ruff, MyPy, TypeScript, production build, and `git diff --check` passed.

Phase 10 is not included in this release.

## [0.3.3] — 2026-08-11

### Added

- **Dashboard and Search polish**: the project dashboard exposes the available
  Title & Abstract and Full-Text workflows while later quality stages remain
  clearly unavailable.
- Search results now support provider-backed Load More, append additional
  results without replacing existing selections, and local pagination across
  all loaded records.

### Fixed

- Aligned the Search Strategy → Import request contract across the browser and
  backend, preserving the existing 7.6 Full-Text Screening workflow.

### Notes

- Phase 7.7 Screening Audit Trail and Progress remains planned.

## [0.3.2] — 2026-08-11

### Added

- **Full-Text Screening**: Reviewer-specific eligibility derived from the
  current canonical input and latest Title & Abstract `INCLUDE` decision.
- Added a derived Full-Text queue with deterministic status, progress,
  filtering, pagination and Save / Save & Next workflow.
- Added active `FULL_TEXT` / `BOTH` criteria, including server-authoritative
  automatic metadata assessments.
- Added project-scoped full-text availability and external reference metadata;
  no copyrighted PDF storage is required.
- Added structured exclusion reasons linked to immutable criterion assessment
  snapshots while preserving append-only decision history.
- Added executable Full-Text GUI with reviewer identity, metadata, criteria,
  availability, history, navigation and `INCLUDE` / `EXCLUDE` / `UNCERTAIN`.

### Fixed

- Integrated Full-Text availability cleanup into atomic project hard delete.
- Preserved Full-Text history when a publication temporarily loses eligibility.

### Notes

- Phase 7.7 audit-trail aggregation remains planned.

## [0.3.1] — 2026-08-10

### Added

- **Project Management**: Persistent projects with list, create, open, edit,
  archive and restore workflows. The active project is retained across reloads.
- **Safe permanent project deletion**: A named confirmation flow and one atomic
  backend transaction remove project-owned data without affecting other
  projects.
- **Screening Input**: Durable live-search result snapshots preserve canonical
  publication metadata and provenance for later import. Approved duplicate
  groups now produce one canonical, non-destructive screening input record;
  rejected groups remain independent and unresolved groups explicitly block
  readiness.
- **Title & Abstract Screening**: Executable project-scoped screening UI with
  explicit reviewer identity, progress, filters, deterministic navigation,
  criterion-level assessments, `INCLUDE` / `EXCLUDE` / `UNCERTAIN`, rationale,
  Save and Save & Next. Decisions retain append-only history and resume from
  the latest reviewer decision.
- **Automatic metadata criteria**: Criteria can be manual or evaluated from
  publication metadata using safe, deterministic rules for publication year,
  language, document type, open-access state, DOI presence and abstract
  presence. Automatic assessments are generated by the backend and presented
  read-only in screening.

### Fixed

- Aligned the Search Strategy provider request contract across frontend and
  backend; new live-search imports retain abstracts and other available
  screening-relevant metadata.
- Added `search_result_snapshots` cleanup to atomic project deletion and
  retained DELETE support in the browser API integration.
- Improved dark-theme readability and selected states for screening inputs,
  criterion assessments and decision controls.

### Notes

- Historical Working Collection records are not automatically enriched or
  backfilled when their stored metadata lacks an abstract.

## [0.3.0] — 2026-08-10

### Added

- **Phase 7.4 Screening Decision Domain and Persistence**: Added project-scoped screening decision domain model (`ScreeningDecision`), `ScreeningOutcome` (`INCLUDE`, `EXCLUDE`, `UNCERTAIN`), `CriterionAssessmentValue` (`MET`, `NOT_MET`, `UNCERTAIN`, `NOT_ASSESSED`), and `CriterionAssessment`.
- Added server-side authoritative criterion snapshot construction in `ScreeningDecisionService` to capture immutable criterion metadata (`criterion_id`, `criterion_name`, `criterion_type`, `criterion_stage`, `criterion_is_required`) at decision time.
- Added business rule validations in `ScreeningDecisionService`: publication existence and project ownership, criteria project ownership, inactive criterion rejection for new decisions, stage compatibility (`TITLE_ABSTRACT` or `FULL_TEXT`), required active criteria completeness, duplicate assessment input rejection, and explicit human outcome selection (no automatic outcome derivation).
- Added durable SQLite persistence in `SqliteScreeningDecisionRepository` and migration `0008_screening_decisions.sql` with composite primary key `(decision_id, criterion_id)` on `screening_criterion_assessments`.
- Implemented append-only decision history and deterministic latest decision resolution per `(project_id, publication_id, stage, reviewer_id)`.
- Added project-scoped REST API endpoints (`/projects/{project_id}/screening/decisions`, `GET .../latest`, `GET .../history`, `GET .../{decision_id}`) and DTOs.
- 100% AI-free design with 22 backend test cases.

## [0.2.9] — 2026-08-10

### Added / Improved

- **Phase 7.3 Screening Configuration GUI**: Added project-scoped GUI for configuring screening criteria based on real Phase 7.2 REST API endpoints (`/projects/{project_id}/screening/criteria`).
- Added `ScreeningCriterionCard` component rendering criterion metadata (display order `#N`, name, description, Inclusion/Exclusion badges, stage badges, required/optional status, active/inactive state) and action buttons (`Edytuj`, `Dezaktywuj`, `Aktywuj`).
- Added `ScreeningCriterionModal` component supporting Create & Edit modes with form validation (empty name, negative display order), explicit `is_active: true` payload on creation without active toggle, and configurable active/inactive state on edit.
- Added `ScreeningCriteriaList` component handling loading (`LoadingSpinner`), error alert with retry button (`ErrorAlert`), empty state (`EmptyState` with info banner and action), and deterministic list rendering.
- Updated `ScreeningPage` to integrate criteria management GUI connected to `projectApiService` (`listScreeningCriteria`, `createScreeningCriterion`, `updateScreeningCriterion`, `deactivateScreeningCriterion`).
- Added 22 frontend unit and integration tests in `frontend/tests/ScreeningCriteria.test.tsx`.

## [0.2.8] — 2026-08-10

### Added

- **Phase 7.2 Screening Criteria Persistence and API**: Added durable SQLite storage (`screening_criteria` table in `migrations/0007_screening_criteria.sql`) and `SqliteScreeningCriterionRepository` for project-scoped screening criteria.
- Added `ScreeningCriterionRepository` abstract protocol decorated with `@runtime_checkable` and `CriterionNotFoundError` exception.
- Added project-scoped REST API endpoints (`/projects/{project_id}/screening/criteria`) supporting `POST` (create), `GET` (list and single item), `PUT` (update), and `PATCH /deactivate` (soft lifecycle).
- Added DTO models (`ScreeningCriterionCreateRequest`, `ScreeningCriterionUpdateRequest`, `ScreeningCriterionResponse`, `ScreeningCriterionListResponse`).
- Enforced strict project isolation across repository and API operations.
- Added 34 unit tests covering SQLite persistence, deterministic display ordering (`ORDER BY display_order ASC, criterion_id ASC`), Enum/Bool round-trips, and cross-project isolation.

## [0.2.7] — 2026-08-10

### Added

- **Phase 7.1 Screening Criteria Domain Model**: Added infrastructure-independent `ScreeningCriterion` domain model (`criterion_id: UUID`, `project_id: str`, `name`, `description`, `criterion_type: ScreeningCriterionType`, `screening_stage: ScreeningCriterionStage`, `display_order`, `is_active`, `is_required`).
- Added `ScreeningCriterionType` (`INCLUSION`, `EXCLUSION`) and `ScreeningCriterionStage` (`TITLE_ABSTRACT`, `FULL_TEXT`, `BOTH`).
- Preserved existing `ScreeningStage` (`TITLE_ABSTRACT`, `FULL_TEXT`) for concrete `ScreeningDecision` events.
- Added validation rules for non-blank text fields, non-negative display order, text normalization, and deterministic JSON serialization.
- Added 21 unit tests in `tests/unit/domain/test_screening.py`.

## [0.2.6] — 2026-08-10

### Added / Improved

- Added `app.rendering` package with `QueryRenderer` protocol and `RenderedQuery` value object supporting provider-specific physical queries, lossy/lossless tracking (`is_lossless`), and audit warnings (`warnings`).
- Added `OpenAlexQueryRenderer` converting canonical `SearchQuery` expressions to OpenAlex `search` string syntax with exact phrase quotes `"..."`, uppercase Boolean operators (`AND`, `OR`, `NOT`), and nested grouping `()`.
- Added `CrossrefQueryRenderer` converting canonical `SearchQuery` expressions to Crossref free-text keyword syntax with phrase quotes `"..."`, space-separated terms, lossy tracking (`is_lossless=False`), and audit warnings for unsupported `NOT` / `OR` operators.
- Integrated query rendering into `SearchEngine.execute()`, ensuring `SearchRun.rendered_query`, `ProvenanceEntry.rendered_query`, and raw response archive entries record the exact physical query executed per provider.
- Extended REST API `POST /projects/{project_id}/search-strategy/executions` response DTO (`SearchStrategyExecutionResponse`) with `provider_queries`.
- Updated frontend types and `SearchResultsSection` UI to present physical provider queries alongside canonical query preview.

## [0.2.5] — 2026-08-06

### Improved

- Added CLI integrity check entrypoint (`app/tools/integrity.py`) runnable via `python -m app.tools.integrity PROJECT_ID`.
- Added `--json` output format and custom `--db-path` options to CLI tool.
- Mapped integrity audit status to standard CLI exit codes (`0` for OK/WARNING, `1` for ERROR, `2` for argument errors).
- Added CLI unit and integration test suites (`tests/unit/tools/test_cli_integrity.py` and `tests/integration/tools/test_cli_integrity_integration.py`).
- Standardized domain object factories (`make_publication`, `make_author`, `make_import_history`, `make_normalization_execution`, `make_duplicate_decision`) in `tests/fixtures/factories.py`.
- Added standard project fixtures (`empty_project`, `project_100`, `project_duplicates`, `project_normalized`) in `tests/fixtures/project_fixtures.py`.
- Refactored `test_integrity_audit_service.py` to use test factories and eliminated redundant mock helpers.
- Added fixture test suite (`tests/unit/test_fixtures.py`).
- Clarified abstract `Protocol` contracts for all repository interfaces (`ProjectPublicationRepository`, `ImportHistoryRepository`, `NormalizationExecutionRepository`, `DuplicateReviewDecisionRepository`, `SearchStrategyRepository`).
- Added `@runtime_checkable` decorators to repository protocols for runtime type verification.
- Isolated driver-specific `sqlite3` types from abstract `Protocol` interfaces to ensure vendor independence.
- Preserved transactional connection parameters in SQLite repository implementations to maintain atomic multi-repository transactions.
- Completed SQLite constraints architecture audit for foreign keys, CHECK constraints, and query indexes (`docs/SQLITE_CONSTRAINTS_REVIEW.md`). Status: `ARCHITECTURE COMPLETED — IMPLEMENTATION DEFERRED`.
- Added repository contract test suite (`tests/unit/repositories/test_repository_contracts.py`).

## [0.2.4] — 2026-08-04

### Added / Improved

- Added the explicit `Uruchom deduplikację` action using the existing duplicate-groups request.
- Added a last-run deduplication report with status, Working Collection input size, analyzed publication count, candidate-group count, client-measured duration and completion time.
- Separated the execution report from the candidate-group review summary.
- Added distinct pre-run, running, success, empty-result and error states for deduplication.
- Added one explicitly labelled historical OpenAlex import-history backfill for 391 publications that predated correct history recording.

### Fixed

- Repaired the historical `lean_energy` project data and removed the single synthetic Crossref test publication together with its import-history entry.
- Reconciled Working Collection, Sources & Imports and Normalization at 535 OpenAlex publications for `lean_energy`.
- Corrected the zero-group review state so it is neutral and is not presented as completed human review.
- Removed redundant zero-group execution copy already represented by the deduplication metrics.
- Removed hardcoded application-version text from the durable duplicate-decision notice.
- Clarified that the total review counter represents detected candidate groups.

### Scope limits

- APPROVE and REJECT decisions remain durable, but APPROVE does not physically merge publications.
- No screening implementation, deduplication algorithm change or new backend endpoint is included.

## [0.2.3] — 2026-08-03

### Added / Improved

- Functional Project Dashboard based on real stage 1–4 data.
- Real loading, empty, partial-data and partial-failure states on the Dashboard.
- Responsive Dashboard card layout.
- Shared next-action derivation used by the Dashboard workflow UI.
- Ability to create and save the first Search Strategy from its empty state.
- OpenAlex and Crossref selection independent of the technical provider `connected` field; Semantic Scholar remains unavailable.
- Accumulated OpenAlex record aggregation on Sources & Imports.
- Individual import-history entries remain visible below the provider aggregate.

### Fixed

- Removed static and demonstration values from the Project Dashboard.
- Restored provider selection when the project has no saved Search Strategy.
- Removed false green provider connection states when no import data exists.
- Prevented Sources data from being incorrectly reset or overwritten.
- Preserved meaningful numeric zero values instead of rendering them as missing data.
- Fixed the regression where the OpenAlex card used only the newest import-history entry instead of the accumulated successful import state.
- Preserved `projectId` when navigating between workflow stages.

### Scope limits

- OpenAlex is the manually verified provider for the current end-to-end workflow. Crossref remains selectable but is not declared fully verified end to end.
- Semantic Scholar and workflow stages 5–8 remain unavailable.
- No normalization or deduplication behavior changed; the Dashboard only reads their existing statuses.

## [0.2.2] — 2026-07-31

### Added

- `WorkflowNavigationStatus` single source of truth in `ProjectContext` for stages 1–8.
- Parallel `Promise.allSettled` status fetch (`refreshWorkflowStatus`) for backend project endpoints:
  1. `GET /projects/{project_id}/search-strategy`
  2. `GET /projects/{project_id}/imports`
  3. `GET /projects/{project_id}/normalization`
  4. `GET /projects/{project_id}/duplicate-groups`
- Dynamic navigation badges in `Sidebar` and `WorkflowStepper` using real backend operational metrics.
- Route parameter synchronization (`projectId`) in `AppShell` with clean race-condition prevention.
- Instant state synchronization after duplicate review decisions (`APPROVE`, `REJECT`) with 1 POST and 0 extra GET requests.
- Stage 5–8 navigation items strictly rendered with neutral `not_available` ("Niedostępne") status.

### Scope limits

- No physical publication merging, screening persistence, quality assessment persistence, data extraction, background jobs, or WebSockets.

## [0.2.1] — Unreleased

### Added

- Durable SQLite storage for duplicate review decisions (`SqliteDuplicateReviewDecisionRepository`)
  with schema migration `0006_duplicate_review_decisions.sql`.
- Human duplicate decisions (`APPROVE`, `REJECT`) and optional rationale text
  persist across backend restarts and page reloads.
- Verified deterministic `group_id` generation for identical publication groups
  independent of input ordering, SQLite re-reads, unrelated publication additions, or normalization executions.
- `GET /projects/{project_id}/duplicate-groups` now returns decision status and rationale for every group, eliminating N+1 decision requests per card on page load.
- Frontend state for duplicate candidate groups is unified at `DeduplicationPage` level with immediate status and dynamic summary updates.
- Real deduplication summary metrics (Total, Pending, Approve, Reject) calculated directly from backend duplicate group responses.
- Clarified UI messages explaining that APPROVE confirms matching publications, REJECT confirms distinct publications, decisions are stored in SQLite, and physical publication merging remains deferred to a future release.

### Scope limits

- Physical publication merging, record deletion, `PublicationMergePolicy` execution,
  and candidate publication status mutation are not part of 0.2.1.

## [0.2.0] — Unreleased

### Added

- Durable SQLite storage for the latest project-scoped normalization execution,
  including summary fields, timestamps, rules and audit trail.
- Normalization results are restored by `GET /projects/{project_id}/normalization`
  after backend restart.

### Scope limits

- This release does not add ISSN validation, full provenance, multi-run history,
  background jobs, deduplication or screening.

## [0.1.9] — Unreleased

### Added

- First working project-scoped bibliographic upload for one `.ris` or `.bib`
  file via `POST /projects/{project_id}/imports`.
- Reuse of the existing RIS and BibTeX parsers, mappers and `Publication`
  repository path.
- Upload response with `import_id`, `records_count`, `warnings` and `status`.
- Real frontend file selection, upload feedback and visible session history
  update after a successful import.
- Durable SQLite import history with newest-first
  `GET /projects/{project_id}/imports` and project isolation.
- Selected OpenAlex result imports now create durable provider history records
  with the rendered query, imported count and available total; Sources shows
  the latest successful OpenAlex import and combines file/provider history.
- Added project-scoped normalization `POST`/`GET` endpoints reusing the existing
  publication normalizers, with live summary counts and audit entries in the
  Normalization screen.

### Scope limits

- Crossref/Semantic Scholar provider status, background jobs, mass import and
  the complete Sources module
- Durable normalization execution history and ISSN validation
  are not part of 0.1.9.

## [0.1.8] — Unreleased

### Search Strategy

- Restored production UI.
- Restored backend persistence.
- Restored live search execution.
- Removed navigation to Sources after Search.
- Restored live OpenAlex results.
- Restored import workflow.
- Added cursor pagination for Search Strategy results, including append-only
  loading, duplicate protection, retryable page errors, and total/loaded
  counts. Full automatic retrieval/import of all result pages is not included.

### Added

- Phase 6.8 End-to-End Literature Search Workflow product direction.
- Durable, project-scoped Search Strategy model and SQLite repository.
- Versioned Search Query persistence with complete Boolean expression trees.
- SQLite schema migration for search strategies.
- REST `GET` and `PUT` Search Strategy endpoints.
- Validation for research questions, concept groups, terms, constraints,
  publication years, languages, publication types, and provider selection.
- Full Search Strategy GUI editing against the persistent GET/PUT API.
- Generic live Boolean preview and explicit loading, dirty, saving, saved,
  validation, missing-strategy, and error states.

### Changed

- Product priority now moves from mock-driven GUI expansion to the complete
  Search Strategy and Sources Ingestion workflow.
- Backend application version is read from the root `VERSION` source of truth.
- Search Strategy no longer uses project mock data as its strategy source.
- The former Repeat/Execute controls are replaced by Save and `Szukaj`;
  `Szukaj` persists and executes the current strategy while keeping results on
  the Search Strategy page.

## [0.1.7]

### Added

- **Live Search Providers & Import (Phase 6.7.2b)**: Connected the Search
  Strategy execution endpoint to the existing OpenAlex and Crossref providers
  through `SearchEngine`.
- Partial provider failure reporting while preserving results returned by
  healthy providers.
- Provider and source-record attribution in the common search-result contract.
- Import of explicitly selected search records into the project's in-memory
  Working Collection, with refreshed collection count and cleared selection.
- Deterministic UUID5 result identifiers scoped by provider and source record.
- Idempotent source-record import scoped by project, provider, and `source_id`,
  reporting `imported_count`, `skipped_count`, and `total_requested`.

The demonstrator Working Collection is stored only in backend process memory
and does not survive a server restart.

## [0.1.6] — Unreleased

### Added

- **Search Results Workflow (Phase 6.7.2a)**: Deterministic controlled search
  result responses, project-scoped result state, result cards, record selection,
  select-all behavior, and initial/loading/success/empty/error states.
- Formal split of Phase 6.7.2 into Search Results Workflow (6.7.2a) and the
  separately planned Live Search Providers & Import increment (6.7.2b).

## [0.1.5] — Unreleased

### Added

- **Functional Search Strategy (Phase 6.7.1)**: Editable year limits, supported
  provider selection, complete concept-group and term editing, client UX
  validation, backend-authoritative validation, and explicit Execute/Repeat
  semantics backed by runtime application state.
- **Search Strategy API**: Added the stateless Module 1 execution-validation
  endpoint `POST /projects/{project_id}/search-strategy/executions`.

## [0.1.4] — Unreleased

### Added
- **Backend Contract Tests**: Added `tests/contract/api/test_deduplication_contract.py` verifying full JSON response schemas, nullable fields, `extra="forbid"` compliance, and OpenAPI v3 specification.
- **Full Duplicate Review Workflow Integration**: Added `tests/integration/api/test_deduplication_workflow_integration.py` testing complete GET -> POST APPROVE -> GET -> POST REJECT -> GET lifecycle, decision overwriting, and project isolation.
- **Frontend Integration & Regression Suite**: Added `frontend/tests/DeduplicationIntegration.test.tsx` verifying interactive user workflow, toggle `aria-expanded` attributes, rationale entry, saving/saved feedback states, network failure recovery (Retry), and null field safety.
- **OpenAPI & Types Parity Verification**: Automated schema checking for FastAPI OpenAPI `maxLength: 1000` constraints and static reflection matching Python DTO fields with TypeScript frontend interfaces in `frontend/src/types/index.ts`.
- **Determinism Verification**: Added backend & frontend determinism tests confirming stable ordering and idempotent response evaluation across repeated calls.
- **Documentation Reconciliation**: Resolved roadmap inconsistency in `ROADMAP.md` to align Phase 6.6 as Integration and Contract Tests and marked Phase 6 as complete. Added `docs/DUPLICATE_REVIEW_TESTING.md`.

## [0.1.3] — Unreleased

### Added

- **Duplicate Comparison & Review UI (Phase 6.5)**:
  - Detailed side-by-side comparison view for candidate duplicate group records.
  - Deterministic field matching and difference indicators across title, authors, year, venue, identifiers (DOI, PMID, OpenAlex), and provenance.
  - Provenance details display per publication record.
  - Optional decision rationale support (`rationale`) with trimming and length validation (max 1000 characters).
  - Accessibility enhancements with `aria-expanded` and clear text/badge state indicators.

## [0.1.2] — 2026-07-29

### Added

- In-memory duplicate review decision repository (`InMemoryDuplicateReviewDecisionRepository`) with `(project_id, group_id)` composite key isolation.
- REST endpoints for recording (`POST`) and fetching (`GET`) duplicate review decisions (`APPROVE` / `REJECT`).
- Strict typing with `DuplicateDecisionType` and `DuplicateDecisionStatus` enums.
- Interactive decision controls in duplicate review GUI (Approve, Reject, Saving, Saved, Error, Retry, Status Badges).

## [0.1.1] — 2026-07-29

### Added

- Read-only API for identifier-linked duplicate candidate groups.
- Frontend integration of the duplicate review view with backend-provided data.
- Loading, empty and error states for duplicate review data.

## [0.1.0] — 2026-07-29

### Added

- Application-wide version source in the root VERSION file.
- Build-time application version available in the React frontend.
- Application version displayed in the GUI.
- About view with release identity and runtime mode.
- Versioning policy documentation.
