# Changelog

## [Unreleased]

### Improved

- Standardized domain object factories (`make_publication`, `make_author`, `make_import_history`, `make_normalization_execution`, `make_duplicate_decision`) in `tests/fixtures/factories.py`.
- Added standard project fixtures (`empty_project`, `project_100`, `project_duplicates`, `project_normalized`) in `tests/fixtures/project_fixtures.py`.
- Refactored `test_integrity_audit_service.py` to use test factories and eliminated redundant mock helpers.
- Added fixture test suite (`tests/unit/test_fixtures.py`).
- Clarified abstract `Protocol` contracts for all repository interfaces (`ProjectPublicationRepository`, `ImportHistoryRepository`, `NormalizationExecutionRepository`, `DuplicateReviewDecisionRepository`, `SearchStrategyRepository`).
- Added `@runtime_checkable` decorators to repository protocols for runtime type verification.
- Isolated driver-specific `sqlite3` types from abstract `Protocol` interfaces to ensure vendor independence.
- Preserved transactional connection parameters in SQLite repository implementations to maintain atomic multi-repository transactions.
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
