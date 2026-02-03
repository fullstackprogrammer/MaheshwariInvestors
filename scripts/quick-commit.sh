#!/usr/bin/env bash
# Quick add + commit + push. Run from repo root.
# Usage: ./scripts/quick-commit.sh "Your commit message"
#        ./scripts/quick-commit.sh   (prompts for message)

set -e
MSG="${1:-}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT"

if [ -z "$MSG" ]; then
  echo -n "Commit message: "
  read -r MSG
fi
if [ -z "$(echo "$MSG" | tr -d ' ')" ]; then
  echo "No message. Exiting."
  exit 1
fi

git add -A
git status
git commit -m "$MSG"
git push
