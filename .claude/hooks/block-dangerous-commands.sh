#!/usr/bin/env bash
# Hook: block dangerous commands before execution
# Catches common destructive patterns that bypass deny rules

set -euo pipefail

COMMAND="${1:-}"

DANGEROUS_PATTERNS=(
  "rm -rf /"
  "rm -rf ~"
  "rm -rf \$HOME"
  "> /dev/sda"
  "mkfs"
  "dd if="
  ":(){:|:&};:"
)

for pattern in "${DANGEROUS_PATTERNS[@]}"; do
  if [[ "$COMMAND" == *"$pattern"* ]]; then
    echo "BLOCKED: Command contains dangerous pattern: $pattern" >&2
    exit 1
  fi
done
