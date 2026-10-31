# Verify follow-up: deduplication read path and first load

Status: **PASS WITH CONDITIONS** for another independent Verify. This is implementation evidence, not an independent Verify verdict or merge approval. Full backend regression has one unrelated failing external catalog check; CI for the task commit is **NOT VERIFIED**. No merge, deployment or archive was performed.

## Scope and recovered review

Work continued in `/tmp/slr-platform-fix-deduplication-read-path-and-first-load`, branch `feature/fix-deduplication-read-path-and-first-load`, based on `74fd67a`. All inherited source, test and planning changes were retained. Generated Playwright output is left uncommitted. No production research database, backup or HomeLab data was read or modified.

The complete prior Verify was recovered from the assistant response in Codex session `01a19106-aa51-72f1-8695-f6e41622315f`, rather than inferred from the Apply report. Its original answer is preserved in [the recovered report](2026-10-31-dedup-independent-verify-recovered.md). The original Apply report is historical; this report supersedes its evidence and completion claims.

Acceptance criteria: final rebuild projection agrees with reconciled groups; failures roll back all rebuild writes; GET remains read-only and internally consistent; E2E verifies real members and readiness on first navigation; diagnostics cover and correlate stages through ASGI send completion; task evidence records remaining uncertainty honestly. Matching, DOI normalization, screening and PRISMA rules remain unchanged.

## Confirmed corrections and evidence

| Prior Verify finding | Follow-up evidence |
|---|---|
| HIGH: stale source projection after rebuild (3.2) | Rebuild now uses one outer SQLite transaction for the shared normalization operation, existing reconciliation, and final projection. All reconciliation reads/deletions use that connection. The existing reconciliation rules/order are retained. |
| Vacuous source assertion | The retained → removed → rebuild fixture now creates three actual source records, requires a historical group ID before rebuild, and verifies all final IDs are null when GET has no groups. Failure after final projection verifies publications, full source records, immutable snapshots, decisions, merges and execution summary equal their pre-operation state. |
| Missing shared operation | `normalization_operation.run_project_normalization` is used by both POST normalization and rebuild, with a caller-owned connection supported for rebuild. Default rebuild execution/duplicate repositories bind to the supplied publication DB. |
| Weak first-load E2E (2.8, 4.1) | Direct navigation to `/dedup` captures the real GET and checks exactly one group, two expected titles, pending readiness=1, screening_ready=false, visible pending badge, both member titles and review action. A blank successful response fails these assertions. |
| Dev frontend / manual document reload | Playwright builds the frontend and serves Vite preview. Import acceptance uses SPA Dashboard navigation; a random window token must survive, proving no document reload. |
| Weak concurrency test (2.3) | New event-controlled tests pause GET after corpus read, wait for the prepared real import service's uncommitted projection, then resume GET. They compare the entire response with the saved pre-import response and verify the final candidate/readiness after import. Both DELETE and WAL pass. Repository schemas are initialized before interleaving; otherwise DELETE mode can block schema initialization before the import transaction begins. |
| Incomplete diagnostics (1.2) | An ASGI route wrapper logs actual status, response byte count and duration after the last body is handed to send. A context-local random token links service stages, endpoint outcome and response completion. Readiness has a separate stage time. Tests verify byte count, correlation and absence of project IDs. ASGI completion does not claim that the browser has received the bytes. |
| Unsupported historical measurements (1.3, 4.2) | Original HEAD code was freshly extracted using `git archive HEAD app migrations VERSION`; HTTP and browser measurements were rerun with distinct new temporary databases. Results below replace reliance on historical measurement claims. |
| Overstated report/task completion (4.4) | This report, recovered review and updated tasks distinguish observed evidence from the production incident, historical TDD limits, external catalog failure and CI. |

One initial hypothesis in this session was rejected: assigning group match type/reason into source records would overwrite import classification. The full suite caught `test_title_without_doi_is_preserved_and_flagged`. That proposed change and its inappropriate assertion were removed. The inherited implementation intentionally updates candidate IDs while preserving import evidence; snapshots retain group match details. The final suite passes that integrity test.

## TDD and regression evidence

All tests used disposable SQLite databases under `/tmp`. Existing installed dependencies were reused; no provider, package or runtime dependency was added. TestClient/browser checks ran with authorized local socket access when required.

Test commands use this prefix in the worktree:

```sh
UV_CACHE_DIR=/tmp/slr-uv-cache UV_PROJECT_ENVIRONMENT=/home/cloud/dev/slr-platform/.venv bash scripts/agent/safe_pytest.sh
```

Observed red-first failures in this session:

- `tests/unit/services/test_normalization_dedup_active_corpus.py -k retained_to_removed`: **1 failed, 1 passed** before the outer-transaction fix. An exception after the final projection left normalized publication rows committed. The test was strengthened with three source records before changing the transaction implementation.
- `tests/unit/services/test_duplicate_group_read_path.py tests/unit/services/test_normalization_dedup_active_corpus.py`: initial run **2 failed, 20 passed**. The default rebuild read a different DB and raised ProjectNotFoundError. The other failure was the rejected metadata hypothesis described above, not a retained requirement.
- `tests/integration/test_v073_r2_duplicate_review.py -k diagnostics`: **1 failed, 2 passed** before ASGI completion instrumentation; no response-completion record existed.

Green/refactor verification:

