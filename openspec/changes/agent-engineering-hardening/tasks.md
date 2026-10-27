# Tasks

## 1. Harden agent permissions

- [x] 1.1 Replace broad shell access in all five agents with default-deny rules and role allowlists.
- [x] 1.2 Deny deployment wrappers, `sudo`, `ssh`, Docker compose, database mutation, destructive Git, and release publication forms.
- [x] 1.3 Add governance edit ask/deny rules and read-time secret protections.
- [x] 1.4 Add `scripts/agent/safe_pytest.sh` with disposable database isolation.

## 2. Effective-permission tests

- [x] 2.1 Add an effective-permission evaluator with last-match wildcard semantics.
- [x] 2.2 Cover C-01, C-02, H-01, H-02, H-03, H-05, and M-08 command families.
- [x] 2.3 Cover model catalog availability when the OpenCode CLI is available.
- [x] 2.4 Cover governance, data, secret, and OpenSpec path checks.

## 3. CI quality gates

- [x] 3.1 Add `git diff --check` to CI.
- [x] 3.2 Add pinned OpenSpec strict validation to CI.
- [x] 3.3 Add and test `scripts/ci/check_migration_safety.py`.
- [x] 3.4 Fix temporary CI directory cleanup.
- [x] 3.5 Align CI branch triggers with the documented branch conventions.

## 4. Documentation and policy

- [x] 4.1 Update `AGENTS.md` for TDD evidence, CI-green Definition of Done, branch conventions, paid-model authorization, and security boundaries.
- [x] 4.2 Update model routing for free fallback, paid default authorization, and HTTP 429 handling.
- [x] 4.3 Update quality gates, workflow, README, skills, and session-start guidance.
- [x] 4.4 Document generated OpenSpec artifact update policy and security residual risks.
- [x] 4.5 Correct the foundation report's overstated model/permission verification claims.

## 5. Validation and delivery

- [x] 5.1 Run configuration and effective-permission tests.
- [x] 5.2 Run Ruff, mypy, full backend tests, migration subset, frontend type-check/tests/build.
- [x] 5.3 Run OpenCode agent/skill discovery and OpenSpec strict validation.
- [x] 5.4 Verify no application, production data, or deployment change.
- [x] 5.5 Write the hardening report with the 22-finding remediation matrix.
- [ ] 5.6 Archive the OpenSpec change after validation.
- [ ] 5.7 Commit, push, open/update the PR, and wait for CI.

## Workflow follow-up

- Do not report PASS if CI has not run.
- Do not merge the PR or deploy.
