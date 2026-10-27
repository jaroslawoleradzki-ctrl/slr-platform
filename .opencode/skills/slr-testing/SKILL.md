---
name: SLR Testing
description: Use when implementing a behavior change, fixing a bug, designing a test strategy, adding regression coverage, or responding to a Ruff, mypy, pytest, TypeScript, Vitest, or frontend-build failure.
---

# SLR Testing

## Activation criteria

Activate for:

- every behavioral change, including bug fixes;
- new API, service, repository, provider, importer, migration, or UI behavior;
- CI failures or flaky tests;
- test-strategy questions and regression planning.

Documentation-only and non-behavioral configuration changes may use the
proportionate validation path in `AGENTS.md` section E.

## Required context

Read `AGENTS.md`, then:

- `docs/testing-standard.md`;
- `pyproject.toml` (pytest, Ruff, mypy settings);
- `tests/conftest.py` and the nearest existing tests;
- `tests/fixtures/` for deterministic data;
- the affected module and its public contract.

## Workflow

1. State the behavior and acceptance criteria in one or two sentences.
2. Choose the lowest test level that proves it: unit, contract, or integration.
3. Write a failing test first. Confirm it fails for the intended reason.
4. Implement the smallest production change.
5. Run the targeted test module and make it green.
6. Refactor only while green.
7. Run the regression gates that cover the change.
8. Record the red/green command and result in the implementation report.

Test-level guidance:

- Unit: pure rules, normalization, mapping, decision semantics, edge cases.
- Contract: provider/import/provider-mapper contracts and API schemas.
- Integration: repository + SQLite + service/API flow, migrations, exports.
- Frontend: component behavior with Vitest and Testing Library.

Determinism rules:

- Use short, anonymous fixtures committed to the repository.
- Inject clocks, IDs, and sleeps where the code already supports it.
- Never call live APIs from a unit test.
- Keep each test's SQLite database disposable; rely on
  `SLR_DATABASE_PATH` isolation in `tests/conftest.py`.
- Avoid order dependence and shared mutable state.

## Safety constraints

- Do not weaken, skip, or delete a failing test to make a change pass.
- Do not mock the integrity boundary being tested.
- Do not use production data or the live database.
- Do not add timing-dependent assertions or sleeps.
- Do not introduce an artificial application feature just to demonstrate TDD.
- Do not commit generated caches, coverage artifacts, or local databases.

## Validation

```bash
uv run --frozen --no-sync pytest -q -p no:cacheprovider <targeted-tests>
uv run --frozen --no-sync ruff check app tests scripts
uv run --frozen --no-sync mypy app
git diff --check
```

For frontend work:

```bash
cd frontend
npm run type-check
npm test
npm run build
```

Migration work also runs:

```bash
uv run --frozen --no-sync pytest -q tests/unit/repositories tests/integration -k "migration or reconciliation"
```

## Expected outputs

- Tests added or updated, with names that state the invariant.
- Red and green command evidence.
- Full relevant gate results.
- Any gate that could not run, reported as **NOT VERIFIED**.
- Residual risk and follow-up tests.

## References

- `AGENTS.md` sections E and F
- `docs/testing-standard.md`
- `pyproject.toml`
- `tests/conftest.py`
- `tests/unit/`, `tests/integration/`, `tests/contract/`
- `tests/fixtures/`
- `.github/workflows/ci.yml`
