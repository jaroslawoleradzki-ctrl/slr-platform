# agent-engineering-foundation Specification

## Purpose
Define how SLR Platform keeps repository-local agent guidance, skills, agents,
risk routing, test-first development, quality gates, and specification changes
consistent and safe.

## Requirements

### Requirement: Authoritative agent guidance

The repository SHALL provide a root `AGENTS.md` that is the authoritative
contract for coding agents, including project identity, verified architecture,
research-integrity rules, development rules, TDD, quality gates, security, and
definition of done.

#### Scenario: Agent starts work

- **WHEN** an agent begins a task in the repository
- **THEN** it reads `AGENTS.md` before inspecting or changing code
- **AND** the file states that SLR Platform is deterministic and has no embedded
  LLM or autonomous research decisions

#### Scenario: Conflicting legacy checklist

- **WHEN** `AGENTS.md` conflicts with `docs/session-start.md`
- **THEN** `AGENTS.md` is treated as authoritative

### Requirement: Discoverable project skills

The repository SHALL provide six version-controlled skills under
`.opencode/skills/<skill-id>/SKILL.md`: `slr-architecture`,
`slr-research-integrity`, `slr-testing`, `slr-database`, `slr-git-workflow`, and
`slr-release`.

#### Scenario: OpenCode discovers a skill

- **WHEN** OpenCode loads project configuration
- **THEN** each skill is discoverable from its directory and description
- **AND** each skill contains activation criteria, required context, workflow,
  safety constraints, validation, expected outputs, and references

#### Scenario: Task-specific activation

- **WHEN** a task matches a skill's declared activation criteria
- **THEN** the agent loads that skill instead of expanding every prompt with all
  procedures

### Requirement: Least-privilege specialized agents

The repository SHALL provide five agents under `.opencode/agents/`:
`slr-architect`, `slr-developer`, `slr-qa`, `slr-research-reviewer`, and
`slr-release-engineer`.

#### Scenario: Read-only review

- **WHEN** the architect, QA, or research reviewer agent runs
- **THEN** it cannot edit repository files
- **AND** its shell access is limited to the read-only or verification commands
  it needs

#### Scenario: Production deployment

- **WHEN** any agent attempts to deploy production
- **THEN** the action requires explicit human authorization or is denied
- **AND** no agent can deploy autonomously

#### Scenario: Invalid model identifier

- **WHEN** an agent definition is loaded
- **THEN** its model identifier is a verified `provider/model` value or the
  configuration test fails

### Requirement: Risk-based routing

The repository SHALL document LOW, MEDIUM, HIGH, and RELEASE workflows and the
minimum agent sequence for each.

#### Scenario: Low-risk fix

- **WHEN** a documentation, simple UI, or isolated bug-fix task is routed
- **THEN** the documented workflow is developer to QA
- **AND** the architect is not required

#### Scenario: Research-integrity change

- **WHEN** a task touches imports, DOI, deduplication, PRISMA, screening,
  quality assessment, extraction, synthesis, or migrations
- **THEN** it is classified HIGH risk
- **AND** the research-integrity reviewer is a required gate

### Requirement: Test-first behavioral change

The repository SHALL require a failing test before a behavioral implementation,
followed by the smallest change, a targeted green run, safe refactoring, and
regression checks.

#### Scenario: Behavioral implementation

- **WHEN** an agent changes application behavior
- **THEN** it records a failing test, the implementation, and a passing
  regression run

#### Scenario: Non-behavioral change

- **WHEN** a change is documentation-only or non-behavioral configuration
- **THEN** a proportionate validation exception applies
- **AND** configuration changes are validated by a deterministic test where
  practical

### Requirement: Documented quality gates

The repository SHALL document the actual Ruff, mypy, pytest, migration,
TypeScript, frontend-test, frontend-build, diff-hygiene, and CI commands.

#### Scenario: Change validation

- **WHEN** an agent prepares a commit
- **THEN** it runs the gates that cover the change and the full relevant suite
- **AND** reports any unavailable gate as NOT VERIFIED rather than PASS

#### Scenario: CI remains authoritative

- **WHEN** local validation disagrees with CI
- **THEN** `.github/workflows/ci.yml` is treated as authoritative
- **AND** existing CI jobs are not duplicated or weakened

### Requirement: OpenSpec-governed substantial changes

The repository SHALL use the OpenSpec `spec-driven` workflow for new features,
architectural changes, schema changes, research-methodology-sensitive changes,
and substantial multi-file refactoring.

#### Scenario: Substantial change

- **WHEN** a change meets the required threshold
- **THEN** it has proposal, requirements, acceptance criteria, design, tasks,
  implementation, verification, and archive artifacts
- **AND** `openspec validate` passes before archive

#### Scenario: Trivial change

- **WHEN** a change is a trivial fix or documentation-only update
- **THEN** full OpenSpec documentation is not required
