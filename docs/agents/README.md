# SLR Agent Engineering

Repository-local guidance for coding agents working on SLR Platform. The root
[`AGENTS.md`](../../AGENTS.md) is authoritative; this directory explains how to
use the agents, skills, OpenSpec workflow, and quality gates in practice.

## What is in the repository

```text
AGENTS.md                       Project-wide agent contract
.opencode/agents/               Five specialized OpenCode agents
.opencode/skills/slr-*/         Six project skills
.opencode/skills/openspec-*/    OpenSpec workflow skills (generated)
.opencode/commands/opsx-*.md    OpenSpec slash commands (generated)
openspec/                       OpenSpec root, specs, and change archive
docs/agents/                    This operational documentation
docs/reviews/                   Implementation and review reports
scripts/agent/safe_pytest.sh    Disposable-database test wrapper
scripts/ci/                     CI policy and migration-safety guards
```

OpenCode discovers project agents from `.opencode/agents/<id>.md` and project
skills from `.opencode/skills/<id>/SKILL.md`. No project-level OpenCode config is
required for discovery.

## The five agents

| Agent | Use it for | Default posture |
|---|---|---|
| `slr-architect` | architecture analysis, impact, specification, risk tier | read-only |
| `slr-developer` | implementation, TDD, tests, docs | can edit source |
| `slr-qa` | independent verification, regression, static analysis, CI readiness | read-only |
| `slr-research-reviewer` | PRISMA, provenance, decisions, audit trails | read-only |
| `slr-release-engineer` | versioning, changelog, integration, release/deploy prep | release metadata only |

Model choices and fallbacks are in [MODEL_ROUTING.md](MODEL_ROUTING.md).
All agents use default-deny shell permissions with narrow allowlists; the
security model and residual risks are in [SECURITY_MODEL.md](SECURITY_MODEL.md).
The disposable test wrapper is `scripts/agent/safe_pytest.sh`.

## The six project skills

| Skill | Activates for |
|---|---|
| `slr-architecture` | contracts, layers, dependencies, compatibility, ADRs |
| `slr-research-integrity` | imports, DOI, dedup, PRISMA, screening, QA, extraction, synthesis |
| `slr-testing` | TDD, test strategy, regression, Ruff/mypy/pytest/TypeScript |
| `slr-database` | SQLite schema, migrations, transactions, backup/restore |
| `slr-git-workflow` | branches, worktrees, commits, merges, CI |
| `slr-release` | versioning, changelog, releases, Homelab, deployment, rollback |

Skills are advertised by their `description`; an agent loads one when the task
matches. You can also load one explicitly in a prompt with `@skill-id`, for
example:

```text
@slr-testing write the failing test for the new import warning path.
```

Keep skills focused. If a procedure belongs to one workflow, update the skill
rather than expanding `AGENTS.md`.

## Example OpenCode commands

Run one agent from the shell:

```bash
opencode run --agent slr-architect \
  "Analyze the proposed import-warning change. Produce an impact analysis and acceptance criteria only."

opencode run --agent slr-developer \
  "Implement the approved specification in the current worktree. Follow TDD and run the quality gates."

opencode run --agent slr-qa \
  "Independently verify the current branch against AGENTS.md and report PASS/FAIL/NOT VERIFIED with commands."

opencode run --agent slr-research-reviewer \
  "Review the current branch for PRISMA, provenance, duplicate, and audit-trail integrity. Do not edit."

opencode run --agent slr-release-engineer \
  "Prepare release v0.7.4 notes and preflight. Stop before tagging or deploying."
```

Fallback model override without editing configuration:

```bash
opencode run --agent slr-developer \
  --model opencode/mimo-v2.6-flash-free \
  "Continue the implementation."
```

In the TUI, select the agent with the agent picker. The `opencode run --agent`
form above is the stable documented path for scripted use.

## Start here

1. Read [`AGENTS.md`](../../AGENTS.md).
2. Check the working tree and current branch.
3. Pick the task risk tier in [MODEL_ROUTING.md](MODEL_ROUTING.md).
4. Use [WORKFLOW.md](WORKFLOW.md) for the end-to-end sequence.
5. Use [QUALITY_GATES.md](QUALITY_GATES.md) before committing.

## Related documentation

- [WORKFLOW.md](WORKFLOW.md) — feature, TDD, OpenSpec, review, release, blocked tasks, token control.
- [MODEL_ROUTING.md](MODEL_ROUTING.md) — risk routing, model IDs, free fallbacks, HTTP 429 handling, handoffs.
- [QUALITY_GATES.md](QUALITY_GATES.md) — exact commands and CI mapping.
- [SECURITY_MODEL.md](SECURITY_MODEL.md) — default-deny shell, protected paths, residual risk.
- [`../../openspec/config.yaml`](../../openspec/config.yaml) — OpenSpec project context and rules.
