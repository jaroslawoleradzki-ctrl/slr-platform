# Proposal

## Why

`GET /projects/{project_id}/duplicate-groups` currently recomputes groups and also clears/updates `duplicate_candidate_group_id` and inserts snapshots. This makes a read mutate SQLite and obscures the source and cost of first-load failures, whose runtime cause and endpoint latency have not yet been measured.

This HIGH-risk change (deduplication, screening, PRISMA, provenance, and audit-adjacent behavior) separates read behavior from explicit writes, instruments the actual request path, and only selects a performance remedy after collecting runtime evidence. The user has approved refreshing source-record group IDs at publication-set mutation boundaries. Normalization can use the existing SQLite transaction manager by passing its shared connection through normalization, execution-summary persistence, and duplicate-group projection; implementation must verify rollback and measure the resulting write-lock duration. Human approval of this proposal is still required before Apply.

## What Changes

- Make duplicate-groups GET return the same backend-derived groups/readiness without changing research records or writing group snapshots.
- Refresh `duplicate_candidate_group_id` and materialize immutable membership snapshots when an operation changes the active publication/group set, in the same transaction as that mutation.
- Make the normalization endpoint participate in that same atomic boundary for active-corpus reads, normalized publication writes, normalization summary, group projection, and snapshot writes.
- Preserve existing snapshot rows, schema, uniqueness, payload meaning, and first-write immutability. Use persisted reviewer-decision records with snapshot membership in the import-review safety fallback; do not rewrite decision or snapshot history.
- Preserve the duplicate algorithm, deterministic group identifiers, response fields, existing reviewer decisions, merge history, screening readiness, and PRISMA accounting.
- Add runtime measurements for endpoint stages and UI first-visible-load/render time, including latency percentiles and failure counts, without recording publication content or identifiers.
- Add backend integration and browser E2E coverage for read-only behavior, first load, concurrent reads/import interaction, decisions, and UI loading/success/error states.
- Require baseline runtime diagnostics before selecting any performance remedy. Timeout changes, retries, asynchronous jobs, or caching changes require evidence and explicit design review; this proposal does not presume any of them.
- Keep the existing `duplicate_candidate_group_id` source-record API field fresh after successful publication-set mutations. If a mutation path cannot safely participate in an existing shared transaction, stop implementation of projection materialization and present transaction-boundary options; do not permit a partial update.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `deduplication-screening-consistency`: require duplicate-group GET to be read-only, preserve backend-derived results and cross-workflow readiness, and define observable initial-load behavior and diagnostic evidence.

## Impact

- Likely backend areas: `app/api/routers/deduplication.py`, `app/services/project_duplicate_service.py`, and `app/repositories/import_source_record_repository.py`.
- Likely frontend areas: duplicate-group fetch/context and deduplication page loading-state components under `frontend/src/`.
- Tests: disposable-SQLite backend integration tests, frontend component tests, and Playwright E2E against a test backend/project fixture. No production research database or data is in scope.
- Observability: request/stage timing and aggregate counts for GET; browser first-visible-state/render timing. Existing API response contract remains compatible.
- No schema migration is assumed. Any proposed schema or history change is out of scope and must be raised for separate approval.
- Out of scope: deduplication algorithm changes, screening methodology or decisions, PRISMA counting rules, import acceptance behavior, source-record content, modifying/deleting/backfilling existing snapshot or reviewer-decision history, timeout/retry changes without diagnostic evidence, production infrastructure changes, deployment, release, merge, and archive.
