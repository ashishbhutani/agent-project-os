# Planning Prompt (Reusable)

You are planning a multi-phase engineering delivery. Produce:
1. phase-wise task list,
2. dependency graph,
3. tracker-ready execution plan,
4. parallelization waves,
5. acceptance criteria.

Rules:
- Use deterministic ticket keys (`P<phase>-NN`).
- Keep tasks small enough for independent worktrees.
- Define explicit blockers for every cross-task dependency.
- Include test and validation requirements per task.
- Mark non-goals to prevent scope drift.
