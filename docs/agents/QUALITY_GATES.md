# Quality Gates

These are the actual repository commands. Do not replace them with invented
commands or weaken an existing gate.

## Local gates

Run from the repository root unless a step says otherwise.

### Backend setup

```bash
uv sync --frozen --extra dev --python 3.12
```

### Ruff

```bash
uv run --frozen --no-sync ruff check app tests scripts
```

Configuration: `pyproject.toml` (`target-version = "py312"`, line length 120,
rules `E`, `F`, `W`, `I`).

### Mypy

```bash
uv run --frozen --no-sync mypy app
```

Configuration: `pyproject.toml`; third-party stubs for `openpyxl`, `fpdf`, and
`pypdf` are configured there.

### Pytest

Agent sessions:

```bash
bash scripts/agent/safe_pytest.sh
```

The wrapper forces a disposable `SLR_DATABASE_PATH` and `TMPDIR`. The raw
command remains valid for CI and human local runs:

```bash
uv run --frozen --no-sync pytest -q -p no:cacheprovider
```

`tests/conftest.py` also isolates `SLR_DATABASE_PATH` to a `tmp_path` database
for each test. Do not run tests against `data/slr-platform.db`.

For a fast loop, target the relevant module:

```bash
bash scripts/agent/safe_pytest.sh tests/unit/services/test_<area>.py
```

### Migration-focused tests

```bash
uv run --frozen --no-sync pytest -q tests/unit/repositories tests/integration -k "migration or reconciliation"
```

### Migration safety

```bash
uv run --frozen --no-sync python scripts/ci/check_migration_safety.py --base-ref origin/development
```

The guard fails if an existing migration was modified, renamed, or deleted. It
also fails on destructive SQL in an added migration unless the file carries the
explicit marker `migration-safety: approved-destructive: <reason>`. Do not add
the marker without human approval and a recovery plan.

### Frontend

```bash
npm --prefix frontend run type-check
npm --prefix frontend test
npm --prefix frontend run build
```

### OpenSpec

```bash
openspec validate --all --strict
openspec validate --archived --strict
```

The CI CLI version is pinned to `@fission-ai/openspec@1.15.0`.

### Diff hygiene

```bash
# Agents use the read-only wrapper; humans and CI may run git diff --check.
python3 scripts/agent/safe_git_inspect.py diff --check
```

## CI mapping

`.github/workflows/ci.yml` is authoritative. It runs on the dedicated
self-hosted runner `ai-node-slr-platform` and must not be replaced with
GitHub-hosted runners.

| CI job | What it runs |
|---|---|
| `ci-policy` | `bash scripts/ci/check_runner_policy.sh`, runner/host assertions, `git diff --check` |
| `openspec` | pinned `@fission-ai/openspec@1.15.0`, strict change/spec validation, archived validation |
| `backend` | locked `uv sync`, Ruff, mypy, migration safety, full pytest on a disposable SQLite database |
| `frontend` | `npm ci`, `npm run type-check`, `npm test`, `npm run build` |

The backend job keeps test files and the SQLite database outside the checkout,
prefers `/dev/shm` for speed, and fails if a database appears under `data/`. The
cleanup step removes the actual temporary directory, including the
`RUNNER_TEMP` fallback.

CI is triggered by pull requests and pushes to `main`, `development`, and
`integration/**`. A feature branch is validated through its pull request.

## Gate selection by change type

| Change type | Minimum gates |
|---|---|
| Documentation only | `git diff --check` (human/CI) or the safe Git wrapper (agent); link/path sanity |
| Agent/skill/config | configuration/effective-permission tests + Ruff + diff hygiene |
| Backend behavior | targeted pytest, Ruff, mypy, full pytest |
| API contract | targeted/contract tests, full pytest, Ruff, mypy |
| Migration | migration-focused subset, migration-safety guard, full pytest, Ruff, mypy, backup/restore notes |
| Frontend behavior | `npm --prefix frontend run type-check`, `npm --prefix frontend test`, `npm --prefix frontend run build` |
| Release | all backend and frontend gates, OpenSpec, clean worktree, CI green |

## Result semantics

Use exactly one of these in reports:

- **PASS** — command ran and succeeded, and CI is green for merge readiness.
- **PASS WITH CONDITIONS** — local evidence is green but a named condition
  remains (for example CI not yet run).
- **FAIL** — command ran and failed; include the failure.
- **BLOCK** — a critical or high-severity finding remains.
- **NOT VERIFIED** — the tool or environment was unavailable. Never report this
  as PASS.

A green targeted test is not a substitute for the full regression suite before
commit. A skipped or weakened check is a failure of the task, not a pass.
