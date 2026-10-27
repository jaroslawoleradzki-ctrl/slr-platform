#!/usr/bin/env python3
"""Fail-closed, read-only Git inspection for OpenCode agents.

Direct ``git diff``, ``git log`` and ``git show`` are intentionally not
allowlisted for the SLR agents because their option surface can read arbitrary
files (``--no-index``), write arbitrary files (``--output``), invoke external
diff helpers (``--ext-diff``) or print file contents from history (``-p``).

Agents use this wrapper instead::

    python3 scripts/agent/safe_git_inspect.py status --short
    python3 scripts/agent/safe_git_inspect.py diff --stat
    python3 scripts/agent/safe_git_inspect.py diff HEAD~1 -- app/services/foo.py
    python3 scripts/agent/safe_git_inspect.py log --oneline -n 20
    python3 scripts/agent/safe_git_inspect.py show --stat HEAD
    python3 scripts/agent/safe_git_inspect.py branch-current
    python3 scripts/agent/safe_git_inspect.py worktree-list

Design rules:

* explicit operation allowlist (status, diff, log, show, branch-current,
  worktree-list);
* explicit option allowlists per operation, unknown options are rejected;
* ``--no-index``, ``--output``, ``--ext-diff``, ``--textconv``, ``--config``,
  ``-c``, ``--git-dir``, ``--work-tree`` and external helpers are rejected;
* paths must be repository-relative, must not contain traversal, glob or
  pathspec magic, must resolve inside the worktree (symlink escapes rejected)
  and must not touch protected research/governance paths;
* revisions must resolve to commits; ``rev:path`` blob syntax is rejected;
* ``log -p``/``--patch`` and patch-producing ``show`` forms are rejected;
* ``subprocess`` argument arrays only, never ``shell=True`` or ``eval``;
* Git environment and configuration that can execute helpers are neutralised.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path, PurePosixPath

USAGE = __doc__ or "safe_git_inspect"

GIT_BIN = shutil.which("git") or "/usr/bin/git"

PROTECTED_PARTS = frozenset({"data", "projects", "secrets", "backups", ".git"})
PROTECTED_SUFFIXES = frozenset({".db", ".sqlite", ".sqlite3", ".pem", ".key"})

DANGEROUS_FLAGS = frozenset(
    {
        "-c",
        "-O",
        "--config",
        "--git-dir",
        "--work-tree",
        "--exec-path",
        "--no-index",
        "--output",
        "--ext-diff",
        "--textconv",
        "--upload-pack",
        "--receive-pack",
    }
)

REV_CHARS = re.compile(r"^[A-Za-z0-9_@{}~^./-]+$")

# Defence in depth: even an unfiltered diff/log/show must not expose protected
# paths that happen to be tracked in the repository.
EXCLUDE_PATHSPECS = (
    ":(exclude).env",
    ":(exclude).env.*",
    ":(exclude)**/.env",
    ":(exclude)**/.env.*",
    ":(exclude)secrets/**",
    ":(exclude)**/secrets/**",
    ":(exclude)data/**",
    ":(exclude)**/data/**",
    ":(exclude)projects/**",
    ":(exclude)**/projects/**",
    ":(exclude)**/backups/**",
    ":(exclude)*.db",
    ":(exclude)**/*.db",
    ":(exclude)**/*.sqlite*",
    ":(exclude)**/*.pem",
    ":(exclude)**/*.key",
)


class Rejected(Exception):
    """A command or argument was rejected before Git was invoked."""


def _reject(message: str) -> None:
    raise Rejected(message)


def _is_protected(path: PurePosixPath) -> bool:
    name = path.name
    if name == ".env" or name.startswith(".env."):
        return True
    if path.suffix.lower() in PROTECTED_SUFFIXES:
        return True
    return any(part in PROTECTED_PARTS for part in path.parts)


def _git_env() -> dict[str, str]:
    """Return a Git environment that cannot load external helpers."""

    env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    env.update(
        {
            "GIT_PAGER": "cat",
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_OPTIONAL_LOCKS": "0",
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_SYSTEM": os.devnull,
            "GIT_ATTR_NOSYSTEM": "1",
        }
    )
    return env


def _git_command() -> list[str]:
    return [
        GIT_BIN,
        "--no-optional-locks",
        "--no-pager",
        "-c",
        "core.pager=cat",
        "-c",
        "core.fsmonitor=false",
        "-c",
        "diff.external=",
        "-c",
        "color.ui=never",
    ]


def _run_git(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [*_git_command(), *args],
        cwd=str(cwd),
        env=_git_env(),
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def _repo_root() -> Path:
    result = _run_git(["rev-parse", "--show-toplevel"], cwd=Path.cwd())
    if result.returncode != 0 or not result.stdout.strip():
        _reject("not inside a Git worktree")
    return Path(result.stdout.strip()).resolve()


def _validate_path(raw: str, root: Path) -> str:
    if not raw:
        _reject("empty path")
    if any(character in raw for character in "\x00\r\n"):
        _reject("path contains a control character")
    if raw.startswith("-"):
        _reject(f"path looks like an option: {raw!r}")
    if raw.startswith("~"):
        _reject(f"home-relative paths are not supported: {raw!r}")
    if "\\" in raw:
        _reject(f"backslash paths are not supported: {raw!r}")
    if ":" in raw:
        _reject(f"pathspec magic and rev:path syntax are rejected: {raw!r}")
    if any(character in raw for character in "*?["):
        _reject(f"glob pathspecs are rejected: {raw!r}")

    candidate = PurePosixPath(raw)
    if candidate.is_absolute():
        _reject(f"absolute paths are rejected: {raw!r}")
    if ".." in candidate.parts:
        _reject(f"path traversal is rejected: {raw!r}")
    if _is_protected(candidate):
        _reject(f"protected path is not inspectable: {raw!r}")

    resolved = (root / Path(*candidate.parts)).resolve()
    try:
        relative = resolved.relative_to(root)
    except ValueError:
        _reject(f"path escapes the worktree: {raw!r}")

    resolved_path = PurePosixPath(relative.as_posix())
    if _is_protected(resolved_path):
        _reject(f"path resolves to a protected path: {raw!r}")
    return resolved_path.as_posix()


def _validate_revision(raw: str, root: Path) -> str:
    if not raw:
        _reject("empty revision")
    if raw.startswith("-"):
        _reject(f"revision looks like an option: {raw!r}")
    if ":" in raw or "\\" in raw:
        _reject(f"rev:path and backslash revisions are rejected: {raw!r}")
    if any(character.isspace() or ord(character) < 32 for character in raw):
        _reject(f"revision contains whitespace or control characters: {raw!r}")

    sides = re.split(r"\.\.\.|\.\.", raw)
    if len(sides) > 2 or any(not side for side in sides):
        _reject(f"invalid revision range: {raw!r}")
    for side in sides:
        if not REV_CHARS.fullmatch(side):
            _reject(f"unsupported revision syntax: {raw!r}")
        check = _run_git(["rev-parse", "--verify", "--quiet", f"{side}^{{commit}}"], cwd=root)
        if check.returncode != 0:
            _reject(f"revision does not resolve to a commit: {side!r}")
    return raw


def _validate_flag(flag: str, allowed: frozenset[str], patterns: tuple[re.Pattern[str], ...]) -> None:
    name = flag.split("=", 1)[0]
    if name in DANGEROUS_FLAGS:
        _reject(f"dangerous option is rejected: {flag!r}")
    if flag in allowed:
        return
    if any(pattern.fullmatch(flag) for pattern in patterns):
        return
    _reject(f"unsupported option: {flag!r}")


DIFF_FLAGS = frozenset(
    {
        "--cached",
        "--staged",
        "--stat",
        "--shortstat",
        "--numstat",
        "--name-only",
        "--name-status",
        "--summary",
        "--check",
        "--patch",
        "-p",
        "--no-patch",
        "--no-color",
        "--color=never",
        "--word-diff",
        "--word-diff=plain",
        "--word-diff=porcelain",
        "--word-diff=none",
        "--ignore-space-at-eol",
        "--ignore-space-change",
        "-b",
        "--ignore-all-space",
        "-w",
        "--ignore-blank-lines",
        "--binary",
        "--full-index",
        "--no-abbrev",
        "--exit-code",
        "--quiet",
        "--no-ext-diff",
        "--no-textconv",
        "--no-renames",
        "--no-prefix",
        "--default-prefix",
    }
)

DIFF_PATTERNS = (
    re.compile(r"-U\d+"),
    re.compile(r"--unified=\d+"),
    re.compile(r"--diff-filter=[ACDMRTUXB*]+"),
    re.compile(r"--find-renames(?:=\d+%?)?"),
    re.compile(r"--find-copies(?:=\d+%?)?"),
    re.compile(r"-M\d*%?"),
    re.compile(r"-C\d*%?"),
    re.compile(r"--abbrev(?:=\d+)?"),
)

LOG_FLAGS = frozenset(
    {
        "--oneline",
        "--stat",
        "--shortstat",
        "--numstat",
        "--name-only",
        "--name-status",
        "--summary",
        "--raw",
        "--graph",
        "--decorate",
        "--no-decorate",
        "--all",
        "--branches",
        "--tags",
        "--first-parent",
        "--no-merges",
        "--merges",
        "--reverse",
        "--topo-order",
        "--date-order",
        "--author-date-order",
        "--abbrev-commit",
        "--no-abbrev-commit",
        "--relative-date",
        "--no-patch",
        "--no-color",
        "--color=never",
        "--no-ext-diff",
        "--no-textconv",
        "--no-renames",
        "--full-history",
        "--simplify-by-decoration",
        "--source",
    }
)

LOG_PATTERNS = (
    re.compile(r"-n\d+"),
    re.compile(r"--max-count=\d+"),
    re.compile(r"--since=.+"),
    re.compile(r"--until=.+"),
    re.compile(r"--author=.+"),
    re.compile(r"--grep=.+"),
    re.compile(r"--format=.+"),
    re.compile(r"--pretty=.+"),
    re.compile(r"--date=.+"),
    re.compile(r"--diff-filter=[ACDMRTUXB*]+"),
)

SHOW_FLAGS = frozenset(
    {
        "--stat",
        "--shortstat",
        "--numstat",
        "--name-only",
        "--name-status",
        "--summary",
        "--raw",
        "--no-patch",
        "-s",
        "--oneline",
        "--abbrev-commit",
        "--no-color",
        "--color=never",
        "--no-ext-diff",
        "--no-textconv",
    }
)

SHOW_PATTERNS = (
    re.compile(r"--format=.+"),
    re.compile(r"--pretty=.+"),
    re.compile(r"--date=.+"),
)

SHOW_METADATA_FLAGS = frozenset(
    {
        "--stat",
        "--shortstat",
        "--numstat",
        "--name-only",
        "--name-status",
        "--summary",
        "--raw",
        "--no-patch",
        "-s",
    }
)

STATUS_FLAGS = frozenset(
    {
        "--short",
        "-s",
        "--porcelain",
        "--porcelain=v1",
        "--porcelain=v2",
        "--branch",
        "-b",
        "--long",
        "--verbose",
        "-v",
        "--untracked-files=no",
        "--untracked-files=normal",
        "--untracked-files=all",
        "-uno",
        "-unormal",
        "-uall",
        "--ignored=no",
        "--ignored=traditional",
        "--ignored=matching",
        "--no-renames",
        "--renames",
        "--show-stash",
        "--ahead-behind",
        "--no-ahead-behind",
        "--no-column",
        "--no-color",
        "--color=never",
        "-z",
        "--null",
    }
)

STATUS_PATTERNS = (
    re.compile(r"--find-renames(?:=\d+)?"),
    re.compile(r"--column(?:=\w+)?"),
)


def _join_numeric_option(argv: list[str], flag: str) -> list[str]:
    """Join ``-n 20`` / ``-U 3`` style arguments into ``-n20`` / ``-U3``."""

    joined: list[str] = []
    index = 0
    while index < len(argv):
        if argv[index] == flag and index + 1 < len(argv) and argv[index + 1].isdigit():
            joined.append(f"{flag}{argv[index + 1]}")
            index += 2
            continue
        joined.append(argv[index])
        index += 1
    return joined


def _parse_diff(argv: list[str], root: Path) -> list[str]:
    argv = _join_numeric_option(argv, "-U")
    flags: list[str] = []
    revisions: list[str] = []
    paths: list[str] = []
    after_separator = False
    for argument in argv:
        if argument == "--":
            after_separator = True
            continue
        if after_separator:
            paths.append(_validate_path(argument, root))
        elif argument.startswith("-"):
            _validate_flag(argument, DIFF_FLAGS, DIFF_PATTERNS)
            flags.append(argument)
        else:
            revisions.append(_validate_revision(argument, root))
    if len(revisions) > 2:
        _reject("diff accepts at most two revisions")
    if not paths:
        paths = ["."]
    return ["diff", *flags, "--no-ext-diff", "--no-textconv", *revisions, "--", *paths, *EXCLUDE_PATHSPECS]


def _parse_log(argv: list[str], root: Path) -> list[str]:
    argv = _join_numeric_option(argv, "-n")
    flags: list[str] = []
    revisions: list[str] = []
    paths: list[str] = []
    after_separator = False
    for argument in argv:
        if argument == "--":
            after_separator = True
            continue
        if after_separator:
            paths.append(_validate_path(argument, root))
        elif argument.startswith("-"):
            if argument in {"-p", "--patch"} or argument.startswith("--patch="):
                _reject("log patch output is rejected; file contents are not available through history")
            _validate_flag(argument, LOG_FLAGS, LOG_PATTERNS)
            flags.append(argument)
        else:
            revisions.append(_validate_revision(argument, root))
    if len(revisions) > 2:
        _reject("log accepts at most two revisions")
    if not paths:
        paths = ["."]
    return ["log", *flags, "--no-ext-diff", "--no-textconv", *revisions, "--", *paths, *EXCLUDE_PATHSPECS]


def _parse_show(argv: list[str], root: Path) -> list[str]:
    flags: list[str] = []
    revisions: list[str] = []
    for argument in argv:
        if argument == "--":
            _reject("show does not accept path arguments")
        if argument.startswith("-"):
            if argument in {"-p", "--patch"} or argument.startswith("--patch="):
                _reject("show patch output is rejected; use diff for safe path-level review")
            _validate_flag(argument, SHOW_FLAGS, SHOW_PATTERNS)
            flags.append(argument)
        else:
            revisions.append(_validate_revision(argument, root))
    if len(revisions) != 1:
        _reject("show requires exactly one revision")
    if not any(flag in SHOW_METADATA_FLAGS for flag in flags):
        _reject("show requires a metadata-only option (--stat, --name-only, --no-patch, ...)")
    return ["show", *flags, "--no-ext-diff", "--no-textconv", *revisions, "--", ".", *EXCLUDE_PATHSPECS]


def _parse_status(argv: list[str]) -> list[str]:
    flags: list[str] = []
    for argument in argv:
        if not argument.startswith("-"):
            _reject("status does not accept path arguments")
        _validate_flag(argument, STATUS_FLAGS, STATUS_PATTERNS)
        flags.append(argument)
    return ["status", *flags]


def main(argv: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if not arguments or arguments[0] in {"-h", "--help", "help"}:
        print(USAGE)
        return 0

    operation = arguments.pop(0)
    root = _repo_root()

    if operation == "diff":
        git_args = _parse_diff(arguments, root)
    elif operation == "log":
        git_args = _parse_log(arguments, root)
    elif operation == "show":
        git_args = _parse_show(arguments, root)
    elif operation == "status":
        git_args = _parse_status(arguments)
    elif operation == "branch-current":
        if arguments:
            _reject("branch-current accepts no arguments")
        git_args = ["branch", "--show-current"]
    elif operation == "worktree-list":
        if arguments:
            _reject("worktree-list accepts no arguments")
        git_args = ["worktree", "list"]
    else:
        _reject(f"unsupported operation: {operation!r}")

    result = _run_git(git_args, cwd=root)
    if result.stdout:
        sys.stdout.write(result.stdout)
    if result.stderr:
        sys.stderr.write(result.stderr)
    return result.returncode


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Rejected as error:
        print(f"safe_git_inspect: REJECTED: {error}", file=sys.stderr)
        raise SystemExit(2) from None
