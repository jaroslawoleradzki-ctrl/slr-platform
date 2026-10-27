"""Contract tests for the repository-local agent engineering foundation.

These tests are infrastructure tests, not application-behavior tests. They keep
the OpenCode agents, skills, AGENTS.md, and OpenSpec root internally consistent
so a broken configuration cannot silently ship.
"""

from __future__ import annotations

import re
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
    "opencode-go/muse-spark-1.3-contributor",
    "opencode-go/mimo-v2.6-flash",
}

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
)


def _split_frontmatter(path: Path) -> tuple[dict[str, Any], str]:
    text = path.read_text(encoding="utf-8")
    parts = text.split("---", 2)
    assert len(parts) == 3, f"{path} must start with a complete YAML frontmatter block"
    assert parts[0].strip() == "", f"{path} must start with '---' on its own line"
    data = yaml.safe_load(parts[1])
    assert isinstance(data, dict), f"{path} frontmatter must be a YAML mapping"
    return data, parts[2]


def _rules_with(frontmatter: dict[str, Any], action: str, effect: str) -> list[dict[str, Any]]:
    return [
        rule
        for rule in frontmatter.get("permissions", [])
        if rule.get("action") == action and rule.get("effect") == effect
    ]


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


@pytest.mark.parametrize("agent_id", READ_ONLY_AGENTS)
def test_read_only_agents_cannot_edit(agent_id: str) -> None:
    frontmatter, _ = _split_frontmatter(AGENTS_DIR / f"{agent_id}.md")
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
    frontmatter, _ = _split_frontmatter(AGENTS_DIR / f"{agent_id}.md")
    broad_read_allow = [
        rule
        for rule in frontmatter["permissions"]
        if rule["action"] == "read" and rule["resource"] == "*" and rule["effect"] == "allow"
    ]
    assert not broad_read_allow, (
        f"{agent_id} must not override the global ask-before-read rule for .env files"
    )


@pytest.mark.parametrize("agent_id", PROJECT_AGENTS)
def test_agents_cannot_delegate_or_deploy_autonomously(agent_id: str) -> None:
    frontmatter, body = _split_frontmatter(AGENTS_DIR / f"{agent_id}.md")
    assert _rules_with(frontmatter, "subagent", "deny"), f"{agent_id} must not launch nested agents"

    for rule in frontmatter["permissions"]:
        if rule["action"] != "shell" or rule["effect"] != "allow":
            continue
        resource = rule["resource"]
        assert "deploy_ai_node" not in resource, f"{agent_id} must not allow a production deploy command"
        assert "docker compose up" not in resource, f"{agent_id} must not allow a compose deploy command"

    lowered = body.lower()
    assert "human approval" in lowered or "human authorization" in lowered, (
        f"{agent_id} must state the human approval boundary"
    )


def test_release_engineer_requires_approval_for_release_actions() -> None:
    frontmatter, _ = _split_frontmatter(AGENTS_DIR / "slr-release-engineer.md")
    for resource in ("git push*", "git tag*", "gh release*", "scripts/deploy_ai_node.sh*"):
        matching = [
            rule
            for rule in frontmatter["permissions"]
            if rule["action"] == "shell" and rule["resource"] == resource
        ]
        assert matching, f"release engineer must declare a rule for {resource}"
        assert matching[-1]["effect"] in {"ask", "deny"}, f"{resource} must require approval or be denied"


def test_openspec_root_is_initialized_and_configured() -> None:
    assert (OPENSPEC_DIR / "config.yaml").is_file(), "OpenSpec config.yaml is required"
    config = yaml.safe_load((OPENSPEC_DIR / "config.yaml").read_text(encoding="utf-8"))
    assert config.get("schema") == "spec-driven"
    assert config.get("context"), "OpenSpec config must carry project context"
    assert (OPENSPEC_DIR / "specs").is_dir()
    assert (OPENSPEC_DIR / "changes" / "archive").is_dir()
