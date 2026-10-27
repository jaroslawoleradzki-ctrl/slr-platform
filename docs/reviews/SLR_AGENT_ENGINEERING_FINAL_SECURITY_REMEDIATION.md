# SLR Agent Engineering — Final Security Remediation

- **Date:** 2026-10-27
- **Mode:** BUILD (focused security remediation)
- **Branch:** `feature/slr-agent-engineering-foundation`
- **Worktree:** `/home/cloud/dev/wt-slr-agent-foundation`
- **Target:** `development`
- **Audited baseline:** `63a01ffc5f26c883c6754a748138dc1393df1999`
- **Pull request:** #5 — https://github.com/jaroslawoleradzki-ctrl/slr-platform/pull/5
- **Audit source:** `/tmp/SLR_AGENT_ENGINEERING_FINAL_AUDIT.md`
- **Application behavior changed:** NO
- **Research data changed:** NO
- **Production configuration changed:** NO
- **Merged / released / deployed:** NO

---

## 1. Executive summary

The second audit found that broad shell permissions for `git diff*`, `git log*`
and `git show --stat*` allowed arbitrary file reads (`--no-index`), arbitrary
file writes (`--output`) and history content (`-p`) for all five agents. It also
found that QA and the release engineer could run mutating Ruff commands, that
the research reviewer could use SQLite shell escapes, and that CI skipped the
OpenCode-dependent security tests.

This remediation closes those permission-rule bypasses:

- direct `git` inspection commands are removed from all five agents;
- every Git inspection operation goes through a new fail-closed wrapper,
  `scripts/agent/safe_git_inspect.py`;
- QA and the release engineer may run only the exact read-only Ruff command;
- `sqlite3` shell access is removed from every agent;
- CI installs a pinned, checksum-verified OpenCode v2.2.0 binary job-locally and
  runs the merged effective-permission tests as a mandatory gate;
- the model-catalog test is split into a mandatory static check and a
  deterministic standalone free-model check; paid-provider live verification is
  explicitly distinguished as **NOT VERIFIED** in CI.

Local results are green:

- 130 configuration/effective-permission and wrapper tests;
- 2,676 backend tests;
- 44 frontend files / 342 tests, TypeScript, and production build;
- Ruff, mypy, migration safety, diff hygiene, OpenSpec strict and archived
  validation, and the CI runner policy.

The remediation is pushed and verified by GitHub Actions run `40513341817` on
`f91d1db8278ce3abb1bd18e36afd3c9e3d06c82a`: all four jobs passed, including the
mandatory sealed permission tests (130 passed) and the full backend suite
(2,676 passed). The run also verified that the pre-existing research database
under `data/` was unchanged by the test suite.

**Assessment:** **PASS WITH CONDITIONS** for the targeted security remediation.
The conditions are non-blocking residuals: live model execution remains
unverified (provider quota), paid-provider live catalog verification is not
available in CI, and OpenCode permissions remain a permission layer rather than
an OS sandbox.

---

## 2. Root cause of the `git diff` bypass

The previous configuration allowlisted broad command prefixes:

```yaml
- action: shell
  resource: "git diff*"
  effect: allow
- action: shell
  resource: "git log*"
  effect: allow
- action: shell
  resource: "git show --stat*"
  effect: allow
```

OpenCode evaluates shell permission rules against the **parsed command node
text**, not against a semantic command name. The shell tool parses the command
with tree-sitter and checks each command node; it resolves the working directory
and `cd` targets for `external_directory`, but it does **not** apply the native
`read`/`edit` permissions to file arguments of an allowed command.

Therefore, once a command matched an allowed prefix, all of its options were
inside the trust boundary:

- `git diff --no-index /dev/null .env` matched `git diff*` and printed `.env`;
- `git diff --no-index /dev/null /home/cloud/.ssh/id_rsa` matched `git diff*`
  and read an external file with no `external_directory` prompt;
- `git diff --output=data/slr-platform.db` matched `git diff*` and truncated the
  research database;
- `git diff --output=.opencode/agents/slr-developer.md` matched `git diff*` and
  silently overwrote a governance file;
- `git log -p -- .env` matched `git log*` and printed history content.

