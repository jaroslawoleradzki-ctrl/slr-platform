# Agent Security Model

## What the permission layer is

OpenCode permissions authorize tool calls. They are ordered rules where the last
matching rule wins. Shell resources match raw command text and support
wildcards. The `slr-*` agents use a default-deny shell rule followed by narrow
role allowlists.

The permission layer is **not** a filesystem or process sandbox. An allowed
command can still run code that the command itself permits. The repository
therefore combines permissions with protected paths, disposable test databases,
and human approval for production and release actions.

## Roles

| Role | Shell posture | Edit posture |
|---|---|---|
| `slr-architect` | Git/OpenSpec inspection only | denied |
| `slr-developer` | allowlisted test/static/Git commands | ordinary source/test/docs; governance asks; data/secrets/deploy denies |
| `slr-qa` | allowlisted tests/static/frontend/OpenSpec | denied |
| `slr-research-reviewer` | Git/OpenSpec inspection and read-only SQLite | denied |
| `slr-release-engineer` | release gates plus approval-required release actions | release metadata only |

## Protected paths

- `data/`, `projects/`, `**/*.db`, `**/*.sqlite*`, `**/backups/**`
- `.env`, `**/.env*`, `**/secrets/**`, `**/*.pem`, `**/*.key`
- `AGENTS.md`, `.opencode/**`, `docs/agents/**`, the configuration test,
  `pyproject.toml`, `scripts/ci/**`, `scripts/agent/**`
- `scripts/deploy_ai_node.sh`

Governance edits are `ask` for the developer. Data, secrets, and the deployment
script are `deny`. The release engineer cannot edit audit reports.

## Git inspection

Direct `git` inspection commands are not allowlisted. Their option surface can
read arbitrary files (`--no-index`), write files (`--output`), invoke external
diff helpers (`--ext-diff`), print file contents from history (`-p`), or run
repository-configured hooks (`core.fsmonitor`). Agents use the read-only
wrapper:

```bash
python3 scripts/agent/safe_git_inspect.py status --short
python3 scripts/agent/safe_git_inspect.py diff --stat
python3 scripts/agent/safe_git_inspect.py diff HEAD~1 -- app/services/foo.py
python3 scripts/agent/safe_git_inspect.py log --oneline -n 20
python3 scripts/agent/safe_git_inspect.py show --stat HEAD
python3 scripts/agent/safe_git_inspect.py branch-current
python3 scripts/agent/safe_git_inspect.py worktree-list
```

The wrapper:

- accepts only those operations and an explicit per-operation option allowlist;
- rejects `--no-index`, `--output`, `--ext-diff`, `--textconv`, `--config`,
  `-c`, `--git-dir`, `--work-tree`, external helpers, and unknown options;
- accepts only repository-relative paths without traversal, glob, or pathspec
  magic; paths must resolve inside the worktree and must not touch `.env*`,
  `data/`, `projects/`, `secrets/`, `backups/`, `*.db`, `*.sqlite*`, `*.pem`, or
  `*.key`;
- accepts only revisions that resolve to commits, rejecting `rev:path` blobs;
- rejects patch-producing `git log`/`git show` forms and excludes protected
  paths from unfiltered output.

Direct `git` commands are denied for agents; every Git inspection operation
goes through the wrapper above. Use the native read/grep/glob tools for file
content.

## Ruff and SQLite

`slr-qa` and `slr-release-engineer` may run only
`uv run --frozen --no-sync ruff check app tests scripts`. `--fix`,
`--unsafe-fixes`, and `ruff format` are denied because those roles are
read-only. `sqlite3` shell access is denied for every agent: SQLite dot-commands
such as `.shell` can execute arbitrary commands.

## Compound commands

Allowed command strings are denied when they contain `;`, `&&`, `&`, a pipe,
command substitution, a backtick, output redirection, or a newline. This is
best-effort defense, not a sandbox. Keep approved command text simple.

## Testing

Use `bash scripts/agent/safe_pytest.sh` in agent sessions. It creates a fresh
temporary directory, points `SLR_DATABASE_PATH` and `TMPDIR` there, and removes
it afterward. A deliberately written test can still open another path; do not
treat the wrapper as complete isolation.

## Deployment

Deployment is human-run. The release engineer may request the exact
`scripts/deploy_ai_node.sh` through the approval prompt. `bash`/`sh`/`./`
wrappers, `sudo`, `ssh`, and Docker compose deployment commands are denied. The
developer agent cannot deploy.

## Residual risk

The permission model cannot prove what an allowed test or script does. Do not
run untrusted tests, do not point an agent at production credentials, and do not
treat a green local run as authorization to merge or deploy.
