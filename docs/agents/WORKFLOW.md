# Agent Workflow

Practical sequence for SLR Platform work. The root [`AGENTS.md`](../../AGENTS.md)
wins over this document if they conflict.

## 1. Start a task safely

```bash
git fetch origin --prune
git worktree list
git branch -a
```

Identify the protected development checkout from `git worktree list`; it is the
repository root, not a task worktree. Confirm the target branch/worktree does
not already exist. Create an isolated worktree from the latest agreed baseline,
normally `origin/development`:

```bash
git worktree add -b feature/<name> <path-outside-the-protected-checkout> origin/development
cd <path-outside-the-protected-checkout>
```

Never implement in the protected development checkout. The task branch is the
only thing you push.

## 2. Classify risk before choosing agents

| Risk | Examples | Workflow |
|---|---|---|
| LOW | docs, simple UI, isolated bug fix | `slr-developer` → `slr-qa` |
| MEDIUM | API change, multi-file change, new behavior | `slr-architect` → `slr-developer` → `slr-qa` |
| HIGH | import/DOI/dedup/PRISMA/screening/QA/extraction/synthesis/migrations | `slr-architect` → `slr-developer` → `slr-qa` → `slr-research-reviewer` |
| RELEASE | versioning, integration, deployment prep | `slr-release-engineer` + CI + human approval |

Do not run all five agents for every task. A typo fix does not need an
architecture review, and a migration is not complete without an integrity
review.

## 3. Use OpenSpec when the change warrants it

OpenSpec is initialized at `openspec/` with the `spec-driven` schema.

**Required** for:

- new features;
- architectural or API contract changes;
- schema or migration changes;
- research-methodology-sensitive changes;
- substantial multi-file refactoring.

**Not required** for trivial fixes, documentation-only changes, comment or
formatting changes, and small non-behavioral configuration updates.

The supported sequence is:

1. **Proposal** — what and why, risk tier, out of scope.
2. **Requirements** — observable `SHALL` statements.
3. **Acceptance criteria** — `WHEN`/`THEN` scenarios.
4. **Design** — affected layers, contracts, migrations, rollback.
5. **Tasks** — test-first, ordered, with validation commands.
6. **Implementation** — `/opsx-apply` or direct work.
7. **Verification** — tests, quality gates, independent review.
8. **Archive** — `/opsx-archive` after the change is complete.

Useful commands:

```bash
openspec list
openspec list --specs
openspec new change "<kebab-case-name>"
openspec status --change "<name>" --json
openspec instructions <artifact-id> --change "<name>" --json
openspec validate --all --strict
openspec archive "<name>" --yes
```

The generated `/opsx-*` commands and `openspec-*` skills provide the detailed
workflow. Keep proposals short. The value is the explicit contract and the
verification trail, not document volume.

The CI CLI is pinned to `@fission-ai/openspec@1.15.0`. Generated skills and
commands are version-controlled. When the pinned version changes, run
`openspec update`, review the generated diff, and commit it with the CLI version
change. Do not hand-edit generated OpenSpec artifacts.

## 4. Apply TDD

For behavioral work:

1. State the expected behavior and acceptance criteria.
2. Add the smallest failing test. Run it and confirm the failure reason.
3. Implement the smallest change that makes it pass.
4. Run the targeted test module.
5. Refactor while green.
6. Run regression and static checks.
7. Record the failing command/output, the green command/output, the refactor
   verification, and the relevant test diff in the report.

Example:

```bash
bash scripts/agent/safe_pytest.sh tests/unit/services/test_<area>.py

# implement

bash scripts/agent/safe_pytest.sh tests/unit/services/test_<area>.py
uv run --frozen --no-sync ruff check app tests scripts
uv run --frozen --no-sync mypy app
```

A green CI run proves the final state, not that the test was written first. Say
so explicitly rather than claiming unverified red-first discipline.

Use the proportionate exception for documentation, comments, formatting, and
non-behavioral configuration. Configuration changes still need a deterministic
validation test where practical; the agent foundation itself is validated by
`tests/unit/test_agent_foundation_configuration.py`.

## 5. Independent review

QA and research review are deliberately read-only.

```bash
opencode run --agent slr-qa \
  "Verify the current branch. Run the gates in docs/agents/QUALITY_GATES.md. Report PASS, PASS WITH CONDITIONS, FAIL, or NOT VERIFIED, with exact commands."

opencode run --agent slr-research-reviewer \
  "Review the current branch for PRISMA, provenance, duplicate, screening, QA, extraction, synthesis, and audit-trail integrity. Report BLOCK or PASS WITH CONDITIONS. Do not edit."
```

The reviewer must not fix its own findings. A HIGH-risk change is not done until
the research reviewer has signed off or a human has explicitly accepted the
residual risk.

## 6. Prepare a release

Use `slr-release-engineer` and the `slr-release` skill. The sequence is:

1. Green CI and clean worktree.
2. Semver decision under `docs/VERSIONING.md`.
3. `VERSION` update, then `pyproject.toml` and `frontend/package.json`.
4. `CHANGELOG.md`, `docs/releases/vX.Y.Z.md`, and a release report.
5. Full quality gates and a clean build.
6. Human-approved `development` → `main` integration. Release-specific
   `integration/` branches follow the same approval rule.
7. Human-approved tag, GitHub Release, Homelab mirror, and human-run
   deployment.
8. Post-deployment verification and rollback readiness.

No agent may merge to main, tag, publish, or deploy without explicit human
authorization. The exact deployment script is at most an approval request; shell
wrappers, `sudo`, `ssh`, and Docker compose deployment are denied.

## 7. Handle a blocked task

Stop and report when:

- acceptance criteria or methodology are ambiguous;
- a migration would be destructive or unrecoverable;
- a test failure reveals an integrity problem;
- the change needs an API or schema decision not covered by the spec;
- credentials, production access, or paid credits are required.

A blocked report should state:

- what was attempted;
- the exact error or contradiction;
- evidence (file, line, command, test);
- the safest options;
- the decision needed from a human.

Do not "work around" a blocker by weakening a test, deleting data, force-pushing,
or silently reducing scope.

## 8. Minimize token consumption

- Start with `AGENTS.md`; load only the skill that matches the task.
- Give the agent the narrowest useful prompt and the relevant paths.
- Run one agent, not the whole chain, when the risk does not justify it.
- Use `slr-architect` for a short specification, then hand the spec to
  `slr-developer`; do not ask the architect to implement.
- Use targeted pytest modules while iterating; run the full suite once before
  commit.
- Ask for findings and evidence, not a restatement of the code.
- Avoid attaching large files when a path or symbol is enough.
- Stop at a human approval gate instead of spending tokens on speculative work.
