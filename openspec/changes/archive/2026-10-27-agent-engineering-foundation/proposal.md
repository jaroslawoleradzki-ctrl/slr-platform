# Proposal

## Why

Agent work on SLR Platform currently depends on ad-hoc prompts and a legacy
session checklist. That produces inconsistent testing, avoidable rework, and
unclear boundaries around research records and production operations. A
repository-local foundation makes the existing engineering conventions explicit
and enforceable.

## What Changes

- Add a root `AGENTS.md` with the project identity, verified architecture,
  research-integrity rules, development rules, TDD, quality gates, security, and
  definition of done.
- Add six repository-local skills: architecture, research integrity, testing,
  database, git workflow, and release.
- Add five least-privilege OpenCode agents: architect, developer, QA, research
  reviewer, and release engineer.
- Initialize OpenSpec with the `spec-driven` workflow and project-specific
  context/rules.
- Add risk-based routing, model routing, workflow, and quality-gate
  documentation.
- Add a deterministic configuration test that validates the foundation itself.
- Reconcile the legacy `docs/session-start.md` checklist with `AGENTS.md`.

This is a development-infrastructure change only. It does not change
application behavior, research data, or production infrastructure.

## Capabilities

### New Capabilities

- `agent-engineering-foundation`: the durable repository-local contract for
  agent guidance, skills, agents, risk routing, TDD/quality gates, and the
  OpenSpec workflow.

### Modified Capabilities

None.

## Impact

- Added: `AGENTS.md`, `.opencode/agents/`, `.opencode/skills/slr-*/`,
  `docs/agents/`, `openspec/`, and a configuration test.
- Modified: `docs/session-start.md` (reconciliation note only).
- No changes to `app/`, `frontend/src/`, `migrations/`, application data,
  Docker configuration, or CI workflows.
- No new runtime dependency. OpenSpec 1.15.0 is already installed.
- Risk tier: **MEDIUM** (multi-file development-tooling change, no application
  behavior). It is not HIGH risk because it does not touch import, DOI,
  deduplication, PRISMA, screening, quality assessment, extraction, synthesis,
  migrations, or research data. It is not RELEASE work.

Out of scope: application features, embedded AI/LLM capabilities, research data
changes, production deployment, CI runner changes, and releases. Any future
HIGH-risk or RELEASE change requires separate human approval.
