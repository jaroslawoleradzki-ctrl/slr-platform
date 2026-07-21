#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."

AI_NODE_HOST="${AI_NODE_HOST:-cloud@ai-node}"
REMOTE_DIR="${REMOTE_DIR:-/srv/slr-platform}"
BRANCH="${BRANCH:-main}"

[[ -z "$(git status --porcelain)" ]] || {
  echo "Najpierw wykonaj commit niezapisanych zmian."
  exit 1
}

git push origin "$BRANCH"

ssh "$AI_NODE_HOST" bash <<REMOTE
set -Eeuo pipefail
cd "$REMOTE_DIR"
git fetch origin
git checkout "$BRANCH"
git pull --ff-only origin "$BRANCH"
sudo docker compose up -d --build
sudo docker compose ps
REMOTE
