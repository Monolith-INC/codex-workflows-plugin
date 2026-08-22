# Rules: Jules Asynchronous Orchestration

Use these rules to determine when to delegate tasks to the Jules MCP server for asynchronous execution.

## 1. Delegation Criteria

Delegate to Jules when a task meets ANY of the following:

- **Scope**: Affects more than 5 files or spans multiple architectural layers (e.g., UI + Domain + Data).
- **Complexity**: Requires large-scale refactoring, dependency upgrades, or project-wide unit test generation.
- **Duration**: Is expected to take more than 10 minutes of synchronous agent time.
- **Independence**: Can be performed on a separate branch without blocking the main workflow.

## 2. Worker Roles

Select the appropriate Jules role based on the task:

- `MAESTRO`: Use for high-level architecture changes or designing new modules.
- `CREW`: Use for implementing well-defined features or multiple related tasks.
- `FREELANCER`: Use for isolated bug fixes, documentation, or single-file changes.
- `EVALUATOR`: Use for code reviews, security audits, or task estimation.

## 3. Communication Protocol

- **Initialization**: Always provide a detailed `task_description` and a clear `title`.
- **Branching**: Use `jules_create_branch` to ensure isolation. Follow the project's branch naming convention: `{feature|bugfix|techdebt}/{description-in-pt-br}`.
- **Monitoring**: Use `jules_get_status` and `jules_get_activities` periodically to check progress. Do not poll excessively; once every 2-5 minutes is sufficient.
- **Handoff**: Once Jules completes a task, use `jules_merge_branch` (after a manual or automated review) to integrate the changes.

## 4. Shared Memory

Use `jules_store_memory` and `jules_read_memory` to pass context between the main Antigravity agent and Jules workers (e.g., API keys, specific architectural constraints, or PR numbers).

## 5. Tool Mapping

- For new features: `jules_create_worker(role: "CREW")`
- For bug fixes: `jules_fix_bug`
- For code reviews: `jules_review_code`
- For large refactors: `jules_create_worker(role: "MAESTRO")`
