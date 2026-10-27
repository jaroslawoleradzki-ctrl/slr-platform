# Proposal: Agent Engineering Security Hardening

## Why

The independent audit of commit `10239bb` found that the repository-local agent
foundation was discoverable and locally green, but its permission model was not
least-privilege. Broad `shell: *` rules allowed deployment wrappers, research
database mutation, self-modification of governance files, destructive Git
commands, and release actions without an effective approval gate. The
configuration test checked declared strings rather than effective permission
decisions, and CI did not validate OpenSpec or migration safety.

This change hardens the foundation without changing application behavior,
research data, production infrastructure, or CI runner topology.

## What Changes

- Replace broad shell access in every `slr-*` agent with default-deny shell
  permissions and narrow allowlists.
- Deny deployment and database-mutation command shapes, including `bash`/`sh`
  wrappers, `sudo`, `ssh`, `docker compose`, `docker-compose`, `python`, `cp`,
  `mv`, and `rm` against protected paths.
- Add shell-metacharacter denials as defense in depth against compound commands.
- Protect governance files (`AGENTS.md`, `.opencode/**`, `docs/agents/**`, the
  configuration test, `pyproject.toml`, `scripts/ci/**`) with ask/deny rules.
- Protect read-only agents from shell-based secret reads; add native read-path
  denials for `.env`, secrets, keys, and credential files.
- Add `scripts/agent/safe_pytest.sh`, a disposable-database test wrapper.
- Extend the configuration test with effective-permission evaluation, governance
  edit checks, model-catalog checks, path checks, and OpenSpec archive checks.
- Add CI diff hygiene, pinned OpenSpec strict validation, and a migration-safety
  guard.
- Align model fallback and 429 handling with the paid-credit policy.
- Update TDD evidence, Definition of Done, release scope, QA frontend commands,
  branch conventions, session-start guidance, and generated-artifact policy.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `agent-engineering-foundation`: adds enforceable least-privilege shell rules,
  research-data protection, governance protection, effective-permission tests,
  CI validation, and evidence requirements.

## Impact

- Changed: `.opencode/agents/*.md`, `tests/unit/test_agent_foundation_configuration.py`,
  `AGENTS.md`, `docs/agents/*`, `docs/session-start.md`, selected skills,
  `openspec/config.yaml`, `.github/workflows/ci.yml`, and documentation.
- Added: `scripts/agent/safe_pytest.sh`, `scripts/ci/check_migration_safety.py`,
  this OpenSpec change, and the hardening report.
- No application code, frontend behavior, migration, research data, Docker
  configuration, runner configuration, release, or deployment is changed.
- Risk tier: **HIGH** because the change governs production and research-data
  access boundaries, even though it is development tooling only. No production
  or data operation is performed.

Out of scope: application features, new runtime dependencies, provider
credentials, paid-model purchase, production deployment, and release tagging.
