# Implementation report: fix-deduplication-read-path-and-first-load

Historical Apply report. The later [Verify follow-up report](2026-10-31-dedup-verify-followup.md) supersedes its task-completion and coverage claims; the recovered independent Verify report is retained alongside it.

## Summary

The duplicate-groups GET now only derives and returns backend state, using one SQLite read-only snapshot for publications, decisions, and merges. Candidate-group source-record fields and immutable membership snapshots are materialized with the existing transaction for provider/file imports, rejected imports, pre-screening removal/restoration, duplicate merge, and SQLite normalization. Normalization writes, candidate projection, snapshots, and its latest execution summary share one connection and commit. The existing matching algorithm, group IDs, snapshot schema and first-write behavior, reviewer decisions, screening logic, PRISMA logic, timeout, and retry policy remain unchanged.

The import-review historical-membership fallback now accepts an immutable `PENDING` snapshot when its group ID has a persisted reviewer decision; it continues to treat the decision row as authoritative and does not modify either history table.

GET and normalization diagnostics record stage durations, outcome/status, bounded counts, response size, and a random correlation token. Browser performance entries record duplicate request outcomes/timeouts, general first-visible workflow status, and the specific first duplicate-result render after React commits it. These measurements contain no publication identifiers or content.

## Test execution diagnosis and evidence

The original `TestClient` hang was an execution-sandbox restriction, not a Python dependency or application defect. Inside the sandbox, `socket.socketpair()` raised `PermissionError: [Errno 1] Operation not permitted`; AnyIO's blocking portal event loop consequently remained idle and the calling test thread waited in `TestClient.__enter__` / `portal.call(wait_startup)`. A minimal FastAPI `/api/health` app reproduced this. The same smoke test and socketpair roundtrip succeeded outside the sandbox. Tests were therefore run outside the sandbox with the already installed `/home/cloud/dev/slr-platform/.venv/bin/python`; no Python packages were installed. Backend test fixtures use temporary databases, and aggregate suite runs explicitly use disposable `/tmp` databases.

Playwright was already in `frontend/package-lock.json` and the npm cache, but `frontend/node_modules` was absent in the worktree. `npm ci --offline` restored lockfile-pinned frontend dependencies from cache (194 packages, zero reported vulnerabilities); package manifests were unchanged. Chromium was already available. The Playwright configuration starts the real FastAPI app and Vite server, gives the API an isolated temporary SQLite database, creates synthetic projects/imports, and removes the database directory after server shutdown. Playwright was run outside the sandbox because server/socket restrictions also prevent its API lifecycle from working inside it.

The read-only GET regression passes for candidate and empty projects and checks source IDs, snapshots, reviewer decisions, and merge history. The regression fails against original HEAD because its GET populates null candidate IDs; it passes on the feature implementation. Eight parallel GETs concurrent with a synthetic import returned successful, complete responses. Rollback failures after projection were tested across provider/file import, import rejection, pre-screen remove/restore, merge, and normalization. Separate normalization injection covers a middle publication update, projection write, snapshot insert, and summary save. The original normalization API rollback test fails against original HEAD with already-normalized rows remaining and passes on current code. These baseline failures were reproduced during this verification; they do not prove the test files were authored before implementation.

## Results

- Backend integration/regression command (final run): same targeted modules listed above — **100 passed**, one Starlette deprecation warning recommending `httpx2`.
- Ruff: `/home/cloud/dev/slr-platform/.venv/bin/ruff check app tests scripts` — **PASS**.
- Mypy: `/home/cloud/dev/slr-platform/.venv/bin/mypy app` — **PASS**, 209 source files.
- Frontend type-check: `npm --prefix frontend run type-check` — **PASS**.
- Frontend tests: `npm --prefix frontend test` — **PASS**, 51 files / 367 tests.
- Frontend build: `npm --prefix frontend run build` — **PASS**. Vite reports the existing large-chunk advisory.
- OpenSpec: `openspec validate --all --strict` — **PASS**, 5 items.
- Diff hygiene: `python3 scripts/agent/safe_git_inspect.py diff --check` — **PASS**.
- Full backend suite: **2721 passed, 1 failed** in 100.16 seconds. The one failure is `tests/unit/test_agent_foundation_configuration.py::test_configured_free_models_are_in_standalone_catalog`, because the environment's external `opencode models` catalog omits `opencode/nemotron-3-ultra-free`. It is unrelated to the SLR implementation; this remains a full-suite gate failure and is not counted as pass.
- Playwright E2E: **7 passed** against an auto-started real FastAPI server and disposable SQLite database, including real first load, import-warning acceptance reflected in Sidebar and Dashboard without reload, import-review flows, controlled HTTP 503, network abort, and timeout. The first-load scenario also collected 20 duplicate-result render samples per backend using a synthetic project.
- Frontend unit suite: **51 files / 367 tests passed**. Type-check and production build pass; Vite emits its existing large-chunk advisory.
- CI — **NOT RUN**. The branch is not declared merge-ready.

## Synthetic timing and SQLite contention

Measurements used a disposable SQLite database and generated 250 synthetic publications arranged into 125 title-candidate groups. No research data or external API was used.

