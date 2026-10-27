---
name: SLR Git Workflow
description: Use when starting work, creating a branch or worktree, committing, preparing a pull request, resolving a merge, or checking CI on SLR Platform.
---

# SLR Git Workflow

## Activation criteria

Activate when:

- starting or finishing a task;
- choosing a branch, worktree, or integration baseline;
- committing, rebasing, merging, or opening a pull request;
- investigating CI status or a merge conflict.

## Required context

Read `AGENTS.md`, then inspect:

```bash
python3 scripts/agent/safe_git_inspect.py status --short
python3 scripts/agent/safe_git_inspect.py worktree-list
python3 scripts/agent/safe_git_inspect.py branch-current
python3 scripts/agent/safe_git_inspect.py log --oneline -5
```

Direct `git` inspection commands are denied; use
`python3 scripts/agent/safe_git_inspect.py` for status, diffs, history,
worktrees, and commit metadata.

Also read `.github/workflows/ci.yml` and the current task/report when present.

## Workflow

1. Fetch `origin` and identify the correct baseline (`origin/development` for
   feature work unless the task says otherwise).
2. Create a dedicated worktree and branch. Never implement in the protected
   development checkout; identify it with
   `python3 scripts/agent/safe_git_inspect.py worktree-list`.
3. Confirm the branch and worktree do not already exist. If they do, inspect
   and stop instead of overwriting.
4. Keep the change scoped to one logical outcome.
5. Run the quality gates before each commit. Agent sessions use
   `bash scripts/agent/safe_pytest.sh`.
6. Commit with a conventional message, for example:
   - `feat(import): preserve source-record identity`
   - `fix(dedup): keep uncertain candidates pending`
   - `docs(agents): document risk routing`
   - `test(agents): validate agent configuration`
7. Push only the task branch. Do not force-push.
8. Open a pull request with scope, risk tier, tests, and known limitations.
9. Merge only with human approval and green CI.

Branch prefixes in use: `feature/`, `fix/`, `release/`, `audit/`, `ci/`, and
release-specific `integration/` branches.

## Safety constraints

Never run:

```text
git reset --hard
git clean
git stash
git restore .
git checkout -- .
git worktree remove
git branch -D
git -C <path> reset --hard
git -C <path> clean
git push --force
```

Also:

- Never modify the protected development worktree.
- Never delete branches or worktrees you did not create.
- Never commit `.env`, secrets, databases, caches, or generated build output.
- Never bypass a failing CI gate by weakening it.
- Never push to `main` or `development` as part of a feature task.
- Do not alter self-hosted runner configuration or FINNARO workflows.

The agents default-deny shell access; destructive commands are not allowlisted.

## Validation

```bash
python3 scripts/agent/safe_git_inspect.py status --short
python3 scripts/agent/safe_git_inspect.py diff --check
python3 scripts/agent/safe_git_inspect.py diff --stat
uv run --frozen --no-sync ruff check app tests scripts
uv run --frozen --no-sync mypy app
uv run --frozen --no-sync pytest -q -p no:cacheprovider
npm --prefix frontend run type-check
npm --prefix frontend test
npm --prefix frontend run build
```

CI is authoritative: `.github/workflows/ci.yml`.

## Expected outputs

- Isolated worktree and branch name.
- Logical commit(s) with clear messages.
- PR description with scope, risk, tests, and limitations.
- CI result and any **NOT VERIFIED** gate.
- No unintended files in the wrapper's `status` output.

## References

- `AGENTS.md` sections D, F, and G
- `.github/workflows/ci.yml`
- `docs/runbooks/CI_SELF_HOSTED_RUNNER.md`
- `docs/VERSIONING.md`
- `scripts/ci/check_runner_policy.sh`
