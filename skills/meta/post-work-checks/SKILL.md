---
name: post-work-checks
description: >
  Run through a project's post-work checklist after the agent finishes a task.
  Fetches the active todo list for the current project and executes each item:
  'always' todos run unconditionally, 'conditional' todos run only when their
  stated condition is met.
  Use when the user asks to run post-work checks, when wrapping up a task, before committing,
  when the user says "done", "finished", "wrap up", "ready to commit", or any signal that a
  work session is concluding and a project checklist may exist.
  Do NOT use for general task management, project planning, managing or editing post-work todos
  (use agent-toolkit for that), or any todo not scoped to post-work agent activities.
version: 1
requires_mcp:
  - post-work-checks
tags: [productivity, checklist, post-work, todos, agent]
---

# Post-Work Checks

Run this skill after finishing work to execute the project's post-work checklist.

**Hard rules — never violate:**

- Never skip an `always` todo — if it appears in the list, execute it.
- For `conditional` todos, evaluate the condition against actual observable state
  (git diff, changed files, etc.) — do not assume.
- If a todo fails or cannot be completed, report it clearly and continue the list.
- Do not modify, create, or delete todos — the user manages the list.

---

## Phase 1: Fetch the checklist

Call the MCP tool `mcp__post-work-checks__list_todos` with the current project path (absolute):

```
mcp__post-work-checks__list_todos(project_path="<absolute-cwd>")
```

If the result has zero todos, report "No post-work todos defined for this project" and stop.

For status semantics and how to evaluate conditions, see `references/status-guide.md`.

Display what will be executed before acting:

| # | Title | Status | Condition |
|---|-------|--------|-----------|
| 1 | Update README | always | — |
| 2 | Run type-check | conditional | if TS files changed |

---

## Phase 2: Execute todos in order

### `always` todos

Run the task described by `title` + `description`. Report done or failed before moving on.

### `conditional` todos

1. Evaluate the `condition` field against current state — use `git diff --name-only HEAD`
   or inspect files as needed.
2. Condition met → execute and report result.
3. Condition not met → report "Condition not met — skipped" and move on.

---

## Phase 3: Final report

```
Post-work checks complete for: /path/to/project

✓ Update README          [always]      — done
✓ Run type-check         [conditional] — condition met, done
– Lint CSS               [conditional] — condition not met, skipped
```

If any todo failed, list it with a brief error and suggest next steps.
