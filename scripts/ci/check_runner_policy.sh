#!/usr/bin/env bash
# Fail closed if any workflow can schedule a GitHub-hosted runner.
#
# SLR Platform CI is physically pinned to AI-node (192.168.100.29) through the
# dedicated self-hosted runner labelled: self-hosted, linux, slr-platform.
set -euo pipefail

workflow_dir="${1:-.github/workflows}"
failures=0

fail() {
  echo "::error::$*"
  failures=$((failures + 1))
}

if [ ! -d "$workflow_dir" ]; then
  echo "::error::workflow directory not found: $workflow_dir"
  exit 1
fi

# GitHub-hosted labels: ubuntu-*, windows-*, macos-*. This also catches them in
# matrices and in any documentation-like YAML values, so they cannot be
# reintroduced accidentally.
if matches=$(grep -RInE '\b(ubuntu|windows|macos)-(latest|[0-9]+(\.[0-9]+)?)\b' "$workflow_dir"); then
  while IFS= read -r match; do
    fail "GitHub-hosted runner label found: $match"
  done <<< "$matches"
fi

# Block-list form (`runs-on:\n  - self-hosted`) is not used in this repository;
# reject it rather than trying to parse YAML with grep.
if matches=$(grep -RInE '^[[:space:]]*runs-on:[[:space:]]*$' "$workflow_dir"); then
  while IFS= read -r match; do
    fail "Unsupported block-form runs-on (use an explicit label list): $match"
  done <<< "$matches"
fi

# Every inline runs-on must carry the full AI-node contract. Matrix/expression
# values are rejected because they cannot be verified statically.
if matches=$(grep -RInE '^[[:space:]]*runs-on:' "$workflow_dir"); then
  while IFS= read -r match; do
    if ! grep -qE '\[[^]]*self-hosted[^]]*linux[^]]*slr-platform[^]]*\]' <<< "$match"; then
      fail "runs-on is missing [self-hosted, linux, slr-platform]: $match"
    fi
    if grep -qE '\$\{\{' <<< "$match"; then
      fail "Dynamic runs-on is not allowed: $match"
    fi
  done <<< "$matches"
else
  fail "No runs-on entries found in $workflow_dir"
fi

if [ "$failures" -ne 0 ]; then
  echo "CI runner policy FAILED ($failures violation(s))."
  exit 1
fi

echo "CI runner policy PASSED: all jobs target [self-hosted, linux, slr-platform]."
