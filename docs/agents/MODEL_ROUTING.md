# Model Routing

Routing is risk-based, not agent-count-based. The goal is the smallest set of
agents and model calls that produces a safe, reviewable change.

## Verified availability

Verified on **2026-10-27** with OpenCode **v2.2.0** and `opencode models` against
the installed provider configuration. These are concrete provider/model IDs,
not guesses.

| Agent | Preferred model | Configured ID | Fallback | Mode |
|---|---|---|---|---|
| `slr-architect` | Nemotron 3 Ultra | `opencode/nemotron-3-ultra-free` | `opencode/mimo-v2.6-flash-free` | all |
| `slr-developer` | Muse Spark 1.3 Contributor | `opencode-go/muse-spark-1.3-contributor` | `opencode/mimo-v2.6-flash-free` | all |
| `slr-qa` | Nemotron 3.5 Lightning | `opencode/nemotron-3.5-lightning-free` | `opencode/mimo-v2.6-flash-free` | all |
| `slr-research-reviewer` | Nemotron 3 Ultra | `opencode/nemotron-3-ultra-free` | `opencode/mimo-v2.6-flash-free` | all |
| `slr-release-engineer` | Nemotron 3.5 Lightning | `opencode/nemotron-3.5-lightning-free` | `opencode/mimo-v2.6-flash-free` | all |

Notes:

- `opencode/*-free` IDs are free-tier model identifiers exposed by the default
  OpenCode provider. They are suitable for read-only analysis and review.
- `opencode-go/muse-spark-1.3-contributor` is the project owner's preferred
  implementation model and is **pre-authorized** for implementation tasks. Its
  list prices are approximately $0.10 per million input tokens and $0.20 per
  million output tokens in the current catalog. Any other paid model, provider,
  or credit purchase requires explicit authorization.
- The fallback is the free `opencode/mimo-v2.6-flash-free` variant. Do not
  silently switch to a paid model.
- The model list is environment-dependent. The configuration test checks the
  live `opencode models` catalog when the CLI is available; add a separate
  deterministic guard if a provider-related CI environment becomes available.
- Agent `model:` values are preferences. A user can override the model at
  invocation time without breaking the agent definition.

Fallback invocation:

```bash
opencode run --agent slr-developer \
  --model opencode/mimo-v2.6-flash-free \
  "Continue the approved implementation. Keep the existing tests green."
```

Use the fallback when the preferred model is unavailable or when the task is
small enough that the free model is sufficient. Record the fallback in the task
report only if it changes review confidence.

## HTTP 429 and unavailable models

Provider quota errors are operational, not proof that the configuration is
broken.

1. Retry once after a short backoff.
2. Switch to `opencode/mimo-v2.6-flash-free`.
3. If that fails, stop and report **NOT VERIFIED**.
4. Use a paid model only with explicit human authorization.
5. Do not mark configuration validation or end-to-end execution as PASS when
   the call did not complete.

The implementation report must state the exact failure and the fallback used.

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
transformations, migrations, and agent security boundaries.

```text
slr-architect → slr-developer → slr-qa → slr-research-reviewer
```

The research reviewer is a gate, not a rubber stamp. A BLOCK finding returns the
task to the developer. A human must accept any residual methodological risk.

### RELEASE risk

Versioning, integration, GitHub Release, Homelab mirror, deployment.

```text
slr-release-engineer + CI + explicit human approval
```

The release engineer prepares and verifies. It does not merge to main, tag,
publish, or deploy without approval. Deployment is human-run.

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
- Use the free MiMo fallback before requesting a paid model.
- Give each agent only the paths and constraints it needs.
- Ask for a specification or findings, not a codebase summary.
- Stop at approval gates instead of speculating about production.
- Reuse the OpenSpec change artifacts as the shared brief instead of repeating
  context in every prompt.

## Permission summary

| Agent | Edit | Shell | Deploy |
|---|---|---|---|
| `slr-architect` | denied | Git/OpenSpec inspection only | denied |
| `slr-developer` | ordinary source; governance asks; data/secrets/deploy denies | allowlisted test/static/Git commands | denied |
| `slr-qa` | denied | allowlisted tests/static/frontend/OpenSpec | denied |
| `slr-research-reviewer` | denied | Git/OpenSpec and read-only SQLite | denied |
| `slr-release-engineer` | release metadata only | release gates plus approval-required release actions | exact script `ask`; wrappers denied |

No agent may launch nested subagents. The human controls the chain.
