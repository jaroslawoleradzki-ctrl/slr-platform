# Spec Delta

## Purpose

Harden the repository-local agent engineering foundation so that its declared
research-integrity, Git-safety, release, and production boundaries are enforced
by the agent permission layer as far as OpenCode permits, and are independently
tested.

## ADDED Requirements

### Requirement: Default-deny agent shell execution

Every `slr-*` agent SHALL declare a default-deny shell rule and MAY allow only
the commands its role needs.

#### Scenario: Developer shell is allowlisted

- **WHEN** the `slr-developer` agent is evaluated
- **THEN** an unlisted command is denied
- **AND** permitted test, static-analysis, Git inspection, and commit commands
  are explicitly listed
- **AND** `bash`, `sh`, `sudo`, `ssh`, `docker`, `docker-compose`, `python`,
  `sqlite3`, `cp`, `mv`, and `rm` are not broadly allowed

#### Scenario: Compound command is denied

- **WHEN** a permitted command is combined with `;`, `&&`, a pipe, command
  substitution, a backtick, redirection, or a newline
- **THEN** the compound command is denied

### Requirement: Deployment requires explicit human authorization

No agent SHALL deploy production autonomously.

#### Scenario: Deployment wrapper is denied

- **WHEN** an agent attempts `bash scripts/deploy_ai_node.sh`,
  `sh scripts/deploy_ai_node.sh`, `sudo docker compose up -d`, `ssh ...`, or a
  `docker`/`docker-compose` deployment command
- **THEN** the command is denied
- **AND** the exact release deployment script is at most `ask`, never `allow`,
  for the release engineer
- **AND** the developer agent cannot execute it

#### Scenario: Deployment is human-run

- **WHEN** production deployment is required
- **THEN** a human runs the approved deployment procedure outside the agent
  session after the release gate

### Requirement: Research data is protected from agent shells

Agents SHALL NOT be able to mutate real research data through shell commands.

#### Scenario: Database mutation is denied

- **WHEN** an agent attempts `python3 -c ... data/slr-platform.db`,
  `sqlite3 data/slr-platform.db`, `rm data/slr-platform.db`, or copies a database
  into `data/`
- **THEN** the command is denied
- **AND** the developer edit rules deny `data/`, `projects/`, database files,
  backups, `.env`, and secret/key files

#### Scenario: Tests use a disposable database

- **WHEN** an agent runs tests through `scripts/agent/safe_pytest.sh`
- **THEN** `SLR_DATABASE_PATH` and `TMPDIR` point to a fresh temporary directory
- **AND** the directory is removed when the test run ends

### Requirement: Governance files are protected

Policy changes SHALL require human approval.

#### Scenario: Developer edits governance

- **WHEN** the developer agent attempts to edit `AGENTS.md`, `.opencode/**`,
  `docs/agents/**`, `tests/unit/test_agent_foundation_configuration.py`,
  `pyproject.toml`, or `scripts/ci/**`
- **THEN** the edit is `ask` or `deny`, never silently allowed

#### Scenario: Release metadata remains narrow

- **WHEN** the release engineer edits release metadata
- **THEN** `VERSION`, `CHANGELOG.md`, and `docs/releases/**` are allowed
- **AND** dependency/build configuration, audit reports, and governance files
  are `ask` or `deny`

### Requirement: Effective permissions are tested

The configuration test SHALL evaluate effective permission decisions, not only
inspect declared strings.

#### Scenario: Representative commands

- **WHEN** the effective-permission tests run
- **THEN** they cover deployment wrappers, `sudo`, `ssh`, database mutation,
  destructive Git, release publication, `gh api`, `cat .env`, and compound
  commands
- **AND** they assert `deny`, `ask`, or `allow` for each agent role
- **AND** they do not claim that shell rules provide filesystem isolation

### Requirement: CI validates OpenSpec, diff hygiene, and migration safety

CI SHALL run the repository's documented validation gates.

#### Scenario: Pull request validation

- **WHEN** a pull request targets `development`
- **THEN** CI runs `git diff --check`, pinned OpenSpec strict validation, the
  migration-safety guard, Ruff, mypy, the full backend suite, and the frontend
  type-check/test/build

#### Scenario: Existing migration changed

- **WHEN** a migration file that exists on the base branch is modified or deleted
- **THEN** the migration-safety check fails

#### Scenario: Destructive SQL

- **WHEN** an added migration contains destructive SQL
- **THEN** the check fails unless the file carries the explicit
  `migration-safety: approved-destructive` marker

### Requirement: Merge readiness requires green CI

A branch SHALL NOT be reported as merge-ready without a green CI run.

#### Scenario: CI not run

- **WHEN** CI has not run
- **THEN** the status is `NOT VERIFIED` or `PASS WITH CONDITIONS`, never `PASS`
- **AND** the report does not claim merge readiness