The previous tests checked specific command strings but not these options, so
they passed while the bypasses existed. Adding a few deny patterns would not be
sufficient because the allow prefix would remain and the option surface is
open-ended. The fix removes the broad allows entirely and replaces them with an
explicit-operation wrapper.

---

## 3. Security design selected

### 3.1 Fail-closed Git inspection wrapper

New file: `scripts/agent/safe_git_inspect.py` (stdlib only, executable).

Supported operations:

```text
status
diff
log
show
branch-current
worktree-list
```

Properties:

- explicit operation allowlist;
- explicit per-operation option allowlists; unknown options are rejected;
- rejects `--no-index`, `--output`, `--ext-diff`, `--textconv`, `--config`,
  `-c`, `--git-dir`, `--work-tree`, `-O`, `--exec-path`, upload/receive-pack,
  and external helpers;
- paths must be repository-relative and must not contain traversal (`..`),
  glob characters (`*`, `?`, `[`), pathspec magic (`:`), backslashes, or control
  characters;
- paths must resolve inside the worktree; symlink escapes are rejected;
- resolved paths are re-checked for protected components;
- protected paths: `.env*`, `data/`, `projects/`, `secrets/`, `backups/`, `.git`,
  `*.db`, `*.sqlite*`, `*.pem`, `*.key`;
- revisions must resolve to commits; `rev:path` blob syntax is rejected;
- `log -p`/`--patch` and patch-producing `show` forms are rejected;
- unfiltered `diff`/`log`/`show` output additionally passes Git exclude
  pathspecs for protected paths, so a tracked protected file is not exposed;
- Git runs with argument arrays only, never `shell=True` or `eval`;
- Git environment is sanitised: local `GIT_*` variables removed, global/system
  config disabled, pager disabled, optional index locks disabled, fsmonitor
  disabled, external diff and textconv disabled;
- no hooks, external helpers, or repository-configured commands are invoked.

The wrapper is not a sandbox. It narrows the Git option surface; it cannot
prevent an allowed test or build command from running repository code.

### 3.2 Direct Git commands removed

All five agents now have only this Git inspection allow:

```yaml
- action: shell
  resource: "python3 scripts/agent/safe_git_inspect.py*"
  effect: allow
```

Direct `git status`, `git diff`, `git log`, `git show`, `git branch --show-current`
and `git worktree list` are denied. Write operations (`git add`, `git commit`,
`git push`) remain `ask` for the developer and release engineer. Release
actions remain `ask`; force-push remains `deny`.

This also closes the `git status`/`core.fsmonitor` hook vector: the wrapper
forces `core.fsmonitor=false` and a clean Git environment.

### 3.3 Ruff is read-only for QA and release

`slr-qa` and `slr-release-engineer` may run exactly:

```bash
uv run --frozen --no-sync ruff check app tests scripts
```

`ruff check --fix`, `ruff check --unsafe-fixes`, `ruff format`, and any extra
arguments do not match the exact allow and fall back to the default-deny shell
rule. The developer may still use `ruff --fix`/`ruff format` intentionally.

### 3.4 SQLite shell removed

The `sqlite3 -readonly*` allow was removed from `slr-research-reviewer` and is
not present for any other agent. SQLite dot-commands such as `.shell` and
`.output` can execute commands or write files, so they are not safe for a
read-only reviewer. The research reviewer uses native read tools, application
reports, and disposable tests instead.

### 3.5 CI security verification

The backend job now:

1. downloads the pinned OpenCode v2.2.0 release asset for the runner
   architecture;
2. verifies it against the published `SHA256SUMS`;
3. extracts it under `$RUNNER_TEMP/opencode-cli` (no global host install);
4. asserts `opencode v2.2.0`;
5. exports `OPENCODE_BIN` and `REQUIRE_OPENCODE_CLI=1`;
6. runs the configuration/effective-permission and wrapper tests in an isolated
   `HOME`/XDG directory;
7. runs the full pytest suite with the same isolated environment.

The mandatory merged-permission test **fails** rather than skips when the CLI is
missing and `REQUIRE_OPENCODE_CLI=1`. I verified this fail-closed behaviour with
a deliberately invalid `OPENCODE_BIN`.

Model verification is split:

