# AGENTS.md — SLR Platform

Authoritative instructions for every coding agent working in this repository.
Read this file first. Detailed procedures live in `docs/agents/` and
`.opencode/skills/`. Where this file conflicts with `docs/session-start.md`,
this file wins.

Current application baseline: **v0.7.3** (root `VERSION` file).

## A. Project identity

SLR Platform supports systematic literature reviews (SLRs). It is a
**deterministic research workflow platform**, not an AI research assistant.

- No embedded LLM and no runtime dependency on an AI service.
- No autonomous AI screening, AI-based quality assessment, AI duplicate
  resolution, AI extraction, or AI-generated methodological decisions.
- Human reviewers own every scientific decision.
- External coding agents may help develop the software. They are development
  tooling, not part of the product and not a source of research truth.

## B. Verified architecture

### Technology stack

| Area | Verified stack |
|---|---|
| Backend | Python 3.12, FastAPI, Pydantic v2, `httpx`, `tenacity`, SQLite (`sqlite3`) |
| Reporting | `openpyxl` (XLSX), `fpdf2` (PDF), deterministic SVG writers |
| Frontend | React 18, TypeScript 5.7, Vite 6, Vitest 2, React Router 6 |
| Tooling | `uv` 0.11, Ruff, mypy, pytest, npm |
| CI | GitHub Actions on the dedicated self-hosted `ai-node-slr-platform` runner |

### Repository map

```text
app/api/          FastAPI app, routers, DTOs
app/domain/       Immutable domain models and value objects
app/services/     Business rules and orchestration
app/repositories/ SQLite adapters and persistence boundaries
app/providers/    Search and file-import providers
app/adapters/     External-system adapters
app/workflow/     Workflow state and transitions
app/storage/      Raw-response archive and storage helpers
app/rendering/    Provider query renderers
app/modules/      Legacy/compatibility module entry points
migrations/       Numbered SQL migrations (NNNN_description.sql)
tests/            unit, integration, contract, fixtures
frontend/         React/TypeScript SPA
docs/             Architecture, ADRs, runbooks, plans, reviews, releases
scripts/          Developer, CI, reconciliation, and deployment scripts
```

### API conventions

- Base prefix: `/api/v1`; health at `/api/health`, version at `/api/version`,
  OpenAPI at `/api/docs` and `/api/openapi.json`.
- Most resources are project-scoped: `/projects/{project_id}/...`.
- Routers stay thin; business rules belong in `app/services/`; persistence
  belongs in `app/repositories/`; request/response models belong in
  `app/api/dto/`.
- Use FastAPI dependency injection and explicit response models.
- Preserve existing response fields and status codes unless a change is
  explicitly approved as breaking.

### Database conventions

- SQLite is the only application database. SQL migrations are numbered files
  in `migrations/` and are applied idempotently through `schema_migrations` by
  the owning repository's `_apply_migrations()` method.
- Never edit an already-applied migration; add a new numbered migration.
- Preserve the transactional boundaries used by the affected repositories.
- Decision and audit tables are append-only where the existing design says so.
- Tests must use a disposable database. `tests/conftest.py` sets
  `SLR_DATABASE_PATH` to a `tmp_path` database per test.
- Do not assume foreign keys exist everywhere; parts of the schema predate
  `projects` as a physical parent table (see
  `docs/SQLITE_CONSTRAINTS_REVIEW.md`).

### Frontend conventions

- API access lives under `frontend/src/api/` and `frontend/src/services/`.
- Shared types live in `frontend/src/types/`; selectors in
  `frontend/src/selectors/`.
- Components are grouped by workflow area under `frontend/src/components/`.
- Use the existing functional-component, hooks, and context patterns.
- TypeScript must pass `npm run type-check`; behavior tests use Vitest.

### Test commands

```bash
# Backend (from repository root)
uv sync --frozen --extra dev --python 3.12
uv run --frozen --no-sync ruff check app tests scripts
uv run --frozen --no-sync mypy app
uv run --frozen --no-sync pytest -q -p no:cacheprovider

# Agent sessions: disposable SQLite database and temporary directory
bash scripts/agent/safe_pytest.sh
bash scripts/agent/safe_pytest.sh tests/unit/test_agent_foundation_configuration.py

# Frontend (agents use the --prefix form)
npm --prefix frontend run type-check
npm --prefix frontend test
npm --prefix frontend run build

# OpenSpec, migration safety, and diff hygiene
openspec validate --all --strict
uv run --frozen --no-sync python scripts/ci/check_migration_safety.py --base-ref origin/development
git diff --check
```

