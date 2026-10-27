# Tasks

## 1. Test-first foundation

- [x] 1.1 Add `tests/unit/test_agent_foundation_configuration.py` and verify it fails before the foundation exists (observed: 22 failures).
- [x] 1.2 Add root `AGENTS.md` with sections A–H and verify the AGENTS.md test passes.

## 2. Project skills

- [x] 2.1 Add the six `slr-*` skills and verify all six parametrized skill tests pass.
- [x] 2.2 Verify every skill has activation criteria, required context, workflow, safety, validation, outputs, and references.

## 3. Specialized agents

- [x] 3.1 Add the five `slr-*` agents with verified model IDs and least-privilege permissions.
- [x] 3.2 Verify agent validity, read-only edit denial, no nested delegation, and release approval gates pass.

## 4. OpenSpec integration

- [x] 4.1 Initialize OpenSpec with `openspec init --tools opencode` and add project context/rules to `openspec/config.yaml`.
- [x] 4.2 Create this change's proposal, spec delta, design, and tasks; run `openspec validate --all --strict`.

## 5. Documentation and reconciliation

- [x] 5.1 Add `docs/agents/README.md`, `WORKFLOW.md`, `MODEL_ROUTING.md`, and `QUALITY_GATES.md`.
- [x] 5.2 Add the reconciliation note to `docs/session-start.md` so `AGENTS.md` is unambiguously authoritative.

## 6. Verification and delivery

- [x] 6.1 Run the configuration test, Ruff, mypy, and `git diff --check`; record results.
- [x] 6.2 Run the full pytest suite and the frontend type-check/test/build; record results.
- [x] 6.3 Write `docs/reviews/SLR_AGENT_ENGINEERING_FOUNDATION_REPORT.md` with audit, files, validation, gaps, and recommendations.
- [x] 6.4 Run `openspec validate --all --strict` and archive the completed change.
- [x] 6.5 Confirm application code and production configuration are unchanged; commit and push only the feature branch.

## Workflow follow-up

- Archive this change only after the report and validation evidence are present.
- Review the archived main spec after archive.
