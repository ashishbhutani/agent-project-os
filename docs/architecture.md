# Agent Project OS Architecture

## Overview
`agent-project-os` separates project planning from multi-agent execution.

- `planning/`: generates and validates task/dependency/tracker artifacts.
- `orchestration/`: runs worker and mayor loops over those artifacts.
- `common/`: shared schemas and utilities.

## Execution model
1. Workers claim ready tasks atomically and implement on ticket branches.
2. Workers mark `in_review` after ticket-level checks.
3. Mayor merges eligible `in_review` tasks into integration branch.
4. Mayor runs full-suite gate and marks `done` or `blocked`.

## Merge authority
Mayor-only merge policy by default.
