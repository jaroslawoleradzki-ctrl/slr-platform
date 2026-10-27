# SLR Agent Engineering Security Hardening Report

- **Date:** 2026-10-27
- **Branch:** `feature/slr-agent-engineering-foundation`
- **Worktree:** `/home/cloud/dev/wt-slr-agent-foundation`
- **Audited baseline:** `10239bb29547bf1a33188976da8e30af9cf0afc9`
- **OpenSpec change:** `agent-engineering-hardening`
- **Mode:** BUILD, development infrastructure only
- **Application behavior changed:** NO
- **Production changed:** NO
- **Research data changed:** NO

## 1. Executive summary

The hardening change replaces the foundation's broad shell permissions with
default-deny shell rules and narrow role allowlists, protects research data and
governance files, adds effective-permission tests, and adds the missing CI gates
for diff hygiene, pinned OpenSpec validation, and migration safety. It also fixes
the model-cost/429 documentation, TDD evidence policy, Definition of Done, QA
frontend commands, branch conventions, and the low-severity documentation items.

Local validation is green:

- 93 configuration/effective-permission tests passed;
- 2,638 backend tests passed;
- 39 migration/reconciliation tests passed;
- Ruff, mypy, TypeScript, 342 frontend tests, and the production build passed;
- OpenSpec strict and archived validation passed;
- all five agents and all six project skills were discovered;
- the migration-safety guard and CI runner-policy checks passed.

GitHub Actions had not run when this report was first written. The final status
therefore remains **PASS WITH CONDITIONS** until the PR checks are green. Do not
merge on local evidence alone.

## 2. Security design

See [`docs/agents/SECURITY_MODEL.md`](../agents/SECURITY_MODEL.md) and
[`scripts/agent/README.md`](../../scripts/agent/README.md).

- Every agent starts with `shell: *` = `deny`.
- Role allowlists cover only the commands the role needs.
- Deployment wrappers, `sudo`, `ssh`, Docker compose, general interpreters,
  database tools, and destructive file commands are not allowlisted.
- `scripts/agent/safe_pytest.sh` forces a disposable `SLR_DATABASE_PATH` and
  `TMPDIR`.
- Compound commands using `;`, `&&`, `&`, pipes, command substitution,
  backticks, redirection, or newlines are denied after the allowlist.
- OpenCode permissions are not a filesystem sandbox. The residual risk is
  documented rather than hidden.

## 3. Remediation matrix