- Active-corpus module: **19 passed**, including default repository binding, projection/summary failure rollback and the non-vacuous final rebuild failure case.
- Integration duplicate review plus active-corpus modules: **35 passed**, including correlation, forced concurrent import/GET in both journal modes, read-only GET/history invariance and rebuild rollback.
- Final full backend command (same prefix, no test filter): **2740 passed, 1 failed**, 101.10 seconds. The failure remains `tests/unit/test_agent_foundation_configuration.py::test_configured_free_models_are_in_standalone_catalog`: external `opencode models` omits `opencode/nemotron-3-ultra-free`. The test and agent configuration have no diff. It was neither skipped nor weakened; the full backend gate is not green.
- Frontend: `npm --prefix frontend test` — **51 files / 367 passed**; type-check passes. Build passes, with the existing Vite large-chunk advisory. Later changes were E2E/config only; the E2E lifecycle rebuilds the frontend.
- Built-frontend E2E: `REAL_BACKEND=1 SLR_PYTHON=/home/cloud/dev/slr-platform/.venv/bin/python frontend/node_modules/.bin/playwright test --config frontend/playwright.config.ts` — **8 passed**, 25.5 seconds, no skipped tests. Includes actual first-load groups/readiness, controlled 503/network/8-second timeout and acceptance without reload. Three import-review tests still use mocks and are not claimed as real-API coverage.
- Ruff passes; mypy passes for **211 source files**. Strict OpenSpec validation: **5 passed**. Migration safety passes (no migrations changed); diff hygiene passes.

The test diff adds real `ImportSourceRecord` fixtures and complete-state rollback assertions in `test_normalization_dedup_active_corpus.py`; whole-response snapshot/concurrency and correlation assertions in `test_v073_r2_duplicate_review.py`; actual member/readiness assertions in the first-load E2E; and the document-token assertion in the workflow E2E. No integrity assertion was weakened. Earlier original-HEAD red comparisons establish behavioral regression sensitivity, not proof that inherited tests were authored first. Green CI likewise cannot prove historical TDD chronology.

## Repeated synthetic runtime measurements

Fresh baseline source is committed HEAD `74fd67a`, extracted without research files. Baseline/current use the same installed interpreter and generated publications, separate temporary databases and the same built frontend. Measurement scripts remain under `/tmp/slr-dedup-followup-{run,measure,compare,equivalence}.py`; no raw research content was used. The HTTP baseline comparison was invoked with `/home/cloud/dev/slr-platform/.venv/bin/python /tmp/slr-dedup-followup-run.py`.

20 HTTP GET samples per version, 250 publications / 125 groups:

| Metric | Original HEAD | Current |
|---|---:|---:|
| First HTTP ms | 171.523 | 17.610 |
| p50 ms | 166.026 | 13.480 |
| p95 ms | 207.997 | 54.335 |
| p99 ms | 210.373 | 54.615 |
| Successful responses | 20/20 | 20/20 |
| HTTP errors / timeouts | 0 / 0 | 0 / 0 |
| Response bytes | 122521 | 122521 |

Current stage p50/p95/p99 ms: corpus 4.183/45.482/45.553; decisions/merges 0.023/0.058/0.070; group build 3.540/5.019/5.187; readiness 0.119/0.129/0.196; serialization probe 0.323/0.368/0.409. These are service stages; the separate ASGI completion metric covers actual FastAPI serialization/send time. Baseline has no per-stage instrumentation.

A separate comparison fixes synthetic provenance timestamps and compares the complete response, excluding only the randomly assigned project_id. Both versions have SHA256 `39d0844a27a6ebb8667096f75568283f54e44e3da9eb71534418c102eee8461c`, covering group IDs, members, reasons, status and readiness. Response size is 120771 bytes in that fixed-timestamp fixture; it is separate from the timing fixture above.

20 browser render samples per version on two synthetic publications, production frontend build: baseline p50/p95/p99 **111.0/139.3/248.7 ms**; current **111.9/117.7/234.3 ms**. Baseline invocation uses the same Playwright command with `SLR_PYTHON=/tmp/slr-dedup-followup-baseline-python.sh` and `--grep 'renders candidate status'`, **1 passed**. The wrapper changes cwd to the freshly extracted baseline and invokes the same Python interpreter. No timeout/retry/cache/async policy changed.

## Limits and recovery

The production first-load incident is **NOT VERIFIED** as resolved: neither the previous nor this synthetic session reproduced it. Controlled first-load success, equivalent results and reduced repeated GET latency do not establish production incident frequency. Tests do not prove absence of every SQLite conflict for arbitrary corpus sizes; read transactions still cover computation/serialization and can delay writers in DELETE mode. The forced interleavings demonstrate bounded completion for these fixtures, not a universal lock guarantee. No timeout increase or retry was introduced to conceal errors.

Snapshots keep their existing schema and INSERT OR IGNORE first-write behavior. Projection materialization never rewrites reviewer decisions; rebuild retains its existing explicit stale-state reconciliation policy, now atomic with its final projection. No methodological rule or PRISMA counting path changed. Recovery from a failed rebuild is a retry of the explicit operation after addressing its failure: its transaction leaves the prior persisted state intact. No corrective production operation or backfill was run.

Implementation is ready for a new independent Verify. CI is not run and the external catalog gate remains failing; the branch is not merge-ready. No archive is requested or performed.
