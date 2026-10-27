#!/usr/bin/env bash
# Run pytest with a disposable SQLite database for agent sessions.
#
# OpenCode permissions are not a filesystem sandbox. This wrapper reduces the
# risk of an agent test run touching the repository's real research database by
# forcing SLR_DATABASE_PATH and TMPDIR into a fresh temporary directory.
set -Eeuo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

TEST_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/slr-agent-tests.XXXXXX")"
cleanup() {
  rm -rf "$TEST_ROOT"
}
trap cleanup EXIT

export TMPDIR="$TEST_ROOT"
export SLR_DATABASE_PATH="$TEST_ROOT/slr-agent.db"
export PYTHONDONTWRITEBYTECODE=1

set +e
uv run --frozen --no-sync pytest -q -p no:cacheprovider "$@"
status=$?
set -e
exit "$status"