| ID | Original severity | Root cause | Changed files | Remediation | Validation evidence | Status |
|---|---|---|---|---|---|---|
| C-01 | CRITICAL | Broad `shell: *` allow; narrow deploy-script deny/ask was bypassable via `bash`, `sh`, `./`, `sudo`, `ssh`, Docker compose | `.opencode/agents/slr-developer.md`, `.opencode/agents/slr-release-engineer.md`, `docs/agents/SECURITY_MODEL.md` | Default-deny shell; deploy wrappers/`sudo`/`ssh`/Docker denied; exact release script `ask`; developer cannot execute it | Effective-permission tests cover every wrapper and merged OpenCode rules | FIXED |
| C-02 | CRITICAL | `edit: data/**` ask did not constrain shell; `python3`, `sqlite3`, `cp`, `mv`, `rm` were allowed | `.opencode/agents/slr-developer.md`, `scripts/agent/safe_pytest.sh`, `scripts/agent/README.md` | Data/projects/database/backup edits and reads denied; general interpreters and file tools removed from shell; disposable test wrapper added | Database-mutation command tests; wrapper test; wrapper run passed | FIXED |
| H-01 | HIGH | Developer could edit its own agent file, `AGENTS.md`, the config test, `pyproject.toml`, and CI scripts | `.opencode/agents/slr-developer.md`, `tests/unit/test_agent_foundation_configuration.py` | Governance paths are `ask`; deploy script `deny`; data/secrets deny | Governance edit tests assert ask/deny; ordinary source remains allow | FIXED |
| H-02 | HIGH | Denylist missed `git restore`, `git checkout --`, worktree removal, branch deletion, `git -C`, `rm -fr`/`rm -r` | All five agents, `.opencode/skills/slr-git-workflow/SKILL.md`, `docs/agents/SECURITY_MODEL.md` | Default-deny shell; destructive commands not allowlisted; compound-command denies | Destructive Git/file command tests pass for developer and release | FIXED |
| H-03 | HIGH | Developer could tag/publish; release could merge/checkout main/use `gh api` without approval | `.opencode/agents/slr-developer.md`, `.opencode/agents/slr-release-engineer.md` | Developer tag/`gh`/merge/checkout denied; release merge/push/tag/`gh release`/`gh api`/`gh pr` ask | Release-action tests and merged-rule tests | FIXED |
| H-04 | HIGH | Tests inspected declared strings; hardcoded model allow-list did not detect provider removal | `tests/unit/test_agent_foundation_configuration.py`, `docs/reviews/SLR_AGENT_ENGINEERING_FOUNDATION_REPORT.md` | Effective `fnmatch` last-match evaluator; command-family tests; merged OpenCode permissions test; live `opencode models` test when CLI is available; report overclaims corrected | 93 effective/contract tests; merged OpenCode rules test; live catalog check passed locally | FIXED |
| H-05 | HIGH | Read-only agents had shell `cat`/`sed`/`find`/`rg`, bypassing the read-tool `.env` ask | All five agents, `docs/agents/SECURITY_MODEL.md` | Shell file readers removed; `read` denies for `.env`, secrets, keys, data; `.env.example` allow; tests added | Secret-read tests pass; shell file-reader tests deny | FIXED |
| M-01 | MEDIUM | CI lacked `git diff --check`, OpenSpec strict validation, and migration safety | `.github/workflows/ci.yml`, `docs/agents/QUALITY_GATES.md` | CI adds diff hygiene, pinned `@fission-ai/openspec@1.15.0` job, migration-safety step; branch triggers aligned | YAML parses; runner-policy script passes; local OpenSpec passes; CI pending | PARTIALLY FIXED |
| M-02 | MEDIUM | TDD evidence requirement was weak; red-first not enforced | `AGENTS.md`, `docs/agents/WORKFLOW.md`, `.opencode/skills/slr-testing/SKILL.md` | Reports must record failing command/output, green command/output, refactor verification, and test diff; limitation documented | Policy reviewed; this hardening change is non-behavioral configuration and uses the proportionate exception | FIXED |
| M-03 | MEDIUM | Paid default/fallback contradicted "no paid credits without authorization" | `docs/agents/MODEL_ROUTING.md`, `docs/agents/README.md`, `AGENTS.md` | Free `opencode/mimo-v2.6-flash-free` fallback; developer model documented as pre-authorized; paid fallback requires approval | Live catalog check includes configured models; fallback documented | FIXED |
| M-04 | MEDIUM | No operational HTTP 429 procedure | `docs/agents/MODEL_ROUTING.md`, `AGENTS.md` | Retry/backoff, free fallback, paid approval, NOT VERIFIED rule documented | Documentation inspection | FIXED |
| M-05 | MEDIUM | No migration-safety guard | `scripts/ci/check_migration_safety.py`, `tests/unit/test_migration_safety_tooling.py`, `.github/workflows/ci.yml`, skills/docs | Rejects modified/deleted existing migrations; flags destructive SQL without explicit marker | Migration guard passed; unit tests for destructive/non-destructive SQL pass | FIXED |
| M-06 | MEDIUM | Definition of Done allowed PASS without CI | `AGENTS.md`, `docs/agents/QUALITY_GATES.md`, foundation report | CI green required for merge-ready; PASS/PASS WITH CONDITIONS/BLOCK/NOT VERIFIED semantics | Policy inspection; foundation report corrected to PASS WITH CONDITIONS | FIXED |
| M-07 | MEDIUM | Release engineer could edit dependency/build config and audit reports | `.opencode/agents/slr-release-engineer.md`, `tests/unit/test_agent_foundation_configuration.py` | Metadata allow; `pyproject.toml`/`package.json`/OpenSpec ask; audit reports deny | Release edit-scope tests pass | FIXED |
| M-08 | MEDIUM | QA allowlist did not match documented `cd frontend` workflow | `.opencode/agents/slr-qa.md`, skills/docs | QA uses `npm --prefix frontend ...`; docs aligned; tests assert allow/deny | QA frontend command tests pass | FIXED |
| L-01 | LOW | `docs/session-start.md` still said no commit/push | `docs/session-start.md` | Review-only vs implementation commit/push scoped to `AGENTS.md` | Documentation inspection | FIXED |
| L-02 | LOW | CI trigger docs omitted integration branch | `.github/workflows/ci.yml`, `docs/agents/QUALITY_GATES.md` | `integration/**` trigger and docs aligned | YAML parse and docs inspection | FIXED |
| L-03 | LOW | Hardcoded protected worktree path | `AGENTS.md`, `docs/agents/WORKFLOW.md`, `.opencode/skills/slr-git-workflow/SKILL.md`, `openspec/config.yaml` | Replaced with `git worktree list` / protected-checkout wording | `grep` found no remaining protected absolute path in guidance | FIXED |
| L-04 | LOW | Config test did not check referenced paths or OpenSpec archive | `tests/unit/test_agent_foundation_configuration.py` | Path-existence tests; archived-change/main-spec tests | Path and archive tests pass | FIXED |
| L-05 | LOW | CI cleanup hardcoded `/dev/shm` | `.github/workflows/ci.yml` | `TEST_ROOT` exported to `$GITHUB_ENV`; cleanup removes actual path | YAML inspection | FIXED |
| L-06 | LOW | Generated OpenSpec artifacts could drift | `docs/agents/WORKFLOW.md`, `openspec/config.yaml`, CI | Pinned CLI; `openspec update` review policy; CI validates generated state | OpenSpec strict/archived validation passes | FIXED |
| L-07 | LOW | Branch prefixes omitted `integration/` | `AGENTS.md`, `.opencode/skills/slr-git-workflow/SKILL.md`, `.opencode/skills/slr-release/SKILL.md`, CI | `integration/` documented as release-specific; CI uses `integration/**` | Documentation and YAML inspection | FIXED |