- **mandatory static check:** every agent model is syntactically valid and in
  the reviewed allowlist;
- **mandatory standalone catalog check:** every free `opencode/*` model used by
  an agent is present in the pinned CLI's deterministic catalog (the free
  fallback is checked too);
- **paid provider live catalog:** requires provider credentials and is not a
  hard CI dependency; it is documented as **NOT VERIFIED**, not silently
  skipped.

---

## 4. Changed files

| File | Change |
|---|---|
| `scripts/agent/safe_git_inspect.py` | New fail-closed Git inspection wrapper |
| `scripts/agent/README.md` | Wrapper usage and security properties |
| `docs/agents/SECURITY_MODEL.md` | Git wrapper, Ruff, SQLite, residual-risk update |
| `AGENTS.md` | Diff hygiene uses the wrapper; worktree guidance |
| `docs/agents/QUALITY_GATES.md` | Agent diff-hygiene command and gate table |
| `docs/agents/WORKFLOW.md` | Human setup vs agent wrapper inspection |
| `.opencode/agents/slr-architect.md` | Direct Git removed; wrapper allow |
| `.opencode/agents/slr-developer.md` | Direct Git removed; wrapper allow |
| `.opencode/agents/slr-qa.md` | Direct Git removed; wrapper allow; exact Ruff allow |
| `.opencode/agents/slr-research-reviewer.md` | Direct Git and `sqlite3` removed; wrapper allow |
| `.opencode/agents/slr-release-engineer.md` | Direct Git removed; wrapper allow; exact Ruff allow |
| `.opencode/skills/slr-git-workflow/SKILL.md` | Wrapper commands; direct Git denied |
| `.opencode/skills/slr-testing/SKILL.md` | Wrapper diff check |
| `.opencode/skills/slr-release/SKILL.md` | Wrapper status/diff commands |
| `.github/workflows/ci.yml` | Pinned CLI install; mandatory security tests; isolated HOME; before/after data database isolation check |
| `tests/unit/test_agent_foundation_configuration.py` | Exact matcher; bypass, Ruff, SQLite, wrapper, merged-rule tests |
| `tests/unit/test_agent_git_inspection_wrapper.py` | New wrapper unit tests |

No `app/`, `frontend/`, `migrations/`, `data/`, `projects/`, `pyproject.toml`,
`compose.yaml`, or deployment file was changed.

---

## 5. Effective permission test matrix

Evaluated with OpenCode v2.2.0's actual matcher (`findLast`, wildcard with `s`
flag, default `ask`) against the merged rules reported by
`opencode --standalone debug agents`.

### 5.1 Previously bypassable commands

| Command | architect | developer | qa | research-reviewer | release-engineer |
|---|---|---|---|---|---|
| `git diff --no-index /dev/null .env` | deny | deny | deny | deny | deny |
| `git diff --no-index /dev/null secrets/token.txt` | deny | deny | deny | deny | deny |
| `git diff --no-index /dev/null /home/cloud/.ssh/id_rsa` | deny | deny | deny | deny | deny |
| `git diff --output=data/slr-platform.db` | deny | deny | deny | deny | deny |
| `git diff --output=AGENTS.md` | deny | deny | deny | deny | deny |
| `git diff --output=.opencode/agents/slr-developer.md` | deny | deny | deny | deny | deny |
| `git diff --output=scripts/agent/safe_pytest.sh` | deny | deny | deny | deny | deny |
| `git log -p -- .env` | deny | deny | deny | deny | deny |
| `git show HEAD:.env` | deny | deny | deny | deny | deny |
| `sqlite3 -readonly data/slr-platform.db '.shell id'` | deny | deny | deny | deny | deny |
| `uv run --frozen --no-sync ruff check --fix app` | deny | **allow** | deny | deny | deny |
| `uv run --frozen --no-sync ruff format app/x.py` | deny | **allow** | deny | deny | deny |

The developer remains allowed to run mutating Ruff intentionally; QA and release
are read-only. This is the intended least-privilege split.

### 5.2 Replacement operations

