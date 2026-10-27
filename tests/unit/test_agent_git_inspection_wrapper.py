"""Unit tests for the fail-closed Git inspection wrapper.

These tests use disposable Git repositories under ``tmp_path`` and synthetic
files only. They never execute a destructive command against the SLR
repository, never read real secrets, and never touch research data.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
WRAPPER = REPO_ROOT / "scripts" / "agent" / "safe_git_inspect.py"


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q", ".")
    _git(root, "config", "user.email", "audit@example.invalid")
    _git(root, "config", "user.name", "Audit")
    (root / "app").mkdir()
    (root / "app" / "module.py").write_text("one\n", encoding="utf-8")
    (root / ".env").write_text("DUMMY=not-a-secret\n", encoding="utf-8")
    (root / "data").mkdir()
    (root / "data" / "x.db").write_text("dummy-db\n", encoding="utf-8")
    (root / "secrets").mkdir()
    (root / "secrets" / "token.txt").write_text("dummy-token\n", encoding="utf-8")
    _git(root, "add", "app/module.py")
    _git(root, "commit", "-qm", "one")
    (root / "app" / "module.py").write_text("two\n", encoding="utf-8")
    _git(root, "commit", "-qam", "two")
    return root


def _run(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(WRAPPER), *args],
        cwd=repo,
        check=False,
        capture_output=True,
        text=True,
    )


def _assert_rejected(result: subprocess.CompletedProcess[str], needle: str | None = None) -> None:
    assert result.returncode == 2, (result.returncode, result.stdout, result.stderr)
    assert "REJECTED" in result.stderr
    if needle is not None:
        assert needle in result.stderr


def test_safe_operations_are_allowed(repo: Path) -> None:
    for args in (
        ("status", "--short"),
        ("diff", "--stat"),
        ("diff", "--check"),
        ("diff", "-U", "2", "HEAD~1", "--", "app/module.py"),
        ("diff", "-M", "--stat", "HEAD~1"),
        ("log", "--oneline", "-n", "2"),
        ("log", "--oneline", "--", "app/module.py"),
        ("show", "--stat", "HEAD"),
        ("show", "--name-only", "HEAD"),
        ("show", "--no-patch", "HEAD"),
        ("branch-current",),
        ("worktree-list",),
    ):
        result = _run(repo, *args)
        assert result.returncode == 0, (args, result.returncode, result.stdout, result.stderr)


def test_no_index_read_bypass_is_rejected(repo: Path) -> None:
    for args in (
        ("diff", "--no-index", "/dev/null", ".env"),
        ("diff", "--no-index", "/dev/null", "secrets/token.txt"),
        ("diff", "--no-index", "/dev/null", "/home/cloud/.ssh/id_rsa"),
        ("diff", "--no-index", "/dev/null", "../outside"),
    ):
        _assert_rejected(_run(repo, *args), "--no-index")


def test_output_write_bypass_is_rejected(repo: Path) -> None:
    for args in (
        ("diff", "--output=out.txt"),
        ("diff", "--output", "out2.txt"),
        ("diff", "--output=data/created.db"),
        ("diff", "--output=AGENTS.md"),
        ("diff", "--output=.opencode/agents/slr-developer.md"),
        ("diff", "--output=scripts/agent/safe_pytest.sh"),
    ):
        _assert_rejected(_run(repo, *args), "--output")
    assert not (repo / "out.txt").exists()
    assert not (repo / "out2.txt").exists()
    assert not (repo / "data" / "created.db").exists()


def test_external_diff_and_config_are_rejected(repo: Path) -> None:
    for args in (
        ("diff", "--ext-diff"),
        ("diff", "--textconv"),
        ("diff", "--config=diff.external=/tmp/evil"),
        ("diff", "-c", "diff.external=/tmp/evil"),
        ("diff", "--git-dir=/tmp/evil"),
        ("diff", "--work-tree=/tmp/evil"),
        ("diff", "-O", "/tmp/order"),
        ("diff", "--output-indicator-new=X"),
        ("diff", "--submodule=log"),
    ):
        _assert_rejected(_run(repo, *args))


def test_protected_paths_and_traversal_are_rejected(repo: Path) -> None:
    for raw in (
        ".env",
        "secrets/token.txt",
        "data/x.db",
        "projects/demo/raw/source.pdf",
        "../outside",
        "/etc/passwd",
        "app/*",
        "app/?.py",
        "app/[ab].py",
        ":(glob)app/**",
    ):
        _assert_rejected(_run(repo, "diff", "--", raw))
    _assert_rejected(_run(repo, "log", "--oneline", "--", ".env"))
    _assert_rejected(_run(repo, "show", "--stat", "HEAD", "--", ".env"))


def test_symlink_escapes_are_rejected(repo: Path, tmp_path: Path) -> None:
    outside = tmp_path / "outside.txt"
    outside.write_text("outside\n", encoding="utf-8")
    (repo / "app" / "escape").symlink_to(outside)
    _assert_rejected(_run(repo, "diff", "--", "app/escape"), "escapes the worktree")

    (repo / "app" / "dblink").symlink_to(repo / "data" / "x.db")
    _assert_rejected(_run(repo, "diff", "--", "app/dblink"), "protected path")


def test_history_content_is_rejected(repo: Path) -> None:
    for args in (
        ("log", "-p"),
        ("log", "--patch"),
        ("log", "-p", "--", "app/module.py"),
        ("show", "HEAD"),
        ("show", "-p", "HEAD"),
        ("show", "HEAD:.env"),
        ("show", "--stat", "HEAD", "--", ".env"),
    ):
        _assert_rejected(_run(repo, *args))


def test_unfiltered_diff_excludes_tracked_protected_paths(repo: Path) -> None:
    _git(repo, "add", "-f", ".env", "data/x.db", "secrets/token.txt")
    _git(repo, "commit", "-qm", "track-protected")
    (repo / ".env").write_text("CHANGED=not-a-secret\n", encoding="utf-8")
    (repo / "data" / "x.db").write_text("changed-db\n", encoding="utf-8")
    (repo / "secrets" / "token.txt").write_text("changed-token\n", encoding="utf-8")
    (repo / "app" / "module.py").write_text("three\n", encoding="utf-8")

    stat = _run(repo, "diff", "--stat")
    assert stat.returncode == 0
    assert "app/module.py" in stat.stdout
    assert ".env" not in stat.stdout
    assert "data/x.db" not in stat.stdout
    assert "secrets/token.txt" not in stat.stdout

    patch = _run(repo, "diff")
    assert patch.returncode == 0
    assert "CHANGED=not-a-secret" not in patch.stdout
    assert "changed-db" not in patch.stdout
    assert "changed-token" not in patch.stdout


def test_unknown_operations_and_options_are_rejected(repo: Path) -> None:
    _assert_rejected(_run(repo, "push"))
    _assert_rejected(_run(repo, "diff", "--not-a-real-option"))
    _assert_rejected(_run(repo, "log", "--not-a-real-option"))
    _assert_rejected(_run(repo, "show", "--stat", "--not-a-real-option", "HEAD"))
    _assert_rejected(_run(repo, "status", "--not-a-real-option"))
    _assert_rejected(_run(repo, "status", "app/module.py"))
    _assert_rejected(_run(repo, "branch-current", "extra"))
    _assert_rejected(_run(repo, "worktree-list", "extra"))


def test_wrapper_can_run_from_a_subdirectory(repo: Path) -> None:
    result = subprocess.run(
        [sys.executable, str(WRAPPER), "status", "--short"],
        cwd=repo / "app",
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
