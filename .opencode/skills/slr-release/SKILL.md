---
name: SLR Release
description: Use when preparing an SLR Platform version, updating VERSION or CHANGELOG, integrating development into main, creating a GitHub Release, mirroring to Homelab, or planning deployment and rollback.
---

# SLR Release

## Activation criteria

Activate for:

- a version bump, changelog, release notes, or release report;
- `development` → `main` integration, including release-specific
  `integration/` branches;
- GitHub Release or tag creation;
- Homelab mirror synchronization;
- deployment preflight, post-deployment verification, or rollback planning.

A release is a RELEASE-risk activity. It always requires CI and explicit human
approval.

## Required context

Read `AGENTS.md`, then:

- `VERSION`, `pyproject.toml`, `frontend/package.json`;
- `CHANGELOG.md`, `docs/VERSIONING.md`;
- the latest `docs/releases/` and `docs/reviews/` reports;
- `.github/workflows/ci.yml` and the latest CI result;
- `scripts/deploy_ai_node.sh`, `compose.yaml`, and
  `docs/runbooks/CI_SELF_HOSTED_RUNNER.md` when deployment is in scope;
- the wrapper's `status`/`log` output and the relevant tags (read-only tag
  listing requires approval).

## Workflow

1. Confirm the release scope and that every intended change is merged and
   covered by a green CI run.
2. Choose the semantic version under `docs/VERSIONING.md` pre-1.0 rules.
3. Update `VERSION` as the source of truth, then synchronize
   `pyproject.toml` and `frontend/package.json`.
4. Update `CHANGELOG.md` and write `docs/releases/vX.Y.Z.md`.
5. Run the full quality gates and a clean build.
6. Prepare the release report with scope, tests, known limitations, and
   rollback notes.
7. Integrate `development` into `main` with human approval; release-specific
   `integration/` branches follow the same approval rule. Do not rewrite
   history or force-push.
8. Tag the release and create the GitHub Release only after approval.
9. Mirror to Homelab using the established procedure; verify the mirror.
10. Run deployment preflight. Deployment is human-run; the agent may request
    the exact `scripts/deploy_ai_node.sh` through the approval prompt, but shell
    wrappers, `sudo`, `ssh`, and Docker compose deployment are denied. Then
    perform post-deployment verification.
11. Keep the previous version and database backup available for rollback.

## Safety constraints

- No autonomous production deployment. A human must authorize and run the
  deploy step.
- No release with failing or missing CI.
- No tag or release from a dirty worktree.
- No merge to main, push, tag, GitHub Release, or `gh api` without approval.
- No force-push, history rewrite, or branch deletion.
- No secrets in release notes, logs, or reports.
- No schema-destructive operation without a tested recovery path.
- Do not modify dependency/build configuration or audit reports without
  approval.
- Do not modify unrelated Docker stacks or FINNARO infrastructure.
- Do not claim a deployment succeeded without post-deployment evidence.

## Validation

```bash
python3 scripts/agent/safe_git_inspect.py status --short
python3 scripts/agent/safe_git_inspect.py diff --check
bash scripts/agent/safe_pytest.sh
uv run --frozen --no-sync ruff check app tests scripts
uv run --frozen --no-sync mypy app
npm --prefix frontend run type-check
npm --prefix frontend test
npm --prefix frontend run build
```

Use the read tool to compare `VERSION`, `pyproject.toml`, and
`frontend/package.json`; do not use shell `cat`.

Post-deployment verification: health endpoint, version endpoint, a read-only
project/workflow smoke check, and a log check for errors.

## Expected outputs

- Version bump and synchronized manifests.
- Changelog and release notes.
- Release report with CI evidence and known limitations.
- Tag and GitHub Release (after approval).
- Homelab mirror verification.
- Deployment preflight, post-deployment verification, and rollback plan.

## References

- `AGENTS.md` sections D, F, and G
- `VERSION`, `pyproject.toml`, `frontend/package.json`
- `CHANGELOG.md`
- `docs/VERSIONING.md`
- `docs/releases/`, `docs/reviews/`
- `.github/workflows/ci.yml`
- `scripts/deploy_ai_node.sh`
- `compose.yaml`