**Remaining at first report write:** 1 medium (M-01, awaiting CI). No critical or
high findings remain in the configuration tests.

## 4. Effective-permission tests

`tests/unit/test_agent_foundation_configuration.py` now:

- evaluates ordered rules with last-match wildcard semantics;
- asserts every agent starts with `shell: *` = `deny`;
- covers `bash`, `sh`, `./`, `sudo`, `ssh`, `docker`, `docker-compose`, and
  `env` deployment forms;
- covers `python3`, `sqlite3`, `cp`, `mv`, `rm`, `truncate`, and `cat` against
  `data/slr-platform.db`;
- covers `git reset`, `clean`, `stash`, `restore`, `checkout --`, worktree
  removal, branch deletion, and `git -C` variants;
- covers `git tag`, `gh release`, `gh api`, `gh pr`, merge, and main checkout;
- covers `cat .env`, secret paths, keys, and read-only agent file readers;
- covers compound commands with `;`, `&&`, `&`, pipes, `$()`, backticks,
  redirection, and newlines;
- covers QA frontend commands with `npm --prefix frontend`;
- queries `opencode debug agents` merged permissions when the CLI is available;
- queries `opencode models` when the CLI is available.

A live model prompt was **not** executed. The previous free-tier quota was
exhausted, and no paid call was authorized. End-to-end agent behavior therefore
remains **NOT VERIFIED**; the tests validate configuration rules, not model
reasoning.

## 5. OpenCode discovery

| Item | Result |
|---|---|
| `opencode debug agents` | 5/5 `slr-*` agents loaded |
| `/api/agent` | 12 agents total, 5 `slr-*` |
| `/api/skill` | 16 skills total, 6 `slr-*` |
| `/api/command` | 9 commands total, 7 `opsx-*` |

Models loaded:

- `slr-architect`: `opencode/nemotron-3-ultra-free`
- `slr-developer`: `opencode-go/muse-spark-1.3-contributor`
- `slr-qa`: `opencode/nemotron-3.5-lightning-free`
- `slr-research-reviewer`: `opencode/nemotron-3-ultra-free`
- `slr-release-engineer`: `opencode/nemotron-3.5-lightning-free`

## 6. OpenSpec results

```text
openspec validate --all --strict       -> 2 passed, 0 failed
openspec validate --archived --strict  -> 1 passed, 0 failed
openspec doctor                        -> root OK
```

The hardening change is `openspec/changes/agent-engineering-hardening` with a
proposal, spec delta, design, and tasks. It will be archived after the final
validation, per the workflow.

## 7. Model cost routing

- Developer default remains `opencode-go/muse-spark-1.3-contributor`, documented
  as pre-authorized for implementation tasks.
- Fallback is the free `opencode/mimo-v2.6-flash-free`.
- Other paid models require explicit authorization.
- HTTP 429 procedure: retry once, use the free fallback, stop and report
  NOT VERIFIED if still unavailable, use paid only with approval.
- No model routing was changed without documenting the decision.

## 8. CI changes

`.github/workflows/ci.yml` now:

