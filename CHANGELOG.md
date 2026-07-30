# Changelog

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
