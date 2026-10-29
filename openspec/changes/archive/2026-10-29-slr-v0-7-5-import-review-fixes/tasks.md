# Tasks

## 1. Frontend regression tests

- [x] 1.1 Add failing tests proving that a successful accept closes the dialog even when `onChanged` never resolves; verify with `npm --prefix frontend test -- ImportWarningResolution.test.tsx`.
- [x] 1.2 Add failing tests proving that a successful reject closes the dialog without waiting for `onChanged`; verify with `npm --prefix frontend test -- ImportWarningResolution.test.tsx`.
- [x] 1.3 Add failing tests for per-action loading: accept shows a spinner only on `Akceptuję`, reject shows a spinner only on `Potwierdź odrzucenie`, both decision triggers are disabled while pending, and `Zamknij` is available after the request settles; verify with `npm --prefix frontend test -- ImportWarningResolution.test.tsx`.
- [x] 1.4 Add failing tests proving that a failed decision keeps the dialog open with its error/blockers, while a failed post-decision refresh does not reopen the dialog or report the decision as failed; verify with `npm --prefix frontend test -- ImportWarningResolution.test.tsx`.
- [x] 1.5 Add a failing test proving that repeated activation of the same decision submits one POST; verify with `npm --prefix frontend test -- ImportWarningResolution.test.tsx`.
- [x] 1.6 Add a failing Sources page test proving that a summary refresh failure after a decision renders an error and retry action even when an older summary exists; verify with `npm --prefix frontend test -- SourcesIngestionRefresh.test.tsx`.

## 2. Decision dialog implementation

- [x] 2.1 Update `ImportReviewModal` to consume the decision response, set the terminal effective/review state, notify the parent through `onDecisionApplied`, and close immediately after a successful POST; verify `npm --prefix frontend test -- ImportWarningResolution.test.tsx`.
- [x] 2.2 Replace the shared `saving` flag with a per-action pending state and apply loading/disabled behavior to the accept, reject, confirmation, and close controls; verify `npm --prefix frontend test -- ImportWarningResolution.test.tsx`.
- [x] 2.3 Separate decision-request errors from refresh errors so a refresh failure cannot be rendered as an acceptance or rejection failure; verify `npm --prefix frontend test -- ImportWarningResolution.test.tsx`.
- [x] 2.4 Ensure rapid repeat activation cannot issue a second decision POST; verify `npm --prefix frontend test -- ImportWarningResolution.test.tsx`.

## 3. Sources refresh implementation

- [x] 3.1 Update `FileDropzone.onChanged` to start the Sources summary and workflow-status refreshes concurrently without blocking dialog close, and wire the decision result to the parent for immediate row update; verify `npm --prefix frontend test -- ImportWarningResolution.test.tsx`.
- [x] 3.2 Update `SourcesIngestionPage` to render a visible summary-refresh error and retry action when stale data exists; verify `npm --prefix frontend test -- SourcesIngestionRefresh.test.tsx`.
- [x] 3.3 Confirm that a successful summary refresh updates the active import row to `Zaimportowano` and leaves the visible import/record counts and working-collection total unchanged; verify `npm --prefix frontend test -- SourcesIngestionRefresh.test.tsx`.
- [x] 3.4 Run the frontend type and build gates with `npm --prefix frontend run type-check` and `npm --prefix frontend run build`.

## 4. Counter and research-integrity regression

- [x] 4.1 Add a failing service test asserting that `sources-summary` after acceptance reports one more successful import and one fewer warning import for the source while `records_added_count` and the working-collection total stay unchanged; verify with `bash scripts/agent/safe_pytest.sh tests/unit/services/test_sources_summary_service.py`.
- [x] 4.2 Add a failing service test asserting that acceptance leaves publications, source records, skip-audit rows, duplicate decisions, screening decisions, and PRISMA stage populations unchanged; verify with `bash scripts/agent/safe_pytest.sh tests/unit/services/test_import_review_service.py`.
- [x] 4.3 Add a failing API assertion that the accept response returns `effective_status="success"` and `review_status="accepted"` and that a repeated accept is idempotent; verify with `bash scripts/agent/safe_pytest.sh tests/unit/api/test_import_review_api.py`.
- [x] 4.4 Add an integration assertion that the workflow Sources stage no longer reports a warning after acceptance while PRISMA populations remain unchanged; verify with `bash scripts/agent/safe_pytest.sh tests/integration/test_v074_import_review_integration.py`.

## 5. Documentation

- [x] 5.1 Update `docs/GUI_FOUNDATION.md` to describe decision-before-refresh completion, per-action pending feedback, and the distinction between decision and refresh errors; verify the documented behavior matches the frontend tests.
- [x] 5.2 Update `docs/SOURCES_IMPORTS_AUDIT.md` to state that acceptance changes only the effective status and warning-derived counts, not working-collection, canonical, source-record, or PRISMA counts; verify the documented invariants match the backend tests.

## 6. Validation and report

- [x] 6.1 Run `npm --prefix frontend test`, `npm --prefix frontend run type-check`, and `npm --prefix frontend run build`; record the results.
- [x] 6.2 Run `bash scripts/agent/safe_pytest.sh tests/unit/services/test_import_review_service.py tests/unit/services/test_sources_summary_service.py tests/unit/api/test_import_review_api.py tests/integration/test_v074_import_review_integration.py`; record the results.
- [x] 6.3 Run `uv run --frozen --no-sync ruff check app tests scripts` and `uv run --frozen --no-sync mypy app`; record the results.
- [x] 6.4 Run `openspec validate slr-v0-7-5-import-review-fixes --strict` and `openspec validate --all --strict`; record the results.
- [x] 6.5 Finalize the v0.7.5 implementation report with red/green evidence, the counter invariant, residual risk, and any `NOT VERIFIED` gate. Do not claim manual browser verification without evidence.

## Workflow follow-up

- Run the research-integrity review gate before merge.
- Do not merge, release, deploy, or archive this change without explicit human authorization.

## Remediation of research-integrity review LOW findings

- [x] LOW-1: strengthened downstream snapshot test with non-empty screening/QA/extraction/synthesis rows.
- [x] LOW-2: verified per-source counters are server-derived and update on successful refresh; no PRISMA change.
- [x] LOW-3: browser E2E via Playwright (Chromium), 3/3 PASS (`frontend/e2e/import-review.spec.ts`).
