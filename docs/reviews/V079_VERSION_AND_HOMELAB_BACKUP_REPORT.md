# v0.7.9 version and HomeLab backup implementation report

## Scope and acceptance

- Synchronize the application version to `0.7.9` using the root `VERSION` file
  as the source of truth, without changing application workflow logic.
- Add a manually invoked HomeLab backup utility for the verified
  `slr-platform-v078` Compose stack. Use SQLite Online Backup API while the
  application remains running, preserve Compose and `.env` modes, validate the
  copied database, and retain prior backups.
- Do not run the utility against HomeLab, change the stack, or change research
  data.

## HomeLab preflight evidence

Read-only inspection of `192.168.100.22` identified:

- Container `slr-platform`, project `slr-platform-v078`.
- Compose `/home/cloud/slr-deploy-v078/compose.prod.yaml` and environment file
  `/home/cloud/slr-deploy-v078/.env` (mode `0600`). The Compose file is mode
  `0600`.
- Persistent mount `/data/compose/18/data` → `/app/data`, and projects mount
  `/data/compose/18/projects` → `/app/projects`.
- Runtime database path `/app/data/slr-platform.db`; `SLR_DATABASE_PATH` is
  unset, so the application uses its default `data/slr-platform.db` relative to
  `/app`.

The script checks these identities before creating a backup and fails closed
if the running stack differs. Its production defaults write under
`/home/cloud/slr-backups/slr-platform-v078`, outside the research data mount.
It was not run on HomeLab.

## TDD evidence

- The frontend version assertion was changed first. Before the version update,
  `npm --prefix frontend test -- Versioning.test.tsx` failed because the
  injected `APP_VERSION` was `0.7.8`, expected `0.7.9`.
- The backend and backup regression tests were authored before implementing the
  backup utility. The first backend invocation could not start because the
  local environment lacked pytest. After syncing the existing frozen dev
  dependencies, the initial utility test exposed a missing parent-directory
  creation in the fake Docker fixture; the fixture was corrected and the tests
  passed. That fixture correction is test harness verification, not a product
  behavior change.
- The focused green command was
  `bash scripts/agent/safe_pytest.sh tests/unit/test_versioning.py tests/unit/test_homelab_backup_script.py`:
  **6 passed**. The backup tests use a disposable SQLite database and a fake
  Docker executable; they verify a real SQLite Online Backup API copy,
  integrity validation, timestamped/private output, preserved config modes,
  refusal of an inactive container, and retention of an older backup.

## Verification

- `npm --prefix frontend test -- Versioning.test.tsx`: **6 passed**. This
  covers the version constant and rendering in Header, Sidebar, and About.
- `npm --prefix frontend run type-check`: **PASS**.
- `npm --prefix frontend run build`: **PASS**; generated bundle contains
  `0.7.9`. Vite reported its existing non-fatal large-chunk advisory.
- `npm --prefix frontend test`: **367 passed, 51 files**.
- `uv run --frozen --no-sync ruff check app tests scripts`: **PASS**.
- `uv run --frozen --no-sync mypy app`: **PASS**.
- `uv run --frozen --no-sync mypy scripts/backup_homelab.py`: **PASS**.
- `openspec validate --all --strict`: **5 passed, 0 failed**.
- `python3 scripts/agent/safe_git_inspect.py diff --check` passed for the
  tracked worktree diff. The first PR CI run found trailing Markdown hard-break
  spaces in the new release note, which that local check did not cover while
  the note was untracked. They were removed in the follow-up commit; the branch
  CI run checks the complete commit diff.
- Full backend `bash scripts/agent/safe_pytest.sh`: **2,745 passed, 1 failed**.
  The sole failure is `test_configured_free_models_are_in_standalone_catalog`, which
  expects `opencode/nemotron-3-ultra-free` in the installed OpenCode catalog.
  This is the previously identified model-catalog environment mismatch on base
  `74fd67a`, unrelated to application versioning or the backup utility. The
  test was not weakened or skipped.
- Migration safety was not applicable: this change adds no database migration.

## Data and deployment boundary

The backup utility was validated only with disposable fixture data. No
HomeLab backup was executed, no container or Compose configuration was changed,
and no production research data was modified. The version bump does not deploy
the application.
