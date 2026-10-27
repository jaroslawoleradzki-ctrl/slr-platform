# SLR Platform v0.7.3 — R5 Final Quality & Performance Remediation Report

**Status:** FUNCTIONAL PASS · PERFORMANCE PASS · QUALITY GATES PASS · CI NOT YET RUN

**Branch:** `fix/v0.7.3-r5-quality-performance`
**Worktree:** `/home/cloud/dev/wt-v0.7.3-r5-quality-performance`
**Base commit:** `4b34f9b8f62b8d2507ba306d92cb61f9d3e8f24f`
**Report date:** 2026-10-27

---

## 1. Executive summary

The three findings from the independent final audit were remediated on an isolated branch:

| Finding | Resolution | Evidence |
|---|---|---|
| **H-01** Ruff/Mypy quality gates fail | All 15 Ruff and 11 Mypy baseline errors fixed; configuration untouched | `ruff check app tests scripts` exit 0; `mypy app` exit 0 (202 files) |
| **H-02** Duplicate-grouping and PRISMA performance regression | Candidate generation replaced with an exact indexed algorithm; PRISMA now builds duplicate groups twice per request instead of three times; workflow/eligibility share one screening input set | 2000-record service path **38.124 s → 0.531 s**; PRISMA **79.233 s → 1.027 s**; candidate output byte-identical to the pre-remediation implementation |
| **M-01** DOI re-import links to a superseded publication | DOI matches now follow `superseded_by` chains to the active canonical; broken/cyclic chains raise a safe, auditable error and roll back the import | 7 deterministic regression tests covering one-step, multi-step, missing target, cycle, conflicting DOI, cross-project isolation, and provider path |

No functionality was disabled, no matching was made more aggressive, no candidate cap was introduced, and no duplicate decision is made automatically. All duplicate candidates remain researcher-controlled.

**Final readiness:** ready for independent re-audit; **not** ready for merge or production until CI has actually run and the historical 508/62 real-data check is available.

---

## 2. Git baseline

| Item | Value |
|---|---|
| Repository | `/home/cloud/dev/slr-platform` |
| Source branch | `feature/v0.7.3-final-audit-remediation` |
| Required base | `4b34f9b8f62b8d2507ba306d92cb61f9d3e8f24f` |
| Source worktree state at start | clean |
| Target branch before creation | absent |
| Target worktree before creation | absent |
| New worktree | `/home/cloud/dev/wt-v0.7.3-r5-quality-performance` |
| New worktree HEAD at creation | `4b34f9b8f62b8d2507ba306d92cb61f9d3e8f24f` |
| New worktree state at creation | clean |

No `reset`, `clean`, `stash`, merge, push, tag, release, deploy, or deletion of existing worktrees was performed. The original/audit/R1–R4 worktrees and the dirty `development` worktree were not modified.

### Commits

| Commit | Subject |
|---|---|
| `0faf9a9` | `fix(slr): restore v0.7.3 quality gates` |
| `c899a72` | `perf(slr): optimize duplicate grouping and PRISMA` |
| `08323a9` | `fix(slr): resolve active canonical after DOI merge` |
| _final report commit_ | `docs(slr): add v0.7.3 R5 final remediation report` |

---

## 3. R5.1 — Ruff/Mypy fixes (H-01)

### Exact baseline (recorded before any edit)

`ruff check app tests scripts` — **15 errors**:

- 6 × `I001` unsorted/unformatted import blocks
- 1 × `F401` unused `default_duplicate_merge_repository` import
- 1 × `F401` unused `uuid.UUID` import in `scripts/ris_import_reconciliation.py`
- 5 × `F841` unused local variables
- 1 × `F841` unused `provenance` local
- (one `I001`/`F841` pair in test files)

Exact baseline files are preserved at `/tmp/v073-r5/ruff_baseline.txt`.

`mypy app` — **11 errors in 4 files**:

- `project_duplicate_service.py`: `None` assigned to `ImportSourceRecordRepository`
- `project_import_service.py`: optional `ProvenanceEntry` assigned to non-optional; five duplicate definitions (`publication`, `index`, `valid_doi`, `original_doi`, `doi_status`)
- `prisma_metrics_service.py`: `None` assigned to repository attributes (2)
- `search_strategy.py`: `str` passed where `UUID` expected in both import-audit endpoints (2)