The CI workflow (`.github/workflows/ci.yml`) is the authoritative gate. Its
backend job runs on a disposable SQLite database outside the checkout; the
frontend job runs the Node checks. CI also runs diff hygiene, pinned OpenSpec
strict validation, and the migration-safety guard. Do not weaken, skip, or
duplicate those jobs.

## C. Research integrity (non-negotiable)

Preserve these without exception:

- PRISMA accounting and its single counting path (`PrismaMetricsService`).
- Publication provenance (`ProvenanceEntry`), source-record identity, raw
  response archives, and import provenance.
- Canonical DOI normalization (`app/normalization/doi.py`); do not fork it.
- Duplicate review decisions and the human approval record.
- Screening decisions, criterion snapshots, and reviewer attribution.
- Quality assessment records and their configuration snapshots.
- Data extraction records and field-state contracts (ADR-0007).
- Synthesis records, immutable synthesis snapshots, and traceability.
- Audit trails: `search_run_audits`, `import_history`, `import_skip_audit`,
  `normalization_executions`, `screening_decisions`, `pre_screening_archive`,
  and related run/decision ledgers.

Hard rules:

- Never silently discard, overwrite, or "clean up" research records.
- Never automatically merge uncertain duplicates. Uncertain means human review.
- Never fabricate publication metadata, identifiers, counts, or provenance.
- Never silently change a methodological decision, criterion, population, or
  PRISMA stage.
- Never replace a human scientific decision with a model recommendation.
- Any destructive or corrective data operation needs an explicit, auditable,
  human-approved migration or reconciliation procedure.

## D. Development rules

- Work in an isolated git worktree. The repository-root checkout is the
  protected development worktree; never edit it while implementing a task.
  Identify it with `git worktree list`.
- Use the branch prefixes already in use: `feature/`, `fix/`, `release/`,
  `audit/`, `ci/`, and release-specific `integration/` branches.
- State the task scope and acceptance criteria before editing. Do not expand
  scope opportunistically.
- Keep diffs minimal. No drive-by refactors, formatting churn, dependency
  upgrades, or unrelated renames.
- Add or update regression tests for every behavioral change.
- Treat migrations as production-sensitive: additive first, tested upgrade
  path, explicit rollback/recovery notes.
- Update the relevant documentation (`docs/`, `CHANGELOG.md`, ADRs, runbooks)
  when behavior, contracts, operations, or methodology changes.
- Run the quality gates before committing.
- Produce an implementation report under `docs/reviews/` for non-trivial work.
- Commit in logical, reviewable units. Do not merge into `development` or
  `main` unless the task explicitly says so.

## E. TDD

For behavioral changes:

1. Define the expected behavior and acceptance criteria.
2. Write or update a test that fails for the right reason.
3. Implement the smallest change that makes it pass.
4. Run the relevant test module.
5. Refactor safely while the test stays green.
6. Run the regression suite and static checks.
7. Record in the implementation report:
   - the failing test command and failure evidence;
   - the green test command and result;
   - the refactor verification;
   - the relevant test diff.

A green CI run proves the final state, not that the test was written first.
Reports must state that limitation rather than claiming red-first discipline that
was not evidenced.

Proportionate exceptions: documentation-only, comment-only, formatting-only, and
non-behavioral configuration changes do not need a failing test, but they still
need validation. Agent/skill/CI configuration changes should be validated by a
deterministic configuration test where practical.

Do not write tests that assert implementation details when a contract-level
assertion is possible. Do not weaken an integrity test to make a change pass.
Do not introduce artificial application features solely to demonstrate TDD.

## F. Quality gates

Run the gates that cover the change, plus the full relevant suite before commit.

