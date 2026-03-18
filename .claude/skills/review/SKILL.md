---
name: review
description: Review recent changes for correctness, security, and quality.
user_invocable: true
---

# Review

Review code changes with fresh context.

## Process
1. Identify what changed (git diff, recent commits, or specified files)
2. Launch the reviewer agent for an independent assessment
3. Present findings organized by severity (blockers → warnings → nits)

## Rules
- Review with fresh eyes — don't assume correctness from context
- Focus on bugs, security issues, and logic errors over style