| Command | All five agents |
|---|---|
| `python3 scripts/agent/safe_git_inspect.py status --short` | allow |
| `python3 scripts/agent/safe_git_inspect.py diff --stat` | allow |
| `python3 scripts/agent/safe_git_inspect.py diff HEAD~1 -- app/services/example.py` | allow |
| `python3 scripts/agent/safe_git_inspect.py log --oneline -n 20` | allow |
| `python3 scripts/agent/safe_git_inspect.py show --stat HEAD` | allow |
| `python3 scripts/agent/safe_git_inspect.py branch-current` | allow |
| `python3 scripts/agent/safe_git_inspect.py worktree-list` | allow |

### 5.3 Unchanged hard boundaries

| Command | developer | release-engineer |
|---|---|---|
| `bash scripts/deploy_ai_node.sh` | deny | deny |
| `sudo docker compose up -d` | deny | deny |
| `ssh cloud@ai-node ...` | deny | deny |
| `scripts/deploy_ai_node.sh` (exact) | deny | ask |
| `git reset --hard` | deny | deny |
| `git restore .` | deny | deny |
| `git worktree remove ...` | deny | deny |
| `git branch -D ...` | deny | deny |
| `git tag ...` | deny | ask |
| `git merge ...` | deny | ask |
| `git checkout main` | deny | ask |
| `gh release ...` | deny | ask |
| `gh api ...` | deny | ask |
| `git push --force` | deny | deny |

### 5.4 Wrapper unit tests

`tests/unit/test_agent_git_inspection_wrapper.py` uses disposable repositories
and synthetic files. It verifies:

- safe `status`, `diff`, `log`, `show`, `branch-current`, `worktree-list`;
- rejection of `--no-index`, `--output`, `--ext-diff`, `--textconv`,
  `--config`, `-c`, `--git-dir`, `--work-tree`, `-O`, submodule/indicator
  options, and unknown options;
- rejection of `.env`, `data/`, `projects/`, `secrets/`, absolute paths,
  traversal, glob/pathspec magic, and symlink escapes;
- rejection of `log -p`/`--patch`, patch-producing `show`, and `rev:path`;
- exclusion of tracked protected paths from unfiltered `diff` output;
- no output file is created by a rejected `--output` command;
- operation from a repository subdirectory.

All 10 wrapper tests pass.

---

## 6. CI security test results

### Local CI-equivalent verification

Run with the pinned v2.2.0 binary, `REQUIRE_OPENCODE_CLI=1`, an isolated
`HOME`/XDG tree, and `--standalone`:

```bash
OPENCODE_BIN=/tmp/oc-dist/opencode \
REQUIRE_OPENCODE_CLI=1 \
HOME=/tmp/oc-ci-home2 \
XDG_CONFIG_HOME=/tmp/oc-ci-home2/.config \
XDG_DATA_HOME=/tmp/oc-ci-home2/.local/share \
XDG_CACHE_HOME=/tmp/oc-ci-home2/.cache \
XDG_STATE_HOME=/tmp/oc-ci-home2/.local/state \
uv run --frozen --no-sync pytest -q -p no:cacheprovider -rs \
  tests/unit/test_agent_foundation_configuration.py \
  tests/unit/test_agent_git_inspection_wrapper.py
```

Result: **130 passed** in 6.88 s.

Fail-closed check with a missing CLI:

```bash
OPENCODE_BIN=/tmp/does-not-exist REQUIRE_OPENCODE_CLI=1 \
uv run --frozen --no-sync pytest -q -p no:cacheprovider \
  tests/unit/test_agent_foundation_configuration.py \
  -k merged_opencode_permissions_enforce_hard_boundaries
```

Result: **1 failed** with
`OpenCode CLI is required for security verification but was not found` — the
mandatory test fails instead of skipping, as intended.

### Pinned CLI installation verification

- Release: `v2.2.0`;
- asset: `opencode-linux-x64.tar.gz`;
- SHA256 verified against the published `SHA256SUMS`
  (`6d597970a8cc448f1b9a9f645532584b339dd3ab9583bb5f063f13d83e54768f`);
- extracted binary reports `opencode v2.2.0`;
- installed only under a temporary directory, not globally.

### GitHub Actions

The workflow now runs the pinned installation and the mandatory security tests
in the backend job.