Exact baseline is preserved at `/tmp/v073-r5/mypy_baseline.txt`.

### Fixes

- Import ordering and unused imports fixed mechanically with `ruff --fix`, then reviewed.
- Optional repository attributes explicitly annotated as `T | None` in constructors.
- Duplicate loop/name definitions renamed (`prepared_publication`, `prepared_valid_doi`, `existing_valid_doi`, etc.).
- Import-audit endpoint path parameters typed as `UUID`; response still serialises `str(import_id)`.
- Unused fixture constructors removed without deleting any test or assertion.
- No Ruff/Mypy configuration change, no blanket `# type: ignore`, no file exclusion, no test removal.

### Result

```text
ruff check app tests scripts  →  All checks passed!  (exit 0)
mypy app                      →  Success: no issues found in 202 source files  (exit 0)
```

---

## 4. R5.2 — Performance root cause (H-02)

The pre-remediation builder (`4b34f9b`) performed, for every file-import record, a comparison against the **entire collection**:

```text
for first in file_origin:
    for second in publication_list:      # O(n²)
        normalize both titles             # repeated regex/Unicode normalization
        SequenceMatcher(...)              # repeated character similarity
```

Additional costs found by inspecting the call graph:

1. `_normalized_title()` was recomputed inside every comparison.
2. No exact-title or token index existed; every unrelated title reached `SequenceMatcher`.
3. `PrismaMetricsService.get_metrics()` built duplicate groups for the active population, then `get_status()` built a screening input set, then `get_excluded_counts()` built another one — three builder executions per metrics request.
4. `stage_readiness()` rebuilt the input set even when its caller already had one.
5. `GET /duplicate-groups` builds groups on the active population; no cache is persisted, so cross-request staleness is impossible.

The audit’s 578-publication project measured 12.202 s for duplicate groups, 86.937 s for PRISMA, and ~601,474 title comparisons across six builder executions.

---

## 5. Optimization architecture

### 5.1 Exact candidate generation (`app/services/duplicate_group_builder.py`)

- **Integer-indexed union-find.** Records are mapped to dense indices in deterministic UUID order; union-find never hashes UUIDs in the hot loop.
- **Normalized-title cache.** Each title is normalized once per `build()`.
- **Exact-title buckets.** Identical normalized titles are grouped first, including DOI-bearing counterparts; behaviour unchanged.
- **Token-count guard.** `titles_are_similar()` rejects pairs whose token counts differ by more than 4. This is used as a necessary condition before candidate generation.
- **Digit-masked shape key.** Titles that differ only by numeric tokens are rejected by the existing numeric-only rule. The builder precomputes a shape (`"#"` for any digit token) and never compares two records with the same shape. This is a proof, not a heuristic: same shape ⇒ all differing tokens are digits ⇒ the existing rule returns `False` (or the titles were already equal and skipped).
- **Top-5 rarest-token inverted index.** For titles with ≥5 tokens, each title indexes its five rarest distinct tokens by global document frequency. Every pair the old code could accept with ≥5 tokens on both sides shares its *rarest shared token*, and that token must be inside both top-5 prefixes because at most four tokens can be unique to either side. Therefore the index cannot drop an accepted pair.
- **Short-title bucket.** Titles with ≤4 tokens are compared against the short-title bucket, preserving typo-only matches that share no token.
- **Component-aware short-circuit.** If both records are already in the same component, the pair cannot change group membership; similarity is skipped. Bitsets make the same-component filter a C-level operation.
- **Precomputed token counters/sets.** The hot loop reuses per-title `Counter` and `frozenset` values instead of rebuilding them for every pair. A distinct-token symmetric-difference check rejects most unrelated pairs before any counter subtraction.
- **Exact prefix/suffix character bound.** For pairs that reach the character stage, a valid upper bound for `SequenceMatcher.ratio()` is computed from the maximal common prefix/suffix plus the character-multiset intersection of the differing middles. If the bound is below 0.92, the full ratio is not computed. This is an exact prefilter (no decision changes).
- **No cutoffs.** There is no record cap, no candidate cap, no year/author blocking, and no silent truncation. High-collision groups remain fully enumerated.

### 5.2 Request-scoped reuse (`prisma_metrics_service.py`, workflow/eligibility)

