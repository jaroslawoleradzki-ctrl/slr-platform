# Changelog

## [0.1.2] — Unreleased

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