- **Green run:** `40513341817` on `f91d1db8278ce3abb1bd18e36afd3c9e3d06c82a`;
  all four jobs passed:
  - `CI runner policy` — pass;
  - `OpenSpec (pinned CLI)` — pass;
  - `Backend (Python 3.12)` — pass;
  - `Frontend (Node 22)` — pass.
- **Mandatory security step:** `130 passed in 7.11s` with
  `OPENCODE_BIN`/`REQUIRE_OPENCODE_CLI=1` and the isolated HOME.
- **Full backend suite in CI:** `2676 passed, 1 warning` in 102.50 s.
- **Data isolation:** `data/ database state unchanged by tests`.
- **Migration safety:** passed.
- **OpenSpec:** 1 spec and 2 archived changes passed.
- **Pinned CLI:** downloaded from the v2.2.0 release, checksum verified against
  `SHA256SUMS`, installed under `$RUNNER_TEMP/opencode-cli`, and asserted as
  `opencode v2.2.0`.

An earlier run, `40512305838`, failed **after** all 2,676 tests passed because
the old CI check required `data/` to be empty; the persistent self-hosted runner
has a pre-existing ignored `data/slr-platform.db`. The check was corrected in
`f91d1db` to compare the path/size/mtime state before and after pytest and fail
only if tests create or modify a database. The corrected run above is green.
The pre-existing research database was not deleted, read, or modified.

---

## 7. Regression results

| Gate | Exact command | Result |
|---|---|---|
| Config/effective permissions | `pytest tests/unit/test_agent_foundation_configuration.py` | **PASS** — 119 passed |
| Wrapper tests | `pytest tests/unit/test_agent_git_inspection_wrapper.py` | **PASS** — 10 passed |
| Full backend | `bash scripts/agent/safe_pytest.sh` | **PASS** — 2,676 passed, 1 warning, 108.16 s |
| Ruff | `uv run --frozen --no-sync ruff check --no-cache app tests scripts` | **PASS** — all checks passed |
| Mypy | `uv run --frozen --no-sync mypy app` | **PASS** — 202 files, no issues |
| Migration safety | `python scripts/ci/check_migration_safety.py --base-ref origin/development` | **PASS** — no migration changes |
| Diff hygiene | `python3 scripts/agent/safe_git_inspect.py diff --check` | **PASS** |
| Frontend TypeScript | `npx tsc --noEmit` (in `frontend/`) | **PASS** |
| Frontend tests | `npx vitest run` | **PASS** — 44 files, 342 tests |
| Frontend build | `npx vite build --outDir /tmp/slr-remediation-build --emptyOutDir` | **PASS** — chunk-size warning only |
| OpenSpec strict | `openspec validate --all --strict` | **PASS** — 1 spec, 0 failed |
| OpenSpec archived | `openspec validate --archived --strict` | **PASS** — 2 changes, 0 failed |
| OpenSpec doctor | `openspec doctor` | **PASS** — root OK |
| CI runner policy | `bash scripts/ci/check_runner_policy.sh` | **PASS** |
| CI YAML parse | `yaml.safe_load('.github/workflows/ci.yml')` | **PASS** — jobs `backend`, `ci-policy`, `frontend`, `openspec` |
| GitHub Actions | Run `40513341817` on `f91d1db` | **PASS** — all four jobs green |

---

## 8. Finding status

