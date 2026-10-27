# Model Routing

Routing is risk-based, not agent-count-based. The goal is the smallest set of
agents and model calls that produces a safe, reviewable change.

## Verified availability

Verified on **2026-10-27** with OpenCode **v2.2.0** and `opencode models` against
the installed provider configuration. These are concrete provider/model IDs,
not guesses.

| Agent | Preferred model | Configured ID | Fallback | Mode |
|---|---|---|---|---|
| `slr-architect` | Nemotron 3 Ultra | `opencode/nemotron-3-ultra-free` | `opencode-go/mimo-v2.6-flash` | all |
| `slr-developer` | Muse Spark 1.3 Contributor | `opencode-go/muse-spark-1.3-contributor` | `opencode-go/mimo-v2.6-flash` | all |
| `slr-qa` | Nemotron 3.5 Lightning | `opencode/nemotron-3.5-lightning-free` | `opencode-go/mimo-v2.6-flash` | all |
| `slr-research-reviewer` | Nemotron 3 Ultra | `opencode/nemotron-3-ultra-free` | `opencode-go/mimo-v2.6-flash` | all |
| `slr-release-engineer` | Nemotron 3.5 Lightning | `opencode/nemotron-3.5-lightning-free` | `opencode-go/mimo-v2.6-flash` | all |

Notes:

- `opencode/*-free` IDs are free-tier model identifiers exposed by the default
  OpenCode provider. They are suitable for read-only analysis and review.
- `opencode-go/muse-spark-1.3-contributor` and
  `opencode-go/mimo-v2.6-flash` are OpenCode Go identifiers and may consume
  paid credits. Do not install providers, buy credits, or switch to a paid
  model without authorization.
- The model list is environment-dependent. If an ID disappears, update the
  agent file and `KNOWN_MODELS` in
  `tests/unit/test_agent_foundation_configuration.py`, then re-run the
  configuration test.
- Agent `model:` values are preferences. A user can override the model at
  invocation time without breaking the agent definition.

Fallback invocation:

```bash
opencode run --agent slr-developer \
  --model opencode-go/mimo-v2.6-flash \
  "Continue the approved implementation. Keep the existing tests green."
```

Use the fallback when the preferred model is unavailable or when the task is
small enough that the cheaper model is sufficient. Record the fallback in the
task report only if it changes review confidence.

## Risk-based workflows

### LOW risk

Documentation, simple UI copy/layout, an isolated bug fix with an obvious
cause.

```text
slr-developer → slr-qa
```

Skip the architect. The developer writes the failing regression test, fixes the
bug, and QA verifies it. A docs-only change may skip QA if the diff is purely
documentation and `git diff --check` passes; state that choice in the report.

### MEDIUM risk

API changes, multi-file behavior, a new workflow path, a dependency-free
service refactor.

```text
slr-architect → slr-developer → slr-qa
```

The architect produces a short specification and acceptance criteria. The
developer implements test-first. QA verifies independently. Do not send the
architect back through the whole codebase after implementation unless the
contract changed.

### HIGH risk

Import integrity, RIS/BibTeX, DOI normalization, deduplication, PRISMA,
screening, quality assessment, extraction, synthesis, research-data
transformations, migrations.

```text
slr-architect → slr-developer → slr-qa → slr-research-reviewer
```

The research reviewer is a gate, not a rubber stamp. A BLOCK finding returns the
task to the developer. A human must accept any residual methodological risk.

### RELEASE risk

Versioning, `development` → `main` integration, GitHub Release, Homelab mirror,
deployment.

```text
slr-release-engineer + CI + explicit human approval
```

The release engineer prepares and verifies. It does not tag, publish, or deploy
without approval. Deployment is never autonomous.

## Handoff contract

Every handoff should include:

- task and risk tier;
- branch and worktree;
- acceptance criteria;
- files/areas touched;
- commands run and results;
- open questions or accepted risks.

Keep handoffs short. A specification, a diff, and a test result are more useful
than a narrative.

## Token-cost control

- Use one agent per role; do not run the full five-agent chain for LOW work.
- Prefer the free Nemotron models for read-only analysis and review.
- Use the developer model for implementation and test iteration.
- Give each agent only the paths and constraints it needs.
- Ask for a specification or findings, not a codebase summary.
- Stop at approval gates instead of speculating about production.
- Reuse the OpenSpec change artifacts as the shared brief instead of repeating
  context in every prompt.

## Permission summary

| Agent | Edit | Shell | Deploy |
|---|---|---|---|
| `slr-architect` | denied | read-only commands | denied |
| `slr-developer` | allowed in source; sensitive paths ask | broad, release/deploy actions ask or deny | denied |
| `slr-qa` | denied | test/static-analysis commands only | denied |
| `slr-research-reviewer` | denied | read-only commands and tests | denied |
| `slr-release-engineer` | release metadata only | broad, release actions ask | ask, never automatic |

No agent may launch nested subagents. The human controls the chain.
