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
