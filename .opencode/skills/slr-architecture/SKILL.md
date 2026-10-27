---
name: SLR Architecture
description: Use when planning or reviewing SLR Platform architecture, API boundaries, frontend/backend contracts, dependency changes, backward compatibility, or an architectural decision record.
---

# SLR Architecture

## Activation criteria

Activate for MEDIUM or HIGH risk work that changes a contract or crosses
layers, including:

- new or changed FastAPI routes, DTOs, response shapes, or status codes;
- changes to domain models, service boundaries, repository protocols, or
  provider/import adapters;
- frontend/backend contract changes or new workflow state;
- new dependencies, shared abstractions, or cross-module refactors;
- architecture-sensitive documentation or ADR work.

Do not activate for documentation-only edits or isolated bug fixes that stay
inside one existing boundary.

## Required context

Read `AGENTS.md` first, then:

- `docs/ARCHITECTURE.md`, `docs/DECISIONS.md`, `docs/adr/README.md`;
- `docs/data-model.md` and the relevant ADRs;
- the affected router, DTOs, service, repository, provider, and tests;
- `docs/testing-standard.md` and `pyproject.toml` for constraints.

Inspect the actual code. Do not infer architecture from filenames alone.

## Workflow

1. Describe the current flow and the boundary being changed.
2. Identify the owner of each rule: API, service, repository, provider, or
   frontend. Keep business rules out of routers and transport code.
3. Define the proposed contract: inputs, outputs, errors, ordering,
   idempotency, and backward compatibility.
4. Assess impact on domain invariants, persistence, migrations, exports,
   PRISMA accounting, and research records.
5. Prefer additive changes. Call out any breaking change explicitly.
6. Record a durable decision in `docs/adr/NNNN-*.md` when the choice will
   constrain future work. Do not create an ADR for a reversible local detail.
7. Produce an implementation specification with acceptance criteria and a test
   plan. Stop before implementation.

## Safety constraints

- This skill is analysis-only. Do not edit application code, migrations, or
  production configuration.
- Do not invent endpoints, fields, tables, or commands. Verify them.
- Do not silently change an existing public contract.
- Do not weaken a research-integrity boundary to simplify an interface.
- Do not add an LLM or autonomous decision path to the application.

## Validation

- Every proposed contract maps to an existing or planned test.
- `docs/` and ADR references are real paths.
- The impact list covers API, persistence, frontend, exports, and research
  integrity where applicable.
- `uv run --frozen --no-sync mypy app` and the relevant pytest modules are
  named as post-implementation gates.

## Expected outputs

- Current-state and target-state description.
- Affected files and layers.
- API/data contract and compatibility statement.
- Impact and risk assessment.
- Acceptance criteria and test plan.
- ADR draft when required.
- Explicit open questions and a recommendation.

## References

- `AGENTS.md` sections B, C, and D
- `docs/ARCHITECTURE.md`
- `docs/DECISIONS.md`
- `docs/adr/`
- `docs/data-model.md`
- `docs/testing-standard.md`
- `app/api/`, `app/domain/`, `app/services/`, `app/repositories/`
- `frontend/src/api/`, `frontend/src/types/`
