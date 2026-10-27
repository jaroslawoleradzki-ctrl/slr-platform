# Agent Shell Helpers

OpenCode permission rules authorize tool calls; they are **not** a filesystem or
process sandbox. An allowed command can still run arbitrary code if it is a
general-purpose interpreter. The repository therefore uses a default-deny shell
policy with narrow allowlists, protected paths, and a small number of helpers.

## `safe_pytest.sh`

Run tests through this wrapper in agent sessions:

```bash
bash scripts/agent/safe_pytest.sh
bash scripts/agent/safe_pytest.sh tests/unit/test_agent_foundation_configuration.py
bash scripts/agent/safe_pytest.sh tests/unit/repositories tests/integration -k "migration or reconciliation"
```

The wrapper:

- creates a fresh temporary directory;
- points `SLR_DATABASE_PATH` and `TMPDIR` there;
- disables the pytest cache;
- removes the temporary directory after the run.

It does not prevent a deliberately written test from opening another path. Do
not treat shell restrictions as complete isolation. Never point an agent at the
real `data/` database, production credentials, or a production host.

## `safe_git_inspect.py`

Direct `git` commands are not agent-allowed. Use the read-only wrapper
instead:

```bash
python3 scripts/agent/safe_git_inspect.py status --short
python3 scripts/agent/safe_git_inspect.py diff --stat
python3 scripts/agent/safe_git_inspect.py diff HEAD~1 -- app/services/foo.py
python3 scripts/agent/safe_git_inspect.py log --oneline -n 20
python3 scripts/agent/safe_git_inspect.py show --stat HEAD
```

The wrapper is deliberately fail-closed:

- operation allowlist: `status`, `diff`, `log`, `show`, `branch-current`,
  `worktree-list`;
- rejects `--no-index`, `--output`, `--ext-diff`, `--textconv`, `--config`,
  `-c`, `--git-dir`, `--work-tree`, external helpers, and unknown options;
- rejects absolute paths, traversal, glob/pathspec magic, symlink escapes, and
  protected paths (`.env*`, `data/`, `projects/`, `secrets/`, `backups/`,
  `*.db`, `*.sqlite*`, `*.pem`, `*.key`);
- rejects `rev:path` blob syntax and patch-producing `log`/`show` forms;
- runs Git with argument arrays, a sanitised environment, no pager, no external
  diff/textconv, and no optional index locks.

It is not a sandbox. An allowed test or build command can still run repository
code. See `docs/agents/SECURITY_MODEL.md`.

## Deployment

Deployment is human-run. `scripts/deploy_ai_node.sh` is not an agent-allowed
command. The release engineer may request the exact script only through the
human approval prompt; wrappers such as `bash scripts/deploy_ai_node.sh`,
`sudo`, `ssh`, and Docker compose deployment commands are denied.

## Compound commands

Allowed commands are denied when combined with `;`, `&&`, pipes, command
substitution, backticks, redirection, or newlines. Keep approved command text
simple and use the edit/read/grep/glob tools for file work.
