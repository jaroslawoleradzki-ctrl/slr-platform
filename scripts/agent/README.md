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

## Deployment

Deployment is human-run. `scripts/deploy_ai_node.sh` is not an agent-allowed
command. The release engineer may request the exact script only through the
human approval prompt; wrappers such as `bash scripts/deploy_ai_node.sh`,
`sudo`, `ssh`, and Docker compose deployment commands are denied.

## Compound commands

Allowed commands are denied when combined with `;`, `&&`, pipes, command
substitution, backticks, redirection, or newlines. Keep approved command text
simple and use the edit/read/grep/glob tools for file work.
