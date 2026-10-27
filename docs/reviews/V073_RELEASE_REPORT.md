# SLR Platform v0.7.3 — Release Report

**Release date:** 2026-10-27
**Release version:** `0.7.3`
**Tag:** `v0.7.3`
**GitHub Release:** https://github.com/jaroslawoleradzki-ctrl/slr-platform/releases/tag/v0.7.3
**Production deployment:** NOT PERFORMED

---

## 1. Preflight results

| Check | Result |
|---|---|
| Repository | `/home/cloud/dev/slr-platform` |
| `origin` | `git@github.com:jaroslawoleradzki-ctrl/slr-platform.git` |
| `homelab` | `cloud@192.168.100.22:/tank/git/slr-platform.git` (reachable) |
| `origin/development` at preflight | `e97c8b1c80e04e8d174ee8a1bcc0e0b701599595` |
| `origin/main` at preflight | `02c1759e384954d9820c4f4d7279cd4c1c3591e2` |
| Integration branch on origin | `integration/v0.7.3-r1-r5` at `4d8876e7724e94fb9865552749b6bfb5addc52ff` |
| Integration worktree | clean |
| Integration CI | green (`40473794313`, `40474271666`) |
| `v0.7.3` tag | absent locally and on origin |
| `v0.7.3` GitHub Release | absent |
| Previous release tag | `v0.7.2` → `02c1759` |
| Homelab mirror before sync | `main` `02c1759`, `development` `3ca83f3` |
| Source `development` worktree | dirty with pre-existing user files (preserved untouched) |

No branch or worktree was deleted, reset, cleaned, stashed, or force-pushed. No production database or container was touched.

## 2. Merge SHAs

| Stage | Commit | Subject |
|---|---|---|
| Integration merge of R5 | `4d8876e7724e94fb9865552749b6bfb5addc52ff` | integration report tip (already CI-validated) |
| Development merge | `17088d334a4dfec239ce8d5f829625eec041d03f` | `Merge branch 'integration/v0.7.3-r1-r5' into release/v0.7.3-development` |
| Version/release preparation | `9751f18197337aa8faf43cfe9268cc0006bce258` | `chore(release): prepare v0.7.3` |
| Main merge | `260744f34940cec7ecd8cedc882cee139c5e09cd` | `Merge remote-tracking branch 'origin/development' into release/v0.7.3-main` |
| Annotated tag object | `ec12d7e6a64337c742a652ab72650f35dfec6cef` | `SLR Platform v0.7.3` |
| Peeled tag target | `260744f34940cec7ecd8cedc882cee139c5e09cd` | validated `main` release commit |

Both merges were normal `--no-ff` merge commits. No squash or rebase was used. Both merges completed without conflicts.

## 3. Version changes

All authoritative version sources now report `0.7.3`:

- `VERSION`
- `pyproject.toml` (`[project].version`)
- `uv.lock` editable `slr-platform` package (previously stale at `0.7.1`)
- `frontend/package.json`
- `frontend/package-lock.json` root and `packages[""]` versions
- `tests/unit/test_versioning.py` expected version
- `frontend/tests/Versioning.test.tsx` expected `APP_VERSION`

Documentation added/updated:

- `CHANGELOG.md` — `[0.7.3] — 2026-10-27`
- `docs/releases/v0.7.3.md` — full release notes (used verbatim for the GitHub Release)

No conflicting version declaration remains in tracked files. `app.core.version.get_app_version()` reads `VERSION`.

## 4. Test results

### CI

| Workflow run | Head | Result |
|---|---|---|
| Integration (initial) `40473794313` | `fdde532` | success |
| Integration (final report) `40474271666` | `4d8876e` | success |
| Development `40475665901` | `9751f18` | success |
| Main `40476073385` | `260744f` | success |

Every run executed on the dedicated self-hosted AI-node runner and included:

- `CI runner policy` — success
- `Backend (Python 3.12)` — Ruff, Mypy, full pytest with disposable SQLite — success
- `Frontend (Node 22)` — `npm ci`, type-check, tests, production build — success

### Local release smoke checks on the main release commit

| Check | Result |
|---|---|
| Ruff | PASS |
| Mypy | PASS (202 files) |
| Version consistency test | 1 passed |
| R1–R5 targeted suite | 60 passed |
| TypeScript (`tsc --noEmit`) | PASS |
| Frontend version tests | 6 passed |
| Production build | PASS |
| Migration-focused suite (validated on integration) | 31 passed |

The integrated code was additionally validated before release with 2544 backend tests and 342 frontend tests.

## 5. CI run URLs

