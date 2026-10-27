# Tasks

## 1. Duplicate-readiness regression tests

- [x] 1.1 Add a failing unit test proving that deduplication and screening build different groups after a merge followed by a new matching import; verify with `bash scripts/agent/safe_pytest.sh tests/unit/services/test_duplicate_readiness_consistency.py`.
- [x] 1.2 Add failing tests for pending review, approved-unmerged, rejected, merged, stale-decision, and no-candidate states; verify all fail for the expected reason with `bash scripts/agent/safe_pytest.sh tests/unit/services/test_duplicate_readiness_consistency.py`.
- [x] 1.3 Record the red-test evidence and planned contract in `docs/reviews/V074_IMPORT_AND_WORKFLOW_CONSISTENCY_REPORT.md`; verify the report names the failing command and observed failure.

## 2. Shared duplicate-readiness implementation

- [x] 2.1 Implement one duplicate-readiness projection over active canonical publications and persisted decisions/merges; verify `bash scripts/agent/safe_pytest.sh tests/unit/services/test_duplicate_readiness_consistency.py`.
- [x] 2.2 Add an integration test that a merged group followed by a new matching import yields one pending group in both deduplication and screening; verify `bash scripts/agent/safe_pytest.sh tests/integration/test_v074_workflow_consistency.py`.
- [x] 2.3 Change screening input grouping to use the active corpus and the shared projection; verify `bash scripts/agent/safe_pytest.sh tests/unit/services/test_screening_input_service.py tests/unit/services/test_title_abstract_screening_service.py`.
- [x] 2.4 Update duplicate-group and workflow-status DTOs with additive readiness fields; verify with `bash scripts/agent/safe_pytest.sh tests/unit/api/test_title_abstract_screening_api.py tests/unit/api/test_workflow_status_deduplication_api.py`.
- [x] 2.5 Update PRISMA metrics and exports to use the same readiness projection, including separate pending and awaiting-merge counts; verify `bash scripts/agent/safe_pytest.sh tests/unit/api/test_prisma_metrics_api.py tests/unit/services/test_prisma_accounting_adversarial_wp3.py tests/unit/services/test_xlsx_workbook.py`.
- [x] 2.6 Update `docs/DUPLICATE_REVIEW_DECISIONS.md`, `docs/DUPLICATE_REVIEW_API.md`, and `docs/EXPORTS_PRISMA.md` with the active-corpus grouping rule and readiness states; verify the documented states match the implemented DTO fields.

## 3. Duplicate-readiness UI

- [x] 3.1 Add failing frontend tests for pending, merge-required, rejected, and ready deduplication states and distinct screening explanations; verify `npm --prefix frontend test -- DeduplicationScreeningConsistency.test.tsx`.
- [x] 3.2 Replace frontend-derived deduplication completion with backend readiness data; verify the new frontend tests pass with `npm --prefix frontend test -- DeduplicationScreeningConsistency.test.tsx`.
- [x] 3.3 Update the deduplication summary and stage labels to show review and merge-required counts without marking the stage completed; verify `npm --prefix frontend run type-check` and `npm --prefix frontend test`.
- [x] 3.4 Update title/abstract and full-text screening messages to distinguish `unresolved_duplicates` from `unmerged_duplicates`; verify `npm --prefix frontend test -- DeduplicationScreeningConsistency.test.tsx`.
- [x] 3.5 Document the user-visible readiness states in `docs/DUPLICATE_COMPARISON_UI.md`; verify the documented labels match the tested UI text.

## 4. Import review migration and repository

- [x] 4.1 Add failing migration tests for `0038_import_review_decisions.sql`, including upgrade from the v0.7.3 schema, unique project/import decisions, and integrity checks; verify `bash scripts/agent/safe_pytest.sh tests/unit/repositories tests/integration -k "migration or import_review"`.
- [x] 4.2 Add the additive `0038_import_review_decisions.sql` migration without editing migrations `0034`–`0037`; verify `bash scripts/agent/safe_pytest.sh tests/unit/repositories tests/integration -k "migration or import_review"`.
- [x] 4.3 Add failing repository tests for creating, reading, listing active/rejected imports, and idempotent decisions; verify `bash scripts/agent/safe_pytest.sh tests/unit/repositories/test_import_review_repository.py`.
- [x] 4.4 Implement the import-review repository and effective-status projection; verify `bash scripts/agent/safe_pytest.sh tests/unit/repositories/test_import_review_repository.py`.
- [x] 4.5 Update `docs/data-model.md` and `docs/SOURCES_IMPORTS_AUDIT.md` with the decision table, effective status, and non-active audit behavior; verify the documented columns match the migration.

