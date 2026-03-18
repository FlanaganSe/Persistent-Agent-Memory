---
name: milestone
description: Execute the next milestone from the current plan.
user_invocable: true
---

# Milestone

Execute the next incomplete milestone from the active plan.

## Process
1. Read the active plan from `.claude/plans/`
2. Find the next incomplete milestone
3. Implement it, committing at logical checkpoints
4. Run `/verify` after completion
5. Update the plan to mark the milestone complete

## Rules
- One milestone at a time — don't jump ahead
- If blocked, stop and explain rather than guessing
- Follow the escalation policy for repeated failures
