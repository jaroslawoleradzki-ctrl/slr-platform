# Design

## Context

The audit found no root `AGENTS.md`, no project OpenCode agents or skills, and no
OpenSpec root. The repository already has a complete CI workflow, a pytest
configuration suite, and clear architecture/research-integrity documentation.
OpenCode V2.2.0 is installed, OpenSpec 1.15.0 is installed, and the preferred
models resolve to concrete provider IDs.

The design therefore adds configuration and documentation only. It does not
touch application code, migrations, data, Docker, or CI.

## Goals / Non-Goals

**Goals:**

- Make the existing conventions explicit and enforceable.
- Give each risk tier the smallest sufficient agent workflow.
- Keep read-only review genuinely read-only.
- Validate the foundation with a deterministic test.
- Integrate OpenSpec using its supported CLI and native layout.

**Non-Goals:**

- Adding application features or AI/LLM runtime behavior.
- Changing research data, schema, or production infrastructure.
- Replacing existing CI jobs or runner policy.
- Automating deployment or scientific decisions.

## Decisions

### Native OpenCode V2 layout

Use `.opencode/agents/<id>.md` and `.opencode/skills/<id>/SKILL.md`. This is the
V2 discovery layout and requires no project-level `opencode.json`. It keeps the
foundation version-controlled and portable.

Alternative considered: a central JSONC `agents` block. Rejected because it
mixes prompts with configuration and is harder to review.

### Verified model IDs

Use the concrete IDs returned by `opencode models`: free Nemotron models for
read-only analysis and review, and Muse Spark 1.3 Contributor for
implementation. Document the MiMo-V2.6-Flash fallback. The configuration test
pins the IDs so a provider rename fails loudly instead of breaking loading
silently.

Alternative considered: putting display names in `model:`. Rejected because
OpenCode requires `provider/model`.

### Five agents, all `mode: all`

All five agents are usable as primary or subagent sessions, but permissions
encode the real boundary. Read-only agents deny edits and restrict shell.
Developer and release engineer can edit only what their role needs. Every agent
denies nested subagents so the human controls the chain and token cost.

Alternative considered: only the developer as primary. Rejected because direct
`opencode run --agent slr-qa` and release handoffs would be awkward.

### Six concise skills

Each skill covers one workflow and references repository files instead of
restating `AGENTS.md`. This keeps the advertised descriptions short and the
loaded bodies focused.

Alternative considered: one large skill. Rejected because it would load
irrelevant procedures and duplicate the root contract.

### OpenSpec with the documented spec-driven workflow

Initialize with `openspec init --tools opencode`, keep the generated commands
and skills, and add project context/rules to `openspec/config.yaml`. This change
is tracked as an OpenSpec change so proposal, requirements, design, tasks,
validation, and archive are exercised end to end.

Alternative considered: documenting OpenSpec as pending. Rejected because the
CLI is already installed and the integration can be tested now.

### Configuration test instead of CI duplication

The existing `backend` CI job already runs pytest. Adding one fast unit test is
enough to validate the foundation; no workflow change is required.

Alternative considered: a new CI job. Rejected as duplicate, slower, and more
maintenance for no additional coverage.

### TDD demonstration without an application feature

The configuration test was written first and observed failing (22 failures)
before the foundation files existed. This demonstrates red/green without adding
an artificial product feature.

## Risks / Trade-offs

- **Model IDs change or provider access changes.** → The config test fails
  loudly; update the agent file and the allow-list after re-verification.
- **Permissions are too broad.** → Read-only agents are tested; destructive
  shell commands are denied; deploy actions require approval.
- **Permissions are too narrow and block legitimate work.** → Users can grant a
  one-off permission or adjust the agent file in a reviewed change; do not
  weaken read-only review by default.
- **Documentation drifts from commands.** → `QUALITY_GATES.md` mirrors
  `pyproject.toml` and CI; validation runs the actual commands.
- **OpenSpec adds process overhead.** → It is required only for the documented
  substantial-change categories; trivial work keeps a proportionate path.
- **Skill descriptions grow and cause over-activation.** → Keep each
  description to a specific trigger; the config test caps length.

## Migration Plan

There is no application or database migration. The change is additive; rollback
is a revert of the feature commit. OpenSpec archive updates the main spec after
validation. Production is unaffected.

## Open Questions

None.