| Gate | Command |
|---|---|
| Ruff | `uv run --frozen --no-sync ruff check app tests scripts` |
| Mypy | `uv run --frozen --no-sync mypy app` |
| Pytest | `uv run --frozen --no-sync pytest -q -p no:cacheprovider` |
| Agent pytest (disposable DB) | `bash scripts/agent/safe_pytest.sh` |
| Migration-focused tests | `uv run --frozen --no-sync pytest -q tests/unit/repositories tests/integration -k "migration or reconciliation"` |
| Migration safety | `uv run --frozen --no-sync python scripts/ci/check_migration_safety.py --base-ref origin/development` |
| TypeScript | `npm --prefix frontend run type-check` |
| Frontend tests | `npm --prefix frontend test` |
| Frontend build | `npm --prefix frontend run build` |
| OpenSpec | `openspec validate --all --strict` |
| Diff hygiene | `git diff --check` |
| CI | `.github/workflows/ci.yml` |

The full pytest suite is the regression gate; targeted modules are for fast
feedback. A gate that cannot run in the current environment must be reported as
**NOT VERIFIED**, never as pass. CI must run before a branch is called
merge-ready.

## G. Security and operational boundaries

- Never expose, print, commit, or paste secrets, tokens, `.env` contents, or
  files under `~/.config/opencode/secrets/`.
- Never read or modify `data/`, `projects/`, database files, backups, or
  production database paths from an agent shell. Use the disposable test wrapper
  and the native read tool with the documented path restrictions.
- Never modify production infrastructure, production databases, or unrelated
  Docker stacks without explicit human authorization.
- Never delete user data, research records, branches, or worktrees to "clean up".
- Do not change the self-hosted runner configuration or affect FINNARO
  workflows/runners.
- Do not deploy from an agent session. Deployment is human-run. Agents must not
  invoke `bash`/`sh`/`./scripts/deploy_ai_node.sh`, `sudo`, `ssh`, or Docker
  compose deployment commands; the release engineer may only request the exact
  deployment script through the human approval prompt.
- Do not install providers or add dependencies without authorization and a
  documented reason. The configured
  `opencode-go/muse-spark-1.3-contributor` developer model is pre-authorized by
  the project owner for implementation tasks; any other paid model or provider
  requires explicit authorization. Prefer the free
  `opencode/mimo-v2.6-flash-free` fallback.

## H. Definition of done

A task is complete only when:

- acceptance criteria are met;
- relevant tests pass and regression evidence exists;
- TDD evidence is recorded when the change is behavioral;
- Ruff, mypy, TypeScript, frontend tests/build, OpenSpec, migration safety, and
  diff hygiene pass as applicable;
- documentation is updated;
- changes are committed on the task branch;
- an implementation/review report is available when required.

A branch is **merge-ready** only when the CI run for the exact commit is green.
Use exactly one of these statuses:

- **PASS** — the evidence exists, including green CI for merge readiness.
- **PASS WITH CONDITIONS** — local evidence is green but a named condition
  remains, such as CI not yet run.
- **BLOCK** — a critical or high-severity finding remains.
- **NOT VERIFIED** — the gate or environment was unavailable.

Do not report PASS when CI has not run.

## I. Agent routing and skills

Use the smallest workflow that fits the risk:

| Risk | Typical work | Workflow |
|---|---|---|
| LOW | docs, simple UI, isolated bug fix | `slr-developer` → `slr-qa` |
| MEDIUM | API changes, multi-file work, new behavior | `slr-architect` → `slr-developer` → `slr-qa` |
| HIGH | import/DOI/dedup/PRISMA/screening/QA/extraction/synthesis/migrations | `slr-architect` → `slr-developer` → `slr-qa` → `slr-research-reviewer` |
| RELEASE | versioning, integration, deployment prep | `slr-release-engineer` + CI + human approval |

Do not run all five agents for every task. See
`docs/agents/MODEL_ROUTING.md` for model IDs, fallbacks, cost control, and
handoff rules.

Repository-local skills are auto-discovered from
`.opencode/skills/<skill-id>/SKILL.md`; agents from
`.opencode/agents/<agent-id>.md`. Load a skill explicitly with `@skill-id` or
let OpenCode activate it from its description.

All five agents use default-deny shell permissions with narrow allowlists.
OpenCode permissions are not a filesystem sandbox; see
`scripts/agent/README.md` and `docs/agents/SECURITY_MODEL.md` for the residual
risk and the disposable test wrapper.
