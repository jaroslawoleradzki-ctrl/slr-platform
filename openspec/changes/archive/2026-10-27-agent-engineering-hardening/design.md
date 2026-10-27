# Design: Agent Engineering Security Hardening

## Context

OpenCode V2 permissions are ordered rules: the last matching rule wins, shell
resources match raw command text, and wildcards are supported. They are a tool
authorization layer, not a filesystem or process sandbox. A command that is
allowed can still run arbitrary code through the shell if the command itself is
a general-purpose interpreter. This design therefore uses defense in depth and
does not claim sandbox guarantees.

## Decisions

### 1. Default-deny shell with role allowlists

Every agent declares `shell: *` = `deny` first, then a narrow allowlist. This
removes the previous broad `shell: *` = `allow` baseline. Role allowlists:

- **architect/reviewer:** Git inspection and, for the reviewer, read-only SQLite
  inspection; native read/grep/glob tools replace shell `cat`/`find`/`rg`.
- **developer:** `uv run` pytest/ruff/mypy, the safe test wrapper, frontend
  checks with `npm --prefix`, Git inspection, `git add`, and approved
  `git commit`/`git push`.
- **QA:** test/static-analysis commands, the safe wrapper, `npm --prefix`
  frontend checks, OpenSpec read/validate, and Git inspection.
- **release:** release/preflight gates, exact deployment script `ask`, and
  `ask` for merge/push/tag/GitHub release/API operations.

### 2. Compound-command denials

Prefix allowlists can be bypassed with `;`, `&&`, pipes, command substitution,
backticks, redirection, and newlines. Each agent appends deny rules for those
metacharacter shapes after its allowlist. This is a best-effort defense, not a
sandbox. Developers should avoid metacharacters in approved command text.

### 3. Deployment

Production deployment remains a human-run action. The developer agent has no
deployment allow. The release engineer may invoke the exact
`scripts/deploy_ai_node.sh` only through `ask`; `bash`/`sh`/`./` wrappers,
`sudo`, `ssh`, and Docker compose commands are denied. The deployment script
itself remains unchanged and is not executed during this change.

### 4. Research-data protection

The developer edit rules deny `data/`, `projects/`, database files, backups,
`.env`, secrets, and keys. Shell access to `python`, `sqlite3`, `cp`, `mv`, and
`rm` is not allowlisted. `scripts/agent/safe_pytest.sh` sets a disposable
`SLR_DATABASE_PATH` and `TMPDIR`, and removes its temporary directory. A test
could still read data if its code deliberately does so; that residual risk is
documented and is not presented as filesystem isolation.

### 5. Governance protection

The developer may edit ordinary application, test, frontend, and docs files.
Governance paths are `ask`: `AGENTS.md`, `.opencode/**`, `docs/agents/**`, the
configuration test, `pyproject.toml`, `scripts/ci/**`, and `scripts/agent/**`.
The deployment script is `deny`. The release engineer's edit set is limited to
`VERSION`, `CHANGELOG.md`, and `docs/releases/**`; dependency/build config and
OpenSpec are `ask`, and audit reports are `deny`.

### 6. Effective-permission tests

The test helper parses each agent's ordered permissions and evaluates a command
with the same last-match, wildcard semantics documented by OpenCode. Tests cover
deploy wrappers, `sudo`, `ssh`, database mutation, destructive Git, release
commands, `gh api`, `cat .env`, compound commands, governance edits, and the QA
frontend command forms. A separate optional test queries `opencode models` when
the CLI is available; CI may skip it if OpenCode is not installed.

### 7. CI gates

CI adds:

- `git diff --check` against the PR base (or `HEAD^` on push);
- pinned `@fission-ai/openspec@1.15.0` strict validation;
- `scripts/ci/check_migration_safety.py`, which rejects modified/deleted
  existing migrations and destructive SQL in added migrations unless explicitly
  marked;
- a cleanup fix that removes the actual temporary test directory.

### 8. Model routing and failures

The paid `opencode-go/muse-spark-1.3-contributor` developer default remains the
user's preferred implementation model and is documented as pre-authorized for
implementation tasks. The fallback becomes the free
`opencode/mimo-v2.6-flash-free`. HTTP 429 handling is documented: retry with
backoff, use the free fallback, use a paid model only with authorization, and
report `NOT VERIFIED` if execution remains unavailable.

## Rejected alternatives

- **Only expanding the denylist:** rejected; prefix deny lists are incomplete and
  the audit demonstrated wrapper bypasses.
- **Allowing broad shell and relying on prompts:** rejected; prompts are not an
  enforcement layer.
- **Adding a container/sandbox runtime:** out of proportion for this repository
  and not demonstrable within the task. The residual risk is documented.
- **Changing the developer model to free:** rejected because it changes the
  user's preferred routing; the decision and cost are documented instead.