| Finding | Status | Evidence |
|---|---|---|
| **N-01** Git read/write bypass | **FIXED** | Direct Git inspection removed; wrapper rejects `--no-index`, `--output`, `--ext-diff`, external paths, traversal, symlink escapes; 130 permission/wrapper tests pass; independent matcher evaluation returns deny for all five agents |
| **N-02** Ruff mutation | **FIXED** | QA/release exact `ruff check app tests scripts` allow; `--fix`, `--unsafe-fixes`, `format` deny; tests pass |
| **N-03** SQLite escape | **FIXED** | `sqlite3` allow removed from all agents; `.shell`/`.output` commands deny; tests pass |
| **N-06** CI skipped security tests | **FIXED** | Pinned v2.2.0 job-local install; mandatory security step; fail-closed `REQUIRE_OPENCODE_CLI=1`; full suite runs with isolated HOME |
| **N-08** Git history secret exposure | **FIXED** | `log -p`/`--patch` and patch-producing `show` rejected; protected paths excluded from unfiltered output; tests pass |
| **C-02** Research data protection | **FIXED** | Direct interpreter/file tools and `git diff --output=data/...`/`--no-index projects/...` deny; wrapper path checks; tests pass |
| **H-01** Governance file protection | **FIXED** | Governance edits remain `ask`; `git diff --output=.opencode/...`/`AGENTS.md` deny; wrapper rejects protected writes; tests pass |
| **H-04** Effective permission verification | **FIXED** | Exact OpenCode matcher in tests; merged-rule test mandatory in CI; static + standalone free-model checks; paid live catalog explicitly NOT VERIFIED |
| **H-05** Secret protection | **FIXED** | Native read deny; shell readers and `git diff --no-index .env`/SSH-key paths deny; `git log -p`/`show` content deny; tests pass |
| **H-02** Destructive Git | **FIXED** (unchanged) | Direct destructive commands deny; wrapper cannot invoke them |
| **H-03** Release actions | **FIXED** (unchanged) | Developer deny; release `ask`; force-push deny |
| **M-02** TDD evidence policy | **PARTIALLY FIXED** (unchanged) | Policy requires red/green evidence; still not machine-enforced |
| **N-04** Code execution is not sandboxed | **OPEN (documented residual)** | Allowed `pytest`/`npm` commands can run repository code; no OS isolation |
| **N-05** Compound-command false positives | **OPEN (low, accepted)** | Commit messages containing `&`, `;`, `>` can be denied |
| **Live model execution** | **NOT VERIFIED** | Provider quota/model availability; no paid call made |
| **Paid provider live catalog** | **NOT VERIFIED** | Requires provider credentials; static allowlist passes |

---

## 9. Remaining risks

1. **OpenCode permissions are not an OS sandbox.** The developer can edit
   ordinary source/test/package files and run allowlisted `pytest`/`npm`
   commands; that code can perform filesystem or network operations. The
   wrapper closes the Git-specific read/write primitives, not arbitrary code
   execution. Do not run untrusted tests and do not point agents at production
   credentials.
2. **Paid provider catalog is static-only in CI.** `opencode-go/muse-spark-1.3-contributor`
   requires provider credentials; CI verifies its identifier statically, not its
   live availability. A provider-side removal of that paid model would not fail
   CI. Free models are verified against the pinned standalone catalog.
3. **Live model execution remains unverified.** Free-tier quota/model
   availability prevented an end-to-end prompt; no paid inference was used.
   Permission rules, not model reasoning, are what this remediation verifies.
4. **QA/release mypy can load plugins.** `mypy` is allowlisted for QA/release;
   a malicious `pyproject.toml` plugin could execute code. QA cannot edit
   `pyproject.toml`; release edits it only with approval. This is part of the
   not-a-sandbox residual.
5. **Approval rules are human-dependent.** `ask` rules for push, tag, merge,
   release and the exact deployment script rely on a human reading the prompt;
   they are not hard denies.
6. **The wrapper is a command validator, not a kernel sandbox.** It validates
   Git arguments, paths, revisions and environment. It cannot prevent a
   deliberately malicious allowed command from doing something outside Git.
7. **Compound-command false positives.** Commit messages containing shell
   metacharacters can be rejected by the compound-deny patterns. This is a
   usability cost of the fail-closed policy.

---

## 10. Exact commands and results