## 5. Import acceptance service

- [x] 5.1 Add failing service tests proving acceptance records one decision, changes effective status to `Zaimportowano`, preserves publications and research decisions, and is idempotent; verify `bash scripts/agent/safe_pytest.sh tests/unit/services/test_import_review_service.py`.
- [x] 5.2 Implement acceptance with reviewer attribution, warning snapshot, and audit data; verify acceptance tests pass with `bash scripts/agent/safe_pytest.sh tests/unit/services/test_import_review_service.py`.
- [x] 5.3 Add a regression test proving acceptance does not change duplicate decisions, screening decisions, QA, extraction, synthesis, or PRISMA populations; verify `bash scripts/agent/safe_pytest.sh tests/unit/services/test_import_review_service.py`.
- [x] 5.4 Update `docs/SOURCES_IMPORTS_AUDIT.md` with acceptance semantics; verify the documented behavior matches the acceptance tests.

## 6. Import rejection safety and transaction

- [x] 6.1 Add failing tests for rejecting an unshared, unmerged import with no downstream records; verify the expected successful deletion in `bash scripts/agent/safe_pytest.sh tests/unit/services/test_import_review_rejection.py`.
- [x] 6.2 Add failing blocker tests for shared canonical publications, merged/superseded records, duplicate decisions, pre-screening decisions/archive, corpus finalization, screening decisions, full-text metadata, quality assessments, extraction, synthesis, and unverifiable legacy ownership; verify each blocker with `bash scripts/agent/safe_pytest.sh tests/unit/services/test_import_review_rejection.py`.
- [x] 6.3 Add failing transaction tests for a failure after publication deletion and for repeated rejection idempotency; verify `bash scripts/agent/safe_pytest.sh tests/unit/services/test_import_review_rejection.py`.
- [x] 6.4 Implement transactional rejection with combined blocker reporting, non-cascading deletion, normalization invalidation, and duplicate-state reconciliation; verify all rejection tests with `bash scripts/agent/safe_pytest.sh tests/unit/services/test_import_review_rejection.py`.
- [x] 6.5 Add rejected-import filtering tests for active history, source summaries, working collection, and active corpus; verify `bash scripts/agent/safe_pytest.sh tests/unit/services/test_sources_summary_service.py tests/unit/services/test_import_review_rejection.py`.
- [x] 6.6 Update `docs/SOURCES_IMPORTS_AUDIT.md`, `docs/data-model.md`, and `docs/DATA_INTEGRITY_CLEANUP.md` with blockers, transaction order, retained audit, and manual recovery limits; verify the documented blockers match the service tests.

## 7. PRISMA rejected-import accounting

- [x] 7.1 Add failing PRISMA tests for `removed before screening — rejected import`, including repeated source occurrences and stage reconciliation; verify `bash scripts/agent/safe_pytest.sh tests/unit/api/test_prisma_metrics_api.py tests/unit/services/test_prisma_accounting_adversarial_wp3.py`.
- [x] 7.2 Implement rejected-import identification retention and the distinct removal count; verify the PRISMA tests pass with `bash scripts/agent/safe_pytest.sh tests/unit/api/test_prisma_metrics_api.py tests/unit/services/test_prisma_accounting_adversarial_wp3.py`.
- [x] 7.3 Update PRISMA XLSX/PDF/SVG and export tests for the new removal category; verify `bash scripts/agent/safe_pytest.sh tests/unit/services/test_prisma_flow_and_svg.py tests/unit/services/test_prisma_pdf.py tests/unit/services/test_xlsx_workbook.py`.
- [x] 7.4 Update `docs/EXPORTS_PRISMA.md` with the rejected-import category and reconciliation rule; verify the documented fields match the PRISMA DTO and export tests.

## 8. Import review API