- triggers on `main`, `development`, and `integration/**`;
- runs `git diff --check` against the PR base or `HEAD^`;
- runs an `openspec` job with pinned `@fission-ai/openspec@1.15.0` and both
  strict validations;
- runs `scripts/ci/check_migration_safety.py` in the backend job;
- stores and removes the actual temporary test directory, including the
  `RUNNER_TEMP` fallback;
- keeps the dedicated self-hosted runner labels and policy check.

## 9. Migration guard

`scripts/ci/check_migration_safety.py`:

- compares `migrations/` against a base ref;
- fails on modified, renamed, or deleted existing migrations;
- scans added migrations for `DROP TABLE`, `DROP COLUMN`, `ALTER ... DROP`,
  `DROP INDEX`, `TRUNCATE`, and `DELETE FROM`;
- requires the explicit marker `migration-safety: approved-destructive` for
  destructive SQL in an added migration;
- does not connect to any database and does not execute SQL.

The guard passed locally with no migration changes. Unit tests cover destructive
and non-destructive SQL patterns.

## 10. Test results

| Gate | Command | Result |
|---|---|---|
| Configuration/effective permissions | `bash scripts/agent/safe_pytest.sh tests/unit/test_agent_foundation_configuration.py` | PASS — 93 passed |
| Migration tooling | `pytest tests/unit/test_migration_safety_tooling.py` | PASS |
| Full backend | `bash scripts/agent/safe_pytest.sh` | PASS — 2,638 passed, 1 warning, 96.04s |
| Migration subset | `bash scripts/agent/safe_pytest.sh tests/unit/repositories tests/integration -k "migration or reconciliation"` | PASS — 39 passed, 311 deselected |
| Ruff | `uv run --frozen --no-sync ruff check --no-cache app tests scripts` | PASS |
| Mypy | `uv run --frozen --no-sync mypy --cache-dir=/tmp/mypy-audit app` | PASS — 202 files |
| TypeScript | `npm --prefix frontend run type-check` | PASS |
| Frontend tests | `npm --prefix frontend test` | PASS — 44 files, 342 tests |
| Frontend build | `npm --prefix frontend run build` | PASS — chunk-size warning only |
| OpenSpec | `openspec validate --all --strict`; `--archived --strict` | PASS |
| Migration safety | `python scripts/ci/check_migration_safety.py --base-ref origin/development` | PASS |
| CI runner policy | `bash scripts/ci/check_runner_policy.sh` | PASS |
| GitHub Actions | PR checks | PENDING / NOT VERIFIED |
| Live model execution | — | NOT VERIFIED (quota; no paid call) |

No application behavior, production data, or deployment was changed.

## 11. Remaining risks

1. **OpenCode permissions are not a sandbox.** An allowed test or script can
   still perform filesystem operations. The default-deny allowlists and
   compound-command denials reduce the attack surface but do not prove
   isolation.
2. **CI is the final gate.** Local results do not prove the self-hosted runner
   environment. Do not merge until the PR checks are green.
3. **Live model execution is not verified.** Free-tier quota prevented a live
   agent prompt; no paid call was made. Model reasoning and live permission
   prompts remain unverified.
4. **Model catalog drift.** The live catalog test runs only where OpenCode is
   installed; CI may skip it if the CLI is absent.
5. **Migration guard scope.** The guard detects common destructive SQL patterns
   and edited applied migrations; it is not a full SQL analyzer.
6. **TDD red-first proof.** The policy now requires evidence; a green CI run
   still cannot prove the test was written first.
7. **Generated OpenSpec artifacts.** They remain version-controlled and must be
   refreshed with the pinned CLI.

## 12. Merge readiness

- Configuration validity: PASS
- Skill discoverability: PASS
- Agent discoverability: PASS
- Effective permission tests: PASS
- Research data protection: PASS (permission-level; no sandbox claim)
- Deployment protection: PASS (permission-level; wrappers denied)
- OpenSpec: PASS
- Backend tests: PASS
- Frontend tests/build: PASS
- GitHub Actions: PENDING / NOT VERIFIED
- Live model execution: NOT VERIFIED

**Overall before CI:** **PASS WITH CONDITIONS**. The branch is ready for
independent review, not for merge. Update this report to **PASS** only after the
PR's CI checks are green.

## 13. Independent review request

Please independently verify:

- the default-deny rules and wrapper denials;
- the effective-permission tests are not merely string-presence checks;
- the migration guard behavior;
- that no application or research data changed;
- the CI run on the exact PR commit.
