"""Contract and effective-permission tests for the agent engineering foundation.

These tests are infrastructure tests, not application-behavior tests. They keep
the OpenCode agents, skills, AGENTS.md, and OpenSpec root internally consistent
so a broken or over-privileged configuration cannot silently ship.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
AGENTS_DIR = REPO_ROOT / ".opencode" / "agents"
SKILLS_DIR = REPO_ROOT / ".opencode" / "skills"
AGENTS_MD = REPO_ROOT / "AGENTS.md"
OPENSPEC_DIR = REPO_ROOT / "openspec"

PROJECT_SKILLS = (
    "slr-architecture",
    "slr-research-integrity",
    "slr-testing",
    "slr-database",
    "slr-git-workflow",
    "slr-release",
)

PROJECT_AGENTS = (
    "slr-architect",
    "slr-developer",
    "slr-qa",
    "slr-research-reviewer",
    "slr-release-engineer",
)

READ_ONLY_AGENTS = ("slr-architect", "slr-qa", "slr-research-reviewer")

# Exact provider/model IDs verified against `opencode models` during the
# foundation build. Update this allow-list only after re-verifying availability.
KNOWN_MODELS = {
    "opencode/nemotron-3-ultra-free",
    "opencode/nemotron-3.5-lightning-free",
    "opencode/mimo-v2.6-flash-free",
    "opencode-go/muse-spark-1.3-contributor",
    "opencode-go/mimo-v2.6-flash",
}

OPENCODE_TIMEOUT_SECONDS = 120
REQUIRE_OPENCODE_CLI = os.environ.get("REQUIRE_OPENCODE_CLI") == "1"
SAFE_GIT_WRAPPER = "python3 scripts/agent/safe_git_inspect.py"

SKILL_SECTIONS = (
    "## Activation criteria",
    "## Required context",
    "## Workflow",
    "## Safety constraints",
    "## Validation",
    "## Expected outputs",
    "## References",
)

AGENTS_MD_SECTIONS = (
    "## A. Project identity",
    "## B. Verified architecture",
    "## C. Research integrity",
    "## D. Development rules",
    "## E. TDD",
    "## F. Quality gates",
    "## G. Security",
    "## H. Definition of done",
    "## I. Agent routing and skills",
)

SKILL_REFERENCED_PATHS = (
    "AGENTS.md",
    "docs/ARCHITECTURE.md",
    "docs/DECISIONS.md",
    "docs/adr/README.md",
    "docs/data-model.md",
    "docs/testing-standard.md",
    "docs/SQLITE_CONSTRAINTS_REVIEW.md",
    "docs/EXPORTS_PRISMA.md",
    "docs/DUPLICATE_REVIEW_DECISIONS.md",
    "docs/VERSIONING.md",
    "docs/runbooks/CI_SELF_HOSTED_RUNNER.md",
    "docs/adr/0005-provenance-first-data-model.md",
    "docs/adr/0006-no-autonomous-scientific-decisions.md",
    "docs/adr/0007-extraction-field-state-contract.md",
    "app/normalization/doi.py",
    "app/services/prisma_metrics_service.py",
    "app/api",
    "app/domain",
    "app/services",
    "app/repositories",
    "frontend/src/api",
    "frontend/src/types",
    "tests/conftest.py",
    "tests/fixtures",
    "tests/fixtures/migrations",
    "tests/unit",
    "tests/integration",
    "tests/contract",
    "scripts/ci/check_runner_policy.sh",
    "scripts/deploy_ai_node.sh",
    ".github/workflows/ci.yml",
)


def _split_frontmatter(path: Path) -> tuple[dict[str, Any], str]:
    text = path.read_text(encoding="utf-8")
    parts = text.split("---", 2)
    assert len(parts) == 3, f"{path} must start with a complete YAML frontmatter block"
    assert parts[0].strip() == "", f"{path} must start with '---' on its own line"
    data = yaml.safe_load(parts[1])
    assert isinstance(data, dict), f"{path} frontmatter must be a YAML mapping"
    return data, parts[2]


def _frontmatter(agent_id: str) -> dict[str, Any]:
    frontmatter, _ = _split_frontmatter(AGENTS_DIR / f"{agent_id}.md")
    return frontmatter


def _rules_with(frontmatter: dict[str, Any], action: str, effect: str) -> list[dict[str, Any]]:
    return [
        rule
        for rule in frontmatter.get("permissions", [])
        if rule.get("action") == action and rule.get("effect") == effect
    ]


_WILDCARD_SPECIAL = set(".+^${}()|[]\\")


def _opencode_wildcard(value: str, pattern: str) -> bool:
    """Replicate OpenCode v2's permission wildcard matcher exactly.

    The matcher escapes ``[.+^${}()|[]\\]``, translates ``*`` to ``.*`` and
    ``?`` to ``.``, and evaluates the result with the ``s`` (dot-all) flag.
    A trailing ``" .*"`` also matches without the space.
    """

    value = value.replace("\\", "/")
    translated: list[str] = []
    for character in pattern.replace("\\", "/"):
        if character in _WILDCARD_SPECIAL:
            translated.append("\\" + character)
        elif character == "*":
            translated.append(".*")
        elif character == "?":
            translated.append(".")
        else:
            translated.append(character)
    expression = "".join(translated)
    if expression.endswith(" .*"):
        expression = expression[:-3] + "( .*)?"
    return re.fullmatch(expression, value, flags=re.S) is not None


def effective_effect(frontmatter: dict[str, Any], action: str, resource: str) -> str | None:
    """Evaluate ordered rules with OpenCode's last-match semantics.

    ``resource`` is the actual resource OpenCode passes to the permission
    service (a repository-relative path for file tools, a parsed command node
    for the shell tool). The evaluator returns ``None`` when no declared rule
    matches; callers that require a deny must still ensure a default rule.
    """

    effect: str | None = None
    for rule in frontmatter.get("permissions", []):
        if rule.get("action") not in {action, "*"}:
            continue
        pattern = str(rule.get("resource", ""))
        if _opencode_wildcard(resource, pattern):
            effect = str(rule.get("effect"))
    return effect


def assert_denied(frontmatter: dict[str, Any], command: str) -> None:
    effect = effective_effect(frontmatter, "shell", command)
    assert effect in {"deny", None}, f"expected deny for {command!r}, got {effect!r}"


def assert_allowed(frontmatter: dict[str, Any], command: str) -> None:
    assert effective_effect(frontmatter, "shell", command) == "allow", command


def assert_ask(frontmatter: dict[str, Any], command: str) -> None:
    assert effective_effect(frontmatter, "shell", command) == "ask", command


def assert_edit_effect(frontmatter: dict[str, Any], path: str, expected: str) -> None:
    assert effective_effect(frontmatter, "edit", path) == expected, path


def _opencode_cli() -> str:
    binary = os.environ.get("OPENCODE_BIN") or shutil.which("opencode")
    if not binary or not Path(binary).is_file():
        if REQUIRE_OPENCODE_CLI:
            pytest.fail(
                "OpenCode CLI is required for security verification but was not found; "
                "install the pinned CLI or set OPENCODE_BIN"
            )
        pytest.skip("opencode CLI is not installed in this environment")
    return binary


def _opencode(*args: str) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        [_opencode_cli(), "--standalone", *args],
        check=False,
        capture_output=True,
        text=True,
        timeout=OPENCODE_TIMEOUT_SECONDS,
        cwd=REPO_ROOT,
    )
    if result.returncode != 0:
        message = (result.stderr or result.stdout).strip()[:300]
        if REQUIRE_OPENCODE_CLI:
            pytest.fail(f"opencode {' '.join(args)} failed: {message}")
        pytest.skip(f"opencode {' '.join(args)} unavailable: {message}")
    return result


def merged_agent_permissions(agent_id: str) -> list[dict[str, Any]]:
    """Return the actual merged permissions reported by OpenCode, when available."""

    agents = json.loads(_opencode("debug", "agents").stdout)
    for agent in agents:
        if agent.get("id") == agent_id:
            permissions = agent.get("permissions")
            assert isinstance(permissions, list)
            return permissions
    pytest.fail(f"agent {agent_id} was not reported by opencode debug agents")


def test_agents_md_exists_and_documents_required_contract() -> None:
    assert AGENTS_MD.is_file(), "Root AGENTS.md is required"
    text = AGENTS_MD.read_text(encoding="utf-8")
    for section in AGENTS_MD_SECTIONS:
        assert section in text, f"AGENTS.md is missing section: {section}"
    assert "deterministic research workflow" in text.lower()
    assert "no embedded llm" in text.lower()
    assert "docs/agents/" in text


@pytest.mark.parametrize("skill_id", PROJECT_SKILLS)
def test_project_skill_is_discoverable_and_complete(skill_id: str) -> None:
    path = SKILLS_DIR / skill_id / "SKILL.md"
    assert path.is_file(), f"Missing repository-local skill: {path}"
    frontmatter, body = _split_frontmatter(path)
    assert frontmatter.get("name"), f"{path} must declare a name"
    assert frontmatter.get("description"), f"{path} must declare a description"
    assert len(str(frontmatter["description"])) <= 500, f"{path} description is too long"
    for section in SKILL_SECTIONS:
        assert section in body, f"{path} is missing section: {section}"
    assert "AGENTS.md" in body, f"{path} must reference AGENTS.md"


@pytest.mark.parametrize("path", SKILL_REFERENCED_PATHS)
def test_skill_referenced_path_exists(path: str) -> None:
    assert (REPO_ROOT / path).exists(), f"Referenced repository path is missing: {path}"


@pytest.mark.parametrize("agent_id", PROJECT_AGENTS)
def test_project_agent_is_valid(agent_id: str) -> None:
    path = AGENTS_DIR / f"{agent_id}.md"
    assert path.is_file(), f"Missing repository-local agent: {path}"
    frontmatter, body = _split_frontmatter(path)
    assert frontmatter.get("description"), f"{path} must declare a description"
    assert frontmatter.get("mode") in {"primary", "subagent", "all"}, f"{path} has an invalid mode"
    model = frontmatter.get("model")
    assert isinstance(model, str) and re.fullmatch(r"[a-z0-9-]+/[A-Za-z0-9._:-]+", model), (
        f"{path} must use a provider/model identifier"
    )
    assert model in KNOWN_MODELS, f"{path} uses an unverified model identifier: {model}"
    assert body.strip(), f"{path} must contain a system prompt"
    assert "AGENTS.md" in body, f"{path} must instruct the agent to read AGENTS.md"

    permissions = frontmatter.get("permissions")
    assert isinstance(permissions, list) and permissions, f"{path} must declare permissions"
    for rule in permissions:
        assert set(rule) == {"action", "resource", "effect"}, f"{path} permission rule has unexpected keys"
        assert rule["effect"] in {"allow", "ask", "deny"}, f"{path} has an invalid permission effect"
        assert rule["action"], f"{path} has an empty permission action"
        assert rule["resource"], f"{path} has an empty permission resource"

    assert _rules_with(frontmatter, "skill", "allow"), f"{path} must allow the skill tool"


def test_permission_wildcard_matches_opencode_semantics() -> None:
    assert _opencode_wildcard("git status --short", "git status*")
    assert _opencode_wildcard("git status", "git status*")
    assert not _opencode_wildcard("bash scripts/deploy_ai_node.sh", "scripts/deploy_ai_node.sh*")
    assert _opencode_wildcard("line1\nline2", "*\n*")
    assert _opencode_wildcard("[x]", "[x]")
    assert not _opencode_wildcard("y", "[x]")
    assert _opencode_wildcard("a?b", "a?b")


@pytest.mark.parametrize("agent_id", PROJECT_AGENTS)
def test_shell_is_default_deny(agent_id: str) -> None:
    frontmatter = _frontmatter(agent_id)
    shell_rules = [rule for rule in frontmatter["permissions"] if rule["action"] == "shell"]
    assert shell_rules, f"{agent_id} must declare shell permissions"
    assert shell_rules[0] == {"action": "shell", "resource": "*", "effect": "deny"}, (
        f"{agent_id} must start with shell * deny"
    )
    assert not [rule for rule in shell_rules if rule["resource"] == "*" and rule["effect"] == "allow"], (
        f"{agent_id} must not declare a broad shell allow"
    )


@pytest.mark.parametrize("agent_id", PROJECT_AGENTS)
def test_general_shell_and_file_readers_are_denied(agent_id: str) -> None:
    frontmatter = _frontmatter(agent_id)
    for command in (
        "bash -c 'echo hi'",
        "sh -c 'echo hi'",
        "sudo true",
        "ssh localhost true",
        "docker compose up -d",
        "docker-compose up -d",
        "python3 -c 'print(1)'",
        "cat .env",
        "sed -n '1p' .env",
        "find . -name '*.db'",
        "rg secret",
        "head .env",
        "tail .env",
        "ls -la",
        "rm -rf data",
        "rm -fr data",
        "rm -r data",
        "cp /tmp/x data/x",
        "mv data/x /tmp/x",
        "chmod 777 data/x",
        "env FOO=1 bash",
    ):
        assert_denied(frontmatter, command)


@pytest.mark.parametrize("agent_id", ("slr-developer", "slr-release-engineer"))
def test_deployment_wrappers_are_denied(agent_id: str) -> None:
    frontmatter = _frontmatter(agent_id)
    for command in (
        "bash scripts/deploy_ai_node.sh",
        "sh scripts/deploy_ai_node.sh",
        "./scripts/deploy_ai_node.sh",
        "sudo docker compose up -d --build",
        "sudo docker-compose up -d",
        "docker compose up -d",
        "docker-compose up -d",
        "ssh cloud@ai-node 'cd /srv/slr-platform && sudo docker compose up -d'",
        "env BRANCH=main scripts/deploy_ai_node.sh",
    ):
        assert_denied(frontmatter, command)


def test_deployment_exact_script_permissions() -> None:
    developer = _frontmatter("slr-developer")
    release = _frontmatter("slr-release-engineer")
    assert_denied(developer, "scripts/deploy_ai_node.sh")
    assert_ask(release, "scripts/deploy_ai_node.sh")


def test_merged_opencode_permissions_enforce_hard_boundaries() -> None:
    developer = {"permissions": merged_agent_permissions("slr-developer")}
    release = {"permissions": merged_agent_permissions("slr-release-engineer")}

    for command in (
        "bash scripts/deploy_ai_node.sh",
        "sh scripts/deploy_ai_node.sh",
        "./scripts/deploy_ai_node.sh",
        "sudo docker compose up -d",
        "ssh cloud@ai-node deploy",
        "python3 -c \"open('data/slr-platform.db')\"",
        "sqlite3 -readonly data/slr-platform.db",
        "git reset --hard",
        "git restore .",
        "git worktree remove /tmp/wt",
        "git branch -D old",
        "git tag v1",
        "gh release create v1",
        "git diff --no-index /dev/null .env",
        "git diff --no-index /dev/null /home/cloud/.ssh/id_rsa",
        "git diff --output=data/slr-platform.db",
        "git diff --output=AGENTS.md",
        "git diff --output=.opencode/agents/slr-developer.md",
        "git log -p -- .env",
        "git show HEAD:.env",
    ):
        assert_denied(developer, command)

    assert_allowed(developer, "python3 scripts/agent/safe_git_inspect.py status --short")
    assert_allowed(developer, "python3 scripts/agent/safe_git_inspect.py diff --stat")
    assert_allowed(developer, "python3 scripts/agent/safe_git_inspect.py log --oneline -n 20")
    assert_allowed(developer, "python3 scripts/agent/safe_git_inspect.py show --stat HEAD")

    assert_denied(release, "bash scripts/deploy_ai_node.sh")
    assert_ask(release, "scripts/deploy_ai_node.sh")
    assert_ask(release, "git merge development")
    assert_ask(release, "gh api repos/x/y/releases")
    assert_denied(release, "git diff --no-index /dev/null .env")
    assert_denied(release, "git diff --output=AGENTS.md")
    assert_denied(release, "uv run --frozen --no-sync ruff check --fix app")
    assert_denied(release, "uv run --frozen --no-sync ruff format app/services/example.py")
    assert_allowed(release, "python3 scripts/agent/safe_git_inspect.py diff --stat")
    assert_allowed(release, "uv run --frozen --no-sync ruff check app tests scripts")


@pytest.mark.parametrize("agent_id", PROJECT_AGENTS)
def test_merged_permissions_do_not_allow_content_git_or_sqlite(agent_id: str) -> None:
    rules = merged_agent_permissions(agent_id)
    forbidden = [
        rule
        for rule in rules
        if rule.get("action") == "shell"
        and rule.get("effect") == "allow"
        and str(rule.get("resource", "")).startswith(("git diff", "git log", "git show", "sqlite3"))
    ]
    assert not forbidden, f"{agent_id} merged permissions still allow: {forbidden}"


def test_safe_git_inspection_wrapper_is_executable() -> None:
    wrapper = REPO_ROOT / "scripts" / "agent" / "safe_git_inspect.py"
    assert wrapper.is_file()
    assert os.access(wrapper, os.X_OK), "safe_git_inspect.py must be executable"


@pytest.mark.parametrize("agent_id", PROJECT_AGENTS)
def test_direct_git_read_and_write_bypasses_are_denied(agent_id: str) -> None:
    frontmatter = _frontmatter(agent_id)
    for command in (
        "git diff",
        "git diff HEAD~1",
        "git diff --no-index /dev/null .env",
        "git diff --no-index /dev/null secrets/token.txt",
        "git diff --no-index /dev/null /home/cloud/.ssh/id_rsa",
        "git diff --output=data/slr-platform.db",
        "git diff --output=data/x.db",
        "git diff --output=AGENTS.md",
        "git diff --output=.opencode/agents/slr-developer.md",
        "git diff --output=scripts/agent/safe_pytest.sh",
        "git log -p -- .env",
        "git log -p",
        "git show HEAD:.env",
        "git show HEAD",
    ):
        assert_denied(frontmatter, command)


@pytest.mark.parametrize("agent_id", PROJECT_AGENTS)
def test_safe_git_inspection_wrapper_is_allowed(agent_id: str) -> None:
    frontmatter = _frontmatter(agent_id)
    for command in (
        f"{SAFE_GIT_WRAPPER} status --short",
        f"{SAFE_GIT_WRAPPER} diff --stat",
        f"{SAFE_GIT_WRAPPER} diff HEAD~1 -- app/services/example.py",
        f"{SAFE_GIT_WRAPPER} log --oneline -n 20",
        f"{SAFE_GIT_WRAPPER} show --stat HEAD",
        f"{SAFE_GIT_WRAPPER} branch-current",
        f"{SAFE_GIT_WRAPPER} worktree-list",
    ):
        assert_allowed(frontmatter, command)


@pytest.mark.parametrize("agent_id", ("slr-qa", "slr-release-engineer"))
def test_read_only_roles_cannot_mutate_with_ruff(agent_id: str) -> None:
    frontmatter = _frontmatter(agent_id)
    for command in (
        "uv run --frozen --no-sync ruff check --fix app",
        "uv run --frozen --no-sync ruff check --unsafe-fixes app",
        "uv run --frozen --no-sync ruff format app/services/example.py",
        "uv run --frozen --no-sync ruff check --fix",
    ):
        assert_denied(frontmatter, command)
    assert_allowed(frontmatter, "uv run --frozen --no-sync ruff check app tests scripts")


def test_developer_may_intentionally_fix_with_ruff() -> None:
    frontmatter = _frontmatter("slr-developer")
    assert_allowed(frontmatter, "uv run --frozen --no-sync ruff check --fix app")
    assert_allowed(frontmatter, "uv run --frozen --no-sync ruff format app/services/example.py")


@pytest.mark.parametrize("agent_id", PROJECT_AGENTS)
def test_sqlite_shell_escape_is_denied(agent_id: str) -> None:
    frontmatter = _frontmatter(agent_id)
    for command in (
        "sqlite3",
        "sqlite3 data/slr-platform.db",
        "sqlite3 -readonly data/slr-platform.db",
        "sqlite3 -readonly data/slr-platform.db '.shell id'",
        "sqlite3 -readonly data/slr-platform.db '.output /tmp/x' 'select 1'",
    ):
        assert_denied(frontmatter, command)


def test_normal_developer_and_qa_workflows_remain_available() -> None:
    developer = _frontmatter("slr-developer")
    qa = _frontmatter("slr-qa")

    for command in (
        f"{SAFE_GIT_WRAPPER} status --short",
        f"{SAFE_GIT_WRAPPER} diff --stat",
        f"{SAFE_GIT_WRAPPER} diff HEAD~1 -- app/services/example.py",
        f"{SAFE_GIT_WRAPPER} log --oneline",
        f"{SAFE_GIT_WRAPPER} show --stat HEAD",
        "bash scripts/agent/safe_pytest.sh",
        "uv run --frozen --no-sync ruff check --fix app",
        "uv run --frozen --no-sync mypy app",
        "npm --prefix frontend run type-check",
        "openspec validate --all --strict",
    ):
        assert_allowed(developer, command)

    for command in (
        f"{SAFE_GIT_WRAPPER} status --short",
        f"{SAFE_GIT_WRAPPER} diff --stat",
        f"{SAFE_GIT_WRAPPER} log --oneline",
        f"{SAFE_GIT_WRAPPER} show --stat HEAD",
        "bash scripts/agent/safe_pytest.sh",
        "uv run --frozen --no-sync ruff check app tests scripts",
        "uv run --frozen --no-sync mypy app",
        "npm --prefix frontend run type-check",
        "npm --prefix frontend test",
        "npm --prefix frontend run build",
        "openspec validate --all --strict",
    ):
        assert_allowed(qa, command)


def test_developer_cannot_mutate_research_database() -> None:
    frontmatter = _frontmatter("slr-developer")
    for command in (
        'python3 -c "import sqlite3; sqlite3.connect(\'data/slr-platform.db\')"',
        'python3 -c "import sqlite3; sqlite3.connect(\'data/slr-platform.db\').execute(\'DELETE FROM x\')"',
        "sqlite3 data/slr-platform.db 'DELETE FROM x'",
        "rm data/slr-platform.db",
        "rm -f data/slr-platform.db",
        "cp /tmp/other.db data/slr-platform.db",
        "mv data/slr-platform.db /tmp/other.db",
        "truncate -s 0 data/slr-platform.db",
        "cat data/slr-platform.db",
        "git diff --output=data/slr-platform.db",
        "git diff --no-index /dev/null projects/demo/raw/source.pdf",
    ):
        assert_denied(frontmatter, command)


@pytest.mark.parametrize("agent_id", ("slr-developer", "slr-release-engineer"))
def test_destructive_git_is_denied(agent_id: str) -> None:
    frontmatter = _frontmatter(agent_id)
    for command in (
        "git reset --hard",
        "git clean -fd",
        "git stash",
        "git restore .",
        "git restore --source HEAD .",
        "git checkout -- .",
        "git worktree remove /home/cloud/dev/wt-other",
        "git branch -D feature/old",
        "git -C . reset --hard",
        "git -C . clean -fd",
        "git -C . stash",
        "rm -rf data",
        "rm -fr data",
        "rm -r data",
        "git push --force",
        "git push -f",
    ):
        assert_denied(frontmatter, command)


def test_developer_cannot_publish_release_or_merge_to_main() -> None:
    frontmatter = _frontmatter("slr-developer")
    for command in (
        "git tag v0.7.4",
        "git merge development",
        "git checkout main",
        "git switch main",
        "gh release create v0.7.4",
        "gh api repos/example/example/releases",
        "gh pr create",
    ):
        assert_denied(frontmatter, command)
    assert_ask(frontmatter, "git commit -m 'fix: test'")
    assert_ask(frontmatter, "git push origin feature/example")


def test_release_actions_require_approval() -> None:
    frontmatter = _frontmatter("slr-release-engineer")
    for command in (
        "git merge development",
        "git checkout main",
        "git switch main",
        "git push origin main",
        "git tag v0.7.4",
        "gh release create v0.7.4",
        "gh api repos/example/example/releases",
        "gh pr create",
        "scripts/deploy_ai_node.sh",
    ):
        assert_ask(frontmatter, command)


@pytest.mark.parametrize("agent_id", ("slr-architect", "slr-qa", "slr-research-reviewer"))
def test_read_only_agents_cannot_edit(agent_id: str) -> None:
    frontmatter = _frontmatter(agent_id)
    edit_rules = [rule for rule in frontmatter["permissions"] if rule["action"] == "edit"]
    assert edit_rules, f"{agent_id} must declare explicit edit permissions"
    assert edit_rules[0]["resource"] == "*" and edit_rules[0]["effect"] == "deny", (
        f"{agent_id} must start by denying all edits"
    )
    assert not [rule for rule in edit_rules if rule["effect"] == "allow"], (
        f"{agent_id} is read-only and must not allow edits"
    )


@pytest.mark.parametrize("agent_id", PROJECT_AGENTS)
def test_agents_do_not_override_secret_read_protection(agent_id: str) -> None:
    frontmatter = _frontmatter(agent_id)
    assert not [
        rule
        for rule in _rules_with(frontmatter, "read", "allow")
        if rule["resource"] == "*"
    ], f"{agent_id} must not declare a broad read allow"

    assert effective_effect(frontmatter, "read", ".env") == "deny", agent_id
    assert effective_effect(frontmatter, "read", "config/secrets/key") == "deny", agent_id
    assert effective_effect(frontmatter, "read", ".env.example") == "allow", agent_id


@pytest.mark.parametrize("agent_id", ("slr-architect", "slr-research-reviewer"))
def test_read_only_agents_have_no_shell_file_readers(agent_id: str) -> None:
    frontmatter = _frontmatter(agent_id)
    for command in (
        "cat .env",
        "sed -n '1p' .env",
        "find .",
        "rg secret",
        "head .env",
        "tail .env",
        "git diff --no-index /dev/null .env",
        "git diff --no-index /dev/null /home/cloud/.ssh/id_rsa",
        "git log -p -- .env",
        "git show HEAD:.env",
    ):
        assert_denied(frontmatter, command)


def test_developer_governance_edits_require_approval() -> None:
    frontmatter = _frontmatter("slr-developer")
    for path in (
        "AGENTS.md",
        ".opencode/agents/slr-developer.md",
        "docs/agents/QUALITY_GATES.md",
        "tests/unit/test_agent_foundation_configuration.py",
        "pyproject.toml",
        "scripts/ci/check_runner_policy.sh",
        "scripts/agent/safe_pytest.sh",
        "migrations/0001_example.sql",
    ):
        assert_edit_effect(frontmatter, path, "ask")

    for path in ("data/slr-platform.db", "projects/demo/raw/x", ".env", "config/secrets/key"):
        assert_edit_effect(frontmatter, path, "deny")
    assert_edit_effect(frontmatter, "scripts/deploy_ai_node.sh", "deny")
    assert_edit_effect(frontmatter, "app/services/example.py", "allow")


def test_release_edit_scope_is_narrow() -> None:
    frontmatter = _frontmatter("slr-release-engineer")
    assert_edit_effect(frontmatter, "VERSION", "allow")
    assert_edit_effect(frontmatter, "CHANGELOG.md", "allow")
    assert_edit_effect(frontmatter, "docs/releases/v0.7.4.md", "allow")
    assert_edit_effect(frontmatter, "pyproject.toml", "ask")
    assert_edit_effect(frontmatter, "frontend/package.json", "ask")
    assert_edit_effect(frontmatter, "openspec/specs/x/spec.md", "ask")
    assert_edit_effect(frontmatter, "docs/reviews/audit.md", "deny")
    assert_edit_effect(frontmatter, "app/services/example.py", "deny")


@pytest.mark.parametrize("agent_id", ("slr-developer", "slr-qa", "slr-research-reviewer", "slr-release-engineer"))
def test_safe_pytest_wrapper_is_allowed(agent_id: str) -> None:
    frontmatter = _frontmatter(agent_id)
    assert_allowed(frontmatter, "bash scripts/agent/safe_pytest.sh")
    assert_allowed(frontmatter, "bash scripts/agent/safe_pytest.sh tests/unit/test_agent_foundation_configuration.py")


def test_qa_frontend_commands_match_the_documented_workflow() -> None:
    frontmatter = _frontmatter("slr-qa")
    for command in (
        "npm --prefix frontend run type-check",
        "npm --prefix frontend test",
        "npm --prefix frontend run build",
    ):
        assert_allowed(frontmatter, command)
    assert_denied(frontmatter, "cd frontend && npm test")
    assert_denied(frontmatter, "npm test")


@pytest.mark.parametrize("agent_id", PROJECT_AGENTS)
def test_compound_commands_are_denied(agent_id: str) -> None:
    frontmatter = _frontmatter(agent_id)
    for command in (
        "python3 scripts/agent/safe_git_inspect.py status; rm -rf data",
        "python3 scripts/agent/safe_git_inspect.py status && rm -rf data",
        "python3 scripts/agent/safe_git_inspect.py status | tee /tmp/x",
        "python3 scripts/agent/safe_git_inspect.py status $(rm -rf data)",
        "python3 scripts/agent/safe_git_inspect.py status `rm -rf data`",
        "python3 scripts/agent/safe_git_inspect.py status > /tmp/x",
        "python3 scripts/agent/safe_git_inspect.py status\nrm -rf data",
    ):
        assert_denied(frontmatter, command)


@pytest.mark.parametrize("agent_id", PROJECT_AGENTS)
def test_agents_cannot_delegate_or_deploy_autonomously(agent_id: str) -> None:
    frontmatter = _frontmatter(agent_id)
    _, body = _split_frontmatter(AGENTS_DIR / f"{agent_id}.md")
    assert _rules_with(frontmatter, "subagent", "deny"), f"{agent_id} must not launch nested agents"
    assert not [
        rule
        for rule in frontmatter["permissions"]
        if rule["action"] == "shell"
        and rule["effect"] == "allow"
        and "deploy_ai_node" in str(rule["resource"])
    ], f"{agent_id} must not allow a production deploy command"
    lowered = body.lower()
    assert "human approval" in lowered or "human authorization" in lowered, (
        f"{agent_id} must state the human approval boundary"
    )


def test_release_engineer_declares_approval_for_release_actions() -> None:
    frontmatter = _frontmatter("slr-release-engineer")
    for resource in (
        "git push*",
        "git merge*",
        "git tag*",
        "gh release*",
        "gh api*",
        "scripts/deploy_ai_node.sh",
    ):
        matching = [
            rule
            for rule in frontmatter["permissions"]
            if rule["action"] == "shell" and rule["resource"] == resource
        ]
        assert matching, f"release engineer must declare a rule for {resource}"
        assert matching[-1]["effect"] in {"ask", "deny"}, f"{resource} must require approval or be denied"


def test_configured_models_are_statically_allowlisted() -> None:
    assert "opencode/mimo-v2.6-flash-free" in KNOWN_MODELS
    for agent_id in PROJECT_AGENTS:
        model = _frontmatter(agent_id).get("model")
        assert model in KNOWN_MODELS, f"{agent_id} model is not statically allow-listed: {model}"
        assert re.fullmatch(r"[a-z0-9-]+/[A-Za-z0-9._:-]+", str(model))


def test_configured_free_models_are_in_standalone_catalog() -> None:
    """Verify free models against the pinned CLI's isolated catalog.

    Paid provider catalogs need provider credentials, so they are covered by the
    static allow-list test above. The standalone catalog is deterministic and
    available on the self-hosted runner without model inference or paid credits.
    """

    catalog = set(_opencode("models").stdout.splitlines())
    assert "opencode/mimo-v2.6-flash-free" in catalog
    for agent_id in PROJECT_AGENTS:
        model = str(_frontmatter(agent_id).get("model"))
        if model.startswith("opencode/"):
            assert model in catalog, f"{agent_id} free model is missing from the catalog: {model}"
        else:
            assert model in KNOWN_MODELS, f"{agent_id} paid model is not statically allow-listed: {model}"


def test_openspec_root_is_initialized_and_configured() -> None:
    assert (OPENSPEC_DIR / "config.yaml").is_file(), "OpenSpec config.yaml is required"
    config = yaml.safe_load((OPENSPEC_DIR / "config.yaml").read_text(encoding="utf-8"))
    assert config.get("schema") == "spec-driven"
    assert config.get("context"), "OpenSpec config must carry project context"
    assert (OPENSPEC_DIR / "specs").is_dir()
    assert (OPENSPEC_DIR / "changes" / "archive").is_dir()


def test_openspec_has_an_archived_change_and_main_spec() -> None:
    archives = sorted((OPENSPEC_DIR / "changes" / "archive").glob("*/proposal.md"))
    assert archives, "OpenSpec archive must contain at least one completed change"
    main_spec = OPENSPEC_DIR / "specs" / "agent-engineering-foundation" / "spec.md"
    assert main_spec.is_file(), "OpenSpec main spec for agent-engineering-foundation is required"
    assert "## Requirements" in main_spec.read_text(encoding="utf-8")