```text
# Configuration and effective permissions
uv run --frozen --no-sync pytest -q -p no:cacheprovider \
  tests/unit/test_agent_foundation_configuration.py
119 passed

# Wrapper
uv run --frozen --no-sync pytest -q -p no:cacheprovider \
  tests/unit/test_agent_git_inspection_wrapper.py
10 passed

# CI-equivalent isolated run
OPENCODE_BIN=/tmp/oc-dist/opencode REQUIRE_OPENCODE_CLI=1 \
HOME=/tmp/oc-ci-home2 XDG_CONFIG_HOME=/tmp/oc-ci-home2/.config \
XDG_DATA_HOME=/tmp/oc-ci-home2/.local/share \
XDG_CACHE_HOME=/tmp/oc-ci-home2/.cache \
XDG_STATE_HOME=/tmp/oc-ci-home2/.local/state \
uv run --frozen --no-sync pytest -q -p no:cacheprovider -rs \
  tests/unit/test_agent_foundation_configuration.py \
  tests/unit/test_agent_git_inspection_wrapper.py
130 passed

# Fail-closed missing-CLI check
OPENCODE_BIN=/tmp/does-not-exist REQUIRE_OPENCODE_CLI=1 \
uv run --frozen --no-sync pytest -q -p no:cacheprovider \
  tests/unit/test_agent_foundation_configuration.py \
  -k merged_opencode_permissions_enforce_hard_boundaries
1 failed (expected: CLI required)

# Full backend
bash scripts/agent/safe_pytest.sh
2676 passed, 1 warning in 108.16s

# Static checks
uv run --frozen --no-sync ruff check --no-cache app tests scripts
All checks passed!
uv run --frozen --no-sync mypy app
Success: no issues found in 202 source files
uv run --frozen --no-sync python scripts/ci/check_migration_safety.py \
  --base-ref origin/development
migration-safety: PASSED (no migration changes)
python3 scripts/agent/safe_git_inspect.py diff --check
exit 0

# Frontend
npx tsc --noEmit                      # PASS
npx vitest run                        # 44 files, 342 tests
npx vite build --outDir /tmp/slr-remediation-build --emptyOutDir  # PASS

# OpenSpec
openspec validate --all --strict      # 1 passed, 0 failed
openspec validate --archived --strict # 2 passed, 0 failed
openspec doctor                       # root OK

# CI policy / YAML
bash scripts/ci/check_runner_policy.sh
CI runner policy PASSED
```

---

## 11. Merge-readiness assessment

| Dimension | Result |
|---|---|
| N-01 Git bypass | **FIXED** |
| N-02 Ruff mutation | **FIXED** |
| N-03 SQLite escape | **FIXED** |
| C-02 research data protection | **FIXED** (permission-rule level) |
| H-01 governance protection | **FIXED** (permission-rule level) |
| H-04 effective permission tests | **FIXED** |
| H-05 secret protection | **FIXED** (permission-rule level) |
| CI security tests | **PASS** — run `40513341817`, 130 security tests |
| Backend | **PASS** — 2,676 tests locally and in CI |
| Frontend | **PASS** — 342 tests, TypeScript, build |
| OpenSpec | **PASS** — strict and archived |
| GitHub Actions | **PASS** — run `40513341817` on `f91d1db` |
| Merge conflicts | **None observed at baseline** |
| Live model execution | **NOT VERIFIED** |

**Overall:** **PASS WITH CONDITIONS** for the targeted security remediation. All
audit-identified permission bypasses are closed and covered by tests. The
conditions are non-blocking and documented: live model execution and the paid
provider catalog are not verified in CI, and permissions are not an OS sandbox.
The verified security remediation commit is
`f91d1db8278ce3abb1bd18e36afd3c9e3d06c82a`; its GitHub Actions run is green.
This report update is a docs-only follow-up whose own PR check is verified on
PR #5. Do not merge without the normal human review.

---

## 12. Final security remediation output

```text
SLR AGENT SECURITY REMEDIATION:
PASS WITH CONDITIONS

BRANCH:
feature/slr-agent-engineering-foundation

COMMIT:
f91d1db8278ce3abb1bd18e36afd3c9e3d06c82a

PR:
#5

N-01 GIT BYPASS:
FIXED

N-02 RUFF MUTATION:
FIXED

N-03 SQLITE ESCAPE:
FIXED

C-02 DATA PROTECTION:
FIXED

H-01 GOVERNANCE PROTECTION:
FIXED

H-04 PERMISSION TESTS:
FIXED

H-05 SECRET PROTECTION:
FIXED

CI SECURITY TESTS:
PASS

BACKEND:
PASS

FRONTEND:
PASS

OPENSPEC:
PASS

GITHUB ACTIONS:
PASS

READY FOR FINAL SECURITY REVIEW:
YES

REPORT:
docs/reviews/SLR_AGENT_ENGINEERING_FINAL_SECURITY_REMEDIATION.md
```
