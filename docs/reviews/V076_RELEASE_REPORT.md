# SLR Platform v0.7.6 — Release Report

**Branch:** `feature/slr-v0.7.6`
**Release type:** patch (bug fix + performance remediation for v0.7.5)
**Base:** `v0.7.5` (`8554025`)
**Release candidate:** `019d053` (feature + CI-green) plus this release metadata commit
**Date:** 2026-10-29

## 1. Scope

v0.7.6 remediates BUG-01, diagnosed after the v0.7.5 production deployment
(`docs/reviews/V075_BUG01_DIAGNOSTIC_REPORT.md`):

- Import decisions propagate to the shared `workflowStatus` immediately (sidebar and
  dashboard Sources stage), instead of waiting for a full refresh.
- Source-summary successful/warning counters update from the decision response; research
  populations stay unchanged.
- `refreshWorkflowStatus` publishes partial results per endpoint and applies an 8 s
  per-endpoint timeout.
- Duplicate-group and PRISMA read models are memoized for 10 s, keyed by project id, and
  cleared on project switch and on mutating actions.
- The batch extraction-eligibility path no longer recomputes the screening input set per
  publication.

OpenSpec change `slr-v0-7-6-dashboard-refresh-performance` is archived and its delta spec is
merged into `openspec/specs/workflow-status/spec.md`.

## 2. Release metadata

- `VERSION`, `pyproject.toml`, `frontend/package.json`, `frontend/package-lock.json`, and
  `uv.lock` synchronized to `0.7.6`.
- Version assertions updated in `tests/unit/test_versioning.py` and
  `frontend/tests/Versioning.test.tsx`.
- `CHANGELOG.md` entry and `docs/releases/v0.7.6.md` added.
- Historical evidence committed: v0.7.5 deployment report and BUG-01 diagnostic report,
  both previously untracked.
- `uv.lock` no longer pins the editable project at `0.7.4`; `uv lock --check` passes.

## 3. Quality gates

| Gate | Result |
|---|---|
| `bash scripts/agent/safe_pytest.sh` (full) | 2718 passed, 1 failed — `test_configured_free_models_are_in_standalone_catalog` (local `opencode models` catalog lacks `opencode/nemotron-3-ultra-free`; CI authoritative and green) |
| `tests/unit/test_versioning.py` | 1 passed |
| Ruff | All checks passed |
| Mypy | 208 source files, no issues |
| Frontend type-check | passed |
| Frontend tests | 365 passed / 50 files |
| Frontend production build | passed (chunk-size warning only) |
| `openspec validate --all --strict` | 4 passed, 0 failed |
| `uv lock --check` | passed |
| CI (branch tip `019d053`) | run `40875181563`, success, 3m8s |

No red-first evidence is re-claimed here for the implementation; the original red/green
evidence is in `docs/reviews/V076_IMPLEMENTATION_REPORT.md`. These gates validate the
release metadata and the unchanged implementation.

## 4. Known limitations

- **Production post-change timing NOT VERIFIED.** The project owner waived the measurement
  gate on 2026-10-29. The report does not claim a production speed-up.
- The timeout path is covered indirectly via partial-result tests, not with fake timers.
- The performance test uses mocked large arrays; it does not measure network or backend
  latency.
- The single local pytest failure is an agent-model catalog mismatch in this environment;
  it is not caused by v0.7.6 and is green on the self-hosted CI runner.

## 5. Research integrity

- No migration, schema change, or data backfill.
- No PRISMA stage population, canonical publication, source record, working-collection
  total, duplicate decision, or screening decision is modified by decision propagation or
  refresh.
- Decisions remain non-destructive, append-only, and attributed.
- No scientific decision is automated.

## 6. Deployment preflight (human-run)

1. Confirm green CI on the release commit and a clean worktree.
2. Merge `feature/slr-v0.7.6` into `development`, then `development` into `main` (approval
   required).
3. Tag `v0.7.6` and publish the GitHub Release.
4. Create a database backup before deployment and record its hash and `integrity_check`.
5. Deploy image `slr-platform:v0.7.6`; no migrations expected.
6. Post-deployment: health, version (`0.7.6`), project/workflow smoke read, and log scan
   for errors.
7. Keep `slr-platform:v0.7.5` and the backup available for rollback.

## 7. Rollback

- Image-only rollback to `slr-platform:v0.7.5`; no schema downgrade is required.
- If data restore is ever needed, restore the pre-deployment backup after hash and
  `integrity_check` verification. Never use broad `DELETE`/`UPDATE` SQL.