- `ScreeningInputService.get_input_set(..., groups=...)` accepts precomputed groups.
- `ProjectWorkflowStatusService.get_input_set()` builds one input set; `get_status(..., input_set=...)` and `get_excluded_counts(..., input_set=...)` reuse it.
- `ScreeningEligibilityAdapter.eligible_publications`, `excluded_publications`, and `stage_readiness` accept the same input set; `stage_readiness` passes it to its internal eligibility call.
- PRISMA still builds one group set for the active population and one for the screening corpus (semantically distinct when superseded/pre-screening-removed records exist), for **2 executions per metrics request** and **1 per duplicate-groups request**.
- No persistent cache was introduced, so imports, merges, review decisions, recovery, and publication updates cannot be served stale data.

---

## 6. Before/after benchmarks

Environment: same machine, Python 3.12.13, disposable SQLite under `/dev/shm`. Dataset is deterministic and exercises all required categories A–E (unrelated, exact duplicates, conservative similar titles, DOI/no-DOI mixed, adversarial high-collision). New timings are warm-up + median of 3; old timings are single runs (a warm-up would double an already multi-minute cost).

### 6.1 Required table — 2000 normal/mixed records

| Dataset size | Duplicate groups before | Duplicate groups after | PRISMA before | PRISMA after | Candidate count before/after | Comparison count before/after |
|---:|---:|---:|---:|---:|---:|---:|
| 200 | 0.427 s | 0.033 s | 0.788 s | 0.035 s | 52 / 52 | 36,589 / 3,612 |
| 500 | 2.440 s | 0.069 s | 4.704 s | 0.090 s | 49 / 49 | 238,321 / 22,225 |
| 1000 | 9.808 s | 0.159 s | 19.137 s | 0.273 s | 54 / 54 | 975,500 / 97,009 |
| **2000** | **38.124 s** | **0.531 s** | **79.233 s** | **1.027 s** | **53 / 53** | **3,948,399 / 416,100** |

- “Duplicate groups” is the full `GET /duplicate-groups` service path (active-population read + builder + response assembly).
- Candidate count is the number of member pairs across returned groups; it is identical before/after (52, 49, 54, 53).
- Returned group counts are identical before/after: 21, 29, 32, 31.
- 2000-record targets: duplicate groups **0.531 s ≤ 2 s**, PRISMA **1.027 s ≤ 3 s**.
- Improvement at 2000: service **71.8×**, PRISMA **77.1×**, builder-only **74.3×**.

### 6.2 Builder-only and readiness

| Size | Builder before | Builder after | Screening input | Stage readiness |
|---:|---:|---:|---:|---:|
| 200 | 0.386 s | 0.008 s | 0.011 s | 0.011 s |
| 500 | 2.413 s | 0.032 s | 0.037 s | 0.035 s |
| 1000 | 9.788 s | 0.127 s | 0.125 s | 0.123 s |
| 2000 | 40.492 s | 0.545 s* | 0.495 s | 0.508 s |

\* Instrumented run (comparison counter adds wrapper overhead). The same build without instrumentation measured **0.468 s median / 0.480 s max**.

### 6.3 578-publication audit reference

The audit’s original 578-record project is not present in the repository (no source rows/import history), so the exact project cannot be replayed. A deterministic 578-record subset of the R5 dataset was used for scale comparability:

| Path | Audit baseline | R5 deterministic 578 | Improvement |
|---|---:|---:|---:|
| Duplicate groups | 12.202 s | 0.074 s | **164.9×** |
| PRISMA | 86.937 s | 0.105 s | **827.9×** |

These exceed the required ≥10× improvement, but the datasets differ; the exact audit project remains `NOT VERIFIED`.

### 6.4 Initial deterministic baseline

Before any optimization, the first deterministic harness measured one builder execution at 2000 records in **317.512 s** (median; 82.082 s at 1000, 19.646 s at 500, 3.204 s at 200). The final all-category 2000 builder is **0.468 s**, a **678×** reduction on a comparable synthetic scale.

### 6.5 Adversarial worst case (limitation)

A worst-case family of 2000 near-identical titles (common template, differing variation/cohort tokens) still has many candidate pairs. It completes in **5.46 s** (median) for the single builder call, down from **13.9 s** before the final prefilters. No candidate is dropped and no cutoff is applied. This is reported as an explicit limitation; the 2000-record normal/mixed targets are met.

