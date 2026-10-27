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

```bash
uv run --frozen --no-sync pytest -q -p no:cacheprovider
```

`tests/conftest.py` isolates `SLR_DATABASE_PATH` to a `tmp_path` database for
each test. Do not run tests against `data/slr-platform.db`.

For a fast loop, target the relevant module:

```bash
uv run --frozen --no-sync pytest -q -p no:cacheprovider tests/unit/services/test_<area>.py
```

### Migration-focused tests

```bash
uv run --frozen --no-sync pytest -q tests/unit/repositories tests/integration -k "migration or reconciliation"
```

This selects the migration/reconciliation modules, including
`test_migration_reconciliation.py`, the numbered migration tests, and the
integration migration/reconciliation tests. The full pytest suite remains the
authoritative gate.

### Frontend

```bash
cd frontend
npm ci
npm run type-check
npm test
npm run build
```

### Diff hygiene

```bash
git diff --check
```

## CI mapping

`.github/workflows/ci.yml` is authoritative. It runs on the dedicated
self-hosted runner `ai-node-slr-platform` and must not be replaced with
GitHub-hosted runners.

| CI job | What it runs |
|---|---|
| `ci-policy` | `bash scripts/ci/check_runner_policy.sh`, runner/host assertions |
| `backend` | locked `uv sync`, Ruff, mypy, full pytest on a disposable SQLite database |
| `frontend` | `npm ci`, `npm run type-check`, `npm test`, `npm run build` |

The backend job keeps test files and the SQLite database outside the checkout,
prefers `/dev/shm` for speed, and fails if a database appears under `data/`. Do
not duplicate these jobs or add a parallel copy. Add a new check only when it
covers a gap with clear value and low maintenance cost.

CI is triggered by pull requests and pushes to `main` and `development`. A
feature branch is validated through its pull request.

## Gate selection by change type

| Change type | Minimum gates |
|---|---|
| Documentation only | `git diff --check`; link/path sanity |
| Agent/skill/config | config test + Ruff + `git diff --check` |
| Backend behavior | targeted pytest, Ruff, mypy, full pytest |
| API contract | targeted/contract tests, full pytest, Ruff, mypy |
| Migration | migration-focused subset, full pytest, Ruff, mypy, backup/restore notes |
| Frontend behavior | `npm run type-check`, `npm test`, `npm run build` |
| Release | all backend and frontend gates, clean worktree, CI green |

## Result semantics

Use exactly one of these in reports:

- **PASS** — command ran and succeeded.
- **FAIL** — command ran and failed; include the failure.
- **NOT VERIFIED** — the tool or environment was unavailable. Never report this
  as PASS.
- **NOT APPLICABLE** — the gate does not cover this change; state why.

A green targeted test is not a substitute for the full regression suite before
commit. A skipped or weakened check is a failure of the task, not a pass.
