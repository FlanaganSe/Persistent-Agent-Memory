---
name: verify
description: Run all verification checks (tests, lint, typecheck).
user_invocable: true
---

# Verify

Run the full verification suite.

## Process
1. Launch the verifier agent
2. Run tests, linter, and type checker
3. Report results with pass/fail status

## Rules
- Run ALL checks, not just tests
- Report failures with exact error messages
- Do not auto-fix — just report