- Integration (final): https://github.com/jaroslawoleradzki-ctrl/slr-platform/actions/runs/40474271666
- Development release prep: https://github.com/jaroslawoleradzki-ctrl/slr-platform/actions/runs/40475665901
- Main release merge: https://github.com/jaroslawoleradzki-ctrl/slr-platform/actions/runs/40476073385

The administrative report commit on `development` triggers one additional run of the same development workflow; it was verified before final sign-off and does not move the tag.

## 6. Release notes

Full notes: `docs/releases/v0.7.3.md` (also the GitHub Release body).

1. **RIS/BibTeX import integrity** — every source occurrence is preserved and classified; repository-skipped rows are auditable.
2. **Source-record provenance and auditability** — DOI text/status, fingerprints, source identity, canonical link, match reason, and recovery status are persisted.
3. **Duplicate review and canonical DOI handling** — candidates remain human-controlled; DOI re-imports resolve through supersession chains to the active canonical.
4. **Recovery and reconciliation safeguards** — explicit approvals, failed-import diagnostics, candidate snapshots, deterministic reconciliation, and safe errors for broken/cyclic chains.
5. **PRISMA source-aware accounting** — source records, repeated occurrences, exact DOI links, canonical/merged/recovered records, pending groups, and historical fallback remain distinct and consistent.
6. **Duplicate-group and PRISMA performance improvements** — indexed candidate generation and request-scoped reuse replace the quadratic loop and redundant builder executions.
7. **Regression tests and validation** — R1–R5 integration, migrations, recovery, duplicate review, PRISMA, DOI integrity, equivalence, and bounded-comparison coverage.
8. **Known limitations** — documented below and in the release notes.

**The historical 508-source/62-row RIS discrepancy is explicitly NOT claimed as resolved.**

## 7. Tag SHA

```text
Annotated tag object: ec12d7e6a64337c742a652ab72650f35dfec6cef
Peeled commit:        260744f34940cec7ecd8cedc882cee139c5e09cd
Tag message:          SLR Platform v0.7.3
```

Remote verification:

```text
ec12d7e6a64337c742a652ab72650f35dfec6cef  refs/tags/v0.7.3
260744f34940cec7ecd8cedc882cee139c5e09cd  refs/tags/v0.7.3^{}
```

## 8. GitHub Release

| Field | Value |
|---|---|
| Name | SLR Platform v0.7.3 |
| Tag | `v0.7.3` |
| Target | `main` / `260744f` |
| Draft | No |
| Prerelease | No |
| Published | 2026-10-27T08:51:10Z |
| URL | https://github.com/jaroslawoleradzki-ctrl/slr-platform/releases/tag/v0.7.3 |

## 9. Homelab mirror verification

Initial synchronization after release:

| Ref | Homelab SHA |
|---|---|
| `refs/heads/main` | `260744f34940cec7ecd8cedc882cee139c5e09cd` |
| `refs/heads/development` | `9751f18197337aa8faf43cfe9268cc0006bce258` |
| `refs/tags/v0.7.3` | `ec12d7e6a64337c742a652ab72650f35dfec6cef` |
| `refs/tags/v0.7.3^{}` | `260744f34940cec7ecd8cedc882cee139c5e09cd` |

Pushes were non-force. No remote branch was deleted. After this administrative report commit passes development CI, `development` is re-synchronized to Homelab; `main` and the tag remain at `260744f`.

## 10. Remaining limitations

1. **Historical 508/62 RIS discrepancy remains NOT VERIFIED and NOT resolved.** Original RIS files/source rows are unavailable.
2. Performance evidence uses deterministic synthetic A–E fixtures; the audit’s original 578-publication project is not replayable.
3. A worst-case 2000-title near-identical family remains slower than normal/mixed data; no candidate cutoff or silent loss is used.
4. Production deployment, production migrations, and production data reconciliation were not performed.
5. CI annotates a non-blocking Node.js 20 deprecation for `actions/checkout@v4`; all jobs still pass.
6. The original local `development` worktree remains at `e97c8b1` with its pre-existing user changes untouched; `origin/development` is the authoritative release line.

## 11. Deployment readiness

- Release code is tagged and published.
- Migrations `0034`–`0037` are included and validated on disposable databases.
- **No production deployment or production migration was executed.**
- Deployment requires the normal controlled rollout: backup, migration run, application restart, and post-deploy verification.
- **Production deployed: NO.**

## 12. Warnings

- GitHub Actions Node.js 20 deprecation annotation (non-blocking).
- `uv.lock` carried a stale editable version `0.7.1` before this release; it is corrected to `0.7.3`.
- The report commit is administrative and intentionally does not move the immutable `v0.7.3` tag.