- Read-only service calls using the read-only snapshot transaction, 20 samples: first 8.88 ms; p50 9.19 ms; p95 15.88 ms; p99 16.20 ms; serialized response 123,885 bytes. No service-call error was observed. These are in-process service timings, not browser or HTTP timings.
- Normalization + projection + snapshot + summary transaction, 20 samples: p50 33.61 ms; p95 40.17 ms; p99 40.51 ms.
- Concurrent SQLite writer check: a second `BEGIN IMMEDIATE` waited 105.07 ms while a synthetic writer held the reservation for 100 ms, then acquired the lock successfully. In 20 concurrent read-only GET/writer samples, there were zero errors or `SQLITE_BUSY`/`SQLITE_LOCKED` outcomes; maximum writer transaction time was 11.87 ms.

### Original-HEAD versus current HTTP and browser comparison

The original backend source was extracted from committed HEAD `74fd67a` into `/tmp`; both runs used the same interpreter, current frontend where applicable, generated data, and separate disposable SQLite databases. The current HTTP process was pinned with `PYTHONPATH` to this feature worktree to avoid importing the protected checkout's editable package.

- HTTP GET, 250 synthetic RIS-origin publications / 125 exact-title groups, 20 requests per version: original HEAD first response 172.04 ms, p50 168.92 ms, p95 207.40 ms, p99 211.90 ms; current first response 17.81 ms, p50 13.19 ms, p95 54.89 ms, p99 55.84 ms. Both versions returned 20/20 HTTP 200 responses, zero timeout/5xx outcomes, 125 groups, and 122,521 response bytes. This controlled result is consistent with the removal of writes from repeated GET; it does not prove the reported production intermittent failure is resolved.
- Current GET stage timings on the same 250/125 synthetic size, 20 samples: active-corpus read p50/p95/p99 3.91/5.02/5.57 ms; decision/merge read 0.021/0.032/0.057 ms; group build 3.34/44.73/46.76 ms; serialization 0.33/0.40/0.74 ms. Tail group-build and full HTTP latency varied more than the medians.
- Current and original-backend browser duplicate-result render, 20 first-load/reload samples each on a small project with two synthetic publications: original p50/p95/p99 86.8/124.6/321.2 ms; current 88.7/113.1/137.1 ms. First-load rendered successfully for both; the small corpus and single controlled session do not characterize production browser latency or failure frequency.
- The earlier in-process normalization transaction timing and SQLite busy/locked contention results remain as reported above. The timeout and retry settings remain unchanged because these measurements do not establish a need to alter them.

## Remaining verification

The environment blockers for backend TestClient and Playwright are removed; targeted backend, frontend, and real-API E2E suites pass. Full backend pytest still has one external OpenCode-catalog failure. The synthetic comparison shows substantially lower current GET latency and successful first loads in both backend versions, but the reported production incident was not reproduced. The browser comparison used a small synthetic project. No production runtime logs were accessed, and no timeout or retry changes are justified. No merge, archive, deployment, or real research-data modification was performed.

## OpenSpec task audit

| Task | Status | Evidence / remaining limitation |
|---|---|---|
| 1.1 | Done, verified | Transaction map in `design.md`; targeted mutation tests pass. |
| 1.2 | Done, verified | Backend privacy-safe log assertion and browser request/render metrics. |
| 1.3 | Done with scope limitation | Synthetic HTTP, stage, transaction, lock and browser measurements are recorded. Original-HEAD stage timings cannot be reconstructed because that version had no stage instrumentation; no production data was accessed. |
| 2.1 | Done, verified | Candidate/no-candidate GET invariance; original HEAD fails on candidate ID mutation, current passes. |
| 2.2 | Done, verified | Deterministic group, screening and PRISMA regressions; included in final 100 passed. |
| 2.3 | Done, verified | Eight concurrent GETs during a synthetic import; each result was complete. |
| 2.4 | Done, behavior verified | All rollback points pass current and API partial-normalization assertion fails on original HEAD. Test-before-implementation chronology was not recorded. |
| 2.5 | Done, verified | Projection-failure rollback exercised for provider/file import, rejection, pre-screen removal/restoration, merge and normalization. |
| 2.6 | Done, verified | Historical `PENDING` membership snapshot plus reviewer decision blocks rejection; history remains unchanged. |
| 2.7 | Done, verified | Frontend loading/project-switch/error tests and new 5xx/network API tests; full 367-test suite passes. |
| 2.8 | Done, verified | Playwright owns API/Vite lifecycle and temporary DB; 7 actual-browser tests pass. |
| 3.1 | Done, verified | GET returns same derived groups without writes; API integration passes. |
| 3.2 | Done, verified | Shared SQLite connection and failure rollback tests pass for normalization and each active-corpus mutation boundary. |
| 3.3 | Done, verified | Persisted decision remains authoritative over immutable `PENDING` snapshot; regression passes. |
| 3.4 | Done, verified | Snapshot schema/immutability and decision/merge workflow tests pass. |
| 4.1 | Done, verified | Playwright covers success/loading, HTTP 503, network failure, and configured timeout. |
| 4.2 | Done, evidence limited | Original/current synthetic comparisons recorded; production intermittent incident was not reproduced. |
| 4.3 | Done, results recorded | All local gates executed; full backend retains one unrelated OpenCode-catalog failure. CI was not run. |
| 4.4 | Done, verified | This report contains test results, timings, rollback coverage, integrity invariants, and limits. |