- [x] 8.1 Add failing API tests for `GET /imports/{import_id}/review`, accept, reject, confirmed rejection, missing confirmation, conflicting decisions, blocked rejection, and cross-project access; verify `bash scripts/agent/safe_pytest.sh tests/unit/api/test_import_review_api.py`.
- [x] 8.2 Implement the review detail and decision endpoints with explicit 404/409/422 responses and structured blockers; verify `bash scripts/agent/safe_pytest.sh tests/unit/api/test_import_review_api.py`.
- [x] 8.3 Add backward-compatibility tests for existing import history and sources-summary fields, including `include_rejected`; verify `bash scripts/agent/safe_pytest.sh tests/unit/api/test_sources_summary_api.py tests/unit/api/test_import_review_api.py`.
- [x] 8.4 Document the endpoints, request/response fields, and error codes in `docs/SOURCES_IMPORTS_AUDIT.md` and `docs/DUPLICATE_REVIEW_API.md` where the readiness fields are exposed; verify the documented contracts match the API tests.

## 9. Import warning frontend

- [x] 9.1 Add failing frontend tests for opening warning details, accepting, cancelling rejection, confirming rejection, and displaying blocked-rejection explanations; verify `npm --prefix frontend test -- ImportWarningResolution.test.tsx`.
- [x] 9.2 Implement the accessible warning detail dialog and accept action with server-confirmed refresh; verify `npm --prefix frontend test -- ImportWarningResolution.test.tsx`.
- [x] 9.3 Implement the rejection confirmation dialog with the approved Polish text and no request on cancel; verify `npm --prefix frontend test -- ImportWarningResolution.test.tsx`.
- [x] 9.4 Ensure rejected imports disappear from active history only after a successful response, and blocked imports remain visible with their explanation; verify `npm --prefix frontend test -- ImportWarningResolution.test.tsx`.
- [x] 9.5 Document the decision and confirmation flow in `docs/GUI_FOUNDATION.md` and `docs/SOURCES_IMPORTS_AUDIT.md`; verify the documented text matches the frontend tests.

## 10. Integration and regression

- [x] 10.1 Add an end-to-end integration test covering warning import, acceptance, rejection, shared-publication blocking, and downstream blocker handling; verify `bash scripts/agent/safe_pytest.sh tests/integration/test_v074_import_review_integration.py`.
- [x] 10.2 Add a cross-feature test covering import rejection followed by duplicate readiness, screening readiness, PRISMA, and export counts; verify `bash scripts/agent/safe_pytest.sh tests/integration/test_v074_workflow_consistency.py`.
- [x] 10.3 Run migration-focused tests and migration safety with `bash scripts/agent/safe_pytest.sh tests/unit/repositories tests/integration -k "migration or reconciliation"` and `uv run --frozen --no-sync python scripts/ci/check_migration_safety.py --base-ref origin/development`; record results.
- [x] 10.4 Run backend gates with `uv run --frozen --no-sync ruff check app tests scripts`, `uv run --frozen --no-sync mypy app`, and `uv run --frozen --no-sync pytest -q -p no:cacheprovider`; record results.
- [x] 10.5 Run frontend gates with `npm --prefix frontend run type-check`, `npm --prefix frontend test`, and `npm --prefix frontend run build`; record results.
- [x] 10.6 Run `python3 scripts/agent/safe_git_inspect.py diff --check`; record the result without claiming CI.
- [x] 10.7 Finalize `docs/reviews/V074_IMPORT_AND_WORKFLOW_CONSISTENCY_REPORT.md` with red/green evidence, integrity findings, residual risk, and any `NOT VERIFIED` gate.

## 11. Release metadata and documentation

- [x] 11.1 Update `VERSION`, `pyproject.toml`, `frontend/package.json`, and version tests for v0.7.4 only when release preparation is authorized; verify `uv run --frozen --no-sync pytest -q tests/unit/test_versioning.py` and `npm --prefix frontend test -- Versioning.test.tsx`.
- [x] 11.2 Add the v0.7.4 entry to `CHANGELOG.md` describing both features, the PRISMA treatment, and known limitations; verify the entry matches the implemented behavior and approved scope.
- [x] 11.3 Update `docs/PROJECT_STATUS.md`, `docs/ROADMAP.md`, or the relevant workflow documentation only where behavior changed; verify links and commands are valid.

## Workflow follow-up

- Run `openspec validate slr-v0-7-4-import-and-workflow-consistency --strict` and `openspec validate --all --strict` after implementation.
- Run the research-integrity review gate before merge.
- Do not merge, release, or deploy without explicit human authorization.
- Archive the OpenSpec change only after all tasks, the implementation report, and validation evidence are complete.
