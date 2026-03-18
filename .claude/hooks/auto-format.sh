#!/usr/bin/env bash
# Hook: auto-format files after editing
# Adapt this to the project's formatter when stack is chosen

set -euo pipefail

FILE="${1:-}"

if [[ -z "$FILE" ]]; then
  exit 0
fi

# TBD: Add formatter invocation when stack is chosen
# Examples:
# prettier --write "$FILE"
# ruff format "$FILE"
# gofmt -w "$FILE"
# rustfmt "$FILE"