---

## 7. Candidate-set equivalence evidence

The pre-remediation builder was extracted verbatim from `4b34f9b` and compared against the optimized builder.

### 7.1 Exact group signatures

Fixtures covering all five categories and short-title cases produced **identical** group IDs, member order, `match_type`, and `match_reason`:

| Fixture | Records | Baseline groups | Optimized groups | Identical |
|---|---:|---:|---:|---|
| A–E fixture 120 | 120 | 19 | 19 | **YES** |
| A–E fixture 300 | 300 | 26 | 26 | **YES** |
| A–E fixture 600 | 600 | 29 | 29 | **YES** |
| Short-title/typo fixture | 11 | 3 | 3 | **YES** |
| A–E fixture 1000 | 1000 | 32 | 32 | **YES** |
| A–E fixture 2000 | 2000 | 31 | 31 | **YES** |

### 7.2 Similarity-decision equivalence

Old and new `titles_are_similar` decisions were compared on every pair in the fixtures plus 5,000 deterministic randomized strings:

```text
similarity comparisons: 224,472
similarity mismatches:   0
fixture failures:        0
EQUIVALENCE PASS
```

Covered behaviours:

- exact-title candidates preserved;
- DOI-bearing and title-only counterparts preserved;
- conflicting-DOI evidence preserved (`conflicting_identifiers`);
- conservative similar-title candidates preserved (`similar_title`);
- numeric-only false positives still rejected (`study 201` vs `study 202`);
- short-title typo candidates preserved through the short bucket;
- group IDs stable where membership is unchanged;
- cross-project isolation verified (separate builds share no member IDs).

No intentional output differences were introduced.

---

## 8. PRISMA performance evidence

| Metric | Before | After |
|---|---:|---:|
| Builder executions per `get_metrics()` | 3 | **2** |
| Builder executions per `GET /duplicate-groups` | 3 (audit total) | **1** |
| 2000-record PRISMA median | 79.233 s* | **1.027 s** |
| 2000-record PRISMA maximum | 79.233 s* | **1.039 s** |

\* Single-run old implementation on the same deterministic A–E dataset; the audit project measured 86.937 s at 578 records.

PRISMA accounting semantics were verified by the existing R4 source-aware tests (all passing):

- source records and repeated occurrences;
- exact DOI duplicates;
- canonical publications;
- merged records;
- recovered records;
- pending duplicate groups;
- historical fallback without source rows;
- API/export agreement.

Workflow status and excluded counts now consume the same `ScreeningInput` object; `stage_readiness` does not rebuild it. No persistent cache exists, so no invalidation surface was added.

---

## 9. R5.3 — DOI/canonical resolution (M-01)

### Reproduction

Deterministic IDs make the DOI-bearing member the higher UUID, so the merge canonical is the lower-UUID title-only member and the DOI-bearing record is superseded — exactly the audited failure, without depending on random UUID order.

### Implementation

New helpers in `app/services/project_import_service.py`:

- `_resolve_active_canonical(project_id, record_id, superseded_by)` follows `superseded_by` links until `None` and returns the active canonical.
- `_active_canonical_for_doi(...)` resolves DOI candidates in deterministic collection order and returns the first valid active canonical.
- `_doi_candidates(...)` builds a project-scoped DOI → candidate list index.
- `CanonicalResolutionError(ValueError)` is raised for dangling targets, targets absent from the project, and cycles.

Both import paths use them:

- **File import:** `existing_by_doi` was replaced by `existing_doi_candidates`; a match is resolved before a source occurrence is linked. The audit reason records when a superseded publication was involved.
- **Provider import:** `by_doi` was replaced by `doi_candidates`; non-inserted provider occurrences resolve the DOI to the active canonical before linking.

Behaviour:

- one-step and multi-step chains resolve to the final active canonical;
- missing target and cycle raise an explicit error; the import transaction rolls back, leaving no partial source/history rows;
- a valid active canonical is never replaced by a new publication;
- new source records are never linked to a superseded ID;
- resolution is confined to the requested project;
- existing merge decisions, historical source rows, and reviewer decisions are unchanged.

### Regression tests (7)

`tests/integration/test_v073_r5_doi_canonical_integrity.py`:

1. re-import DOI after merge links the active canonical, not the superseded record;
2. multi-step supersession chain resolves the final active record;
3. missing supersession target raises and rolls back;
4. malformed cycle raises and rolls back;
5. DOI resolution is project-scoped;
6. conflicting DOI candidates resolve deterministically to the first valid active canonical;
7. provider re-import links the active canonical.

All 7 pass.

---

## 10. New R5 regression tests

| File | Tests | Purpose |
|---|---:|---|
| `tests/unit/services/test_v073_r5_performance_equivalence.py` | 9 | all-pairs reference equivalence, similar-title preservation, numeric-only rejection, short-title bucket, conflicting DOI, determinism/isolation, bounded comparison count, PRISMA 2-build reuse, duplicate-groups 1-build reuse |
| `tests/integration/test_v073_r5_doi_canonical_integrity.py` | 7 | all R5.3 canonical-resolution cases |

Performance tests are functional/deterministic; the only bound is a comparison-count ceiling (`< 100,000` at 1000 records) intended to catch a return to unbounded all-pairs behaviour. It is not a wall-clock threshold, avoiding shared-runner flakiness. Detailed timings are in this report.

### R5 targeted suite

```text
tests/integration/test_v073_r1_import_integrity.py
tests/integration/test_v073_r1_migrations.py
tests/integration/test_v073_r2_duplicate_review.py
tests/integration/test_v073_r3_recovery.py
tests/integration/test_v073_r4_prisma_source_aware.py
tests/integration/test_v073_r5_doi_canonical_integrity.py
tests/unit/services/test_v073_r5_performance_equivalence.py
→ 60 passed, 1 warning in 6.27 s
```

---

## 11. Full backend/frontend results

| Check | Command | Result |
|---|---|---|
| Ruff | `ruff check app tests scripts` | **PASS** — All checks passed, exit 0 |
| Mypy | `mypy app` | **PASS** — 202 files, no issues, exit 0 |
| Backend | `pytest -q -p no:cacheprovider` with `SLR_DATABASE_PATH` + `TMPDIR` under `/dev/shm` | **PASS — 2544 passed**, 1 warning, 92.68 s |
| Frontend | `npm test` | **PASS — 342 passed**, 44 files, 6.98 s |
| TypeScript | `npm run type-check` (`tsc --noEmit`) | **PASS** |
| Production build | `npm run build` | **PASS**, built in 1.53 s (chunk-size warning only, pre-existing) |
| Migrations | migration-focused pytest selection | **PASS — 31 passed**, 0.74 s |

The backend total is 16 higher than the audit’s 2528, matching the 16 new R5 tests.

All databases used for validation were disposable SQLite files under `/dev/shm` or pytest `tmp_path`. No production database was opened or written. A generated empty `data/slr-platform.db` produced by repository construction during local runs was removed; it was ignored, empty, and never committed.

---

## 12. Migration compatibility

The migration-focused suite includes:

- `tests/integration/test_v073_r1_migrations.py`
- `tests/integration/test_pre_screening_archive_migration_and_workflow.py`
- extraction/synthesis migration tests (0019–0026)
- `tests/unit/repositories/test_migration_reconciliation.py`

Result: **31 passed in 0.74 s**. No migration file was added or modified by R5; schema compatibility is unchanged.

---

## 13. CI readiness

