---
name: plan
description: Create an implementation plan from a PRD or task description.
user_invocable: true
---

# Plan

Create a step-by-step implementation plan.

## Process
1. Read the PRD or task description
2. Break it into milestones (each independently testable)
3. For each milestone, list:
   - What changes are needed
   - Which files are affected
   - What tests to write
   - Acceptance criteria
4. Write the plan to `.claude/plans/plan-[name].md`

## Rules
- Milestones should be small enough to complete in one session
- Each milestone must have clear acceptance criteria
- Include a "risks and open questions" section