- `.github/workflows/` is **absent on this branch** because it was created from `4b34f9b`, which predates the development CI merge.
- `development` (`e97c8b1`, “Merge pull request #4 … ci/self-hosted-runner”) contains `.github/workflows/ci.yml`.
- The workflow uses the self-hosted `ai-node-slr-platform` runner, a runner-policy check, Ruff, Mypy, the full pytest suite with disposable SQLite, and frontend type-check/test/build. It was **not modified**, and no GitHub-hosted runner was added.
- Every declared gate was executed locally with equivalent commands and passed.
- No push, PR, merge, tag, or workflow dispatch was performed.

**GITHUB ACTIONS: NOT RUN** — no workflow run was observed.

---

## 14. Remaining limitations

1. **Historical 508/62 real-data verification:** the original RIS files and source rows are unavailable; this remains `NOT VERIFIED`.
2. **Exact audit project replay:** the 578-publication project is unavailable. The 578-record comparison uses a deterministic dataset of the same size; absolute times are not directly interchangeable.
3. **Old-implementation timings** are single runs without warm-up because a warm-up would double multi-minute costs. New timings use warm-up + median of 3.
4. **Adversarial worst case:** a single 2000-member near-identical title family still takes 5.46 s for the builder because every pair is a legitimate candidate unless the numeric-only rule applies. No candidates are dropped; this is a deliberate correctness-over-speed trade-off and is reported rather than hidden by a cutoff.
5. **Frontend dependency source:** local frontend validation used the existing workspace `node_modules` (TypeScript 5.9.3, compatible with `^5.7.2`) because the new worktree had no install; `npm ci` was not run. CI will run the locked install.
6. **Synthetic data:** equivalence and timing fixtures are deterministic synthetics, not the production corpus.

---

## 15. Changed files

```text
app/api/routers/search_strategy.py
app/normalization/title.py
app/services/duplicate_group_builder.py
app/services/prisma_metrics_service.py
app/services/project_duplicate_service.py
app/services/project_import_service.py
app/services/project_workflow_status_service.py
app/services/screening_eligibility_adapter.py
app/services/screening_input_service.py
scripts/ris_import_reconciliation.py
tests/integration/test_v073_r1_import_integrity.py
tests/integration/test_v073_r1_migrations.py
tests/integration/test_v073_r2_duplicate_review.py
tests/integration/test_v073_r4_prisma_source_aware.py
tests/integration/test_v073_r5_doi_canonical_integrity.py        (new)
tests/unit/services/test_project_import_service.py
tests/unit/services/test_v073_duplicate_candidate_remediation.py
tests/unit/services/test_v073_r5_performance_equivalence.py       (new)
docs/reviews/V073_R5_FINAL_REMEDIATION_REPORT.md                  (this report)
```

Diff from base: 18 changed files, +1,405 / −164 (before this report commit).

---

## 16. Commit SHAs

| Stage | Commit | Subject |
|---|---|---|
| R5.1 | `0faf9a9` | `fix(slr): restore v0.7.3 quality gates` |
| R5.2 | `c899a72` | `perf(slr): optimize duplicate grouping and PRISMA` |
| R5.3 | `08323a9` | `fix(slr): resolve active canonical after DOI merge` |
| Report | _recorded after commit_ | `docs(slr): add v0.7.3 R5 final remediation report` |

---

## 17. Final readiness assessment

| Gate | Verdict |
|---|---|
| FUNCTIONAL | **PASS** — 2544 backend, 342 frontend, 60 targeted R1–R5, 31 migration |
| PERFORMANCE | **PASS** — 2000-record service 0.531 s ≤ 2 s; PRISMA 1.027 s ≤ 3 s; ≥10× improvement exceeded on every measured path |
| QUALITY GATES | **PASS** — Ruff 0, Mypy 0 |
| CANDIDATE EQUIVALENCE | **PASS** — 224,472 similarity decisions, 0 mismatches; identical groups through 2000 records |
| CI | **NOT YET RUN** |
| Historical 508/62 real-data check | **NOT VERIFIED** |
| Ready for independent re-audit | **YES** |
| Ready for merge | **NO** |
| Ready for production | **NO** |

Reasons merge/production remain blocked: no actual CI workflow run has been observed, and the historical real-data verification is still unavailable.

---

## Required final status block

```text
R5 STATUS: PASS

R5.1 QUALITY: PASS
R5.2 PERFORMANCE: PASS
R5.3 DOI INTEGRITY: PASS

RUFF: PASS
MYPY: PASS

BACKEND: PASS
FRONTEND: PASS
TYPESCRIPT: PASS
BUILD: PASS

2000 RECORD DUPLICATE GROUPS: 0.531 seconds
2000 RECORD PRISMA: 1.027 seconds

CANDIDATE EQUIVALENCE: PASS

GITHUB ACTIONS: NOT RUN

READY FOR INDEPENDENT RE-AUDIT: YES
READY FOR MERGE: NO
READY FOR PRODUCTION: NO

BRANCH:
fix/v0.7.3-r5-quality-performance

WORKTREE:
/home/cloud/dev/wt-v0.7.3-r5-quality-performance

FINAL HEAD:
the report commit at the branch tip (see `git log -1` / final output)

REPORT:
docs/reviews/V073_R5_FINAL_REMEDIATION_REPORT.md
```
