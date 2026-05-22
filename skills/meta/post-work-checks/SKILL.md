---
name: post-work-checks
description: >
  Run through a project's post-work checklist after the agent finishes a task.
  Fetches the active todo list for the current project and executes each item:
  'always' todos run unconditionally, 'conditional' todos run only when their
  stated condition is met.
  Use when the user asks to run post-work checks, when work is finishing and
  there may be a checklist defined, or when the user says "check the post-work list".
  Also use when the user asks to preview or evaluate what would run ("show me the todos",
  "what would run if...", "which conditions are met") — in that case enter preview mode.
  Do NOT use for general task management, project planning, managing or editing
  post-work todos, or any todo not scoped to post-work agent activities.
version: 1
requires_mcp:
  - post-work-checks
tags: [productivity, checklist, post-work, todos, agent]
---

# Post-Work Checks

**Determine the mode before acting:**

- **Execute mode** — user says "run", "execute", "do the checks", or has just finished work and is closing out.
- **Preview mode** — user says "show me", "what would run", "which conditions are met", "evaluate", or asks about hypothetical file changes. In preview mode, evaluate conditions and display results — never execute the actual tasks.

When in doubt, prefer preview mode and ask if the user wants to proceed with execution.

**Hard rules — never violate:**

- Never skip an `always` todo — if it appears in the list, execute it (in execute mode).
- For `conditional` todos, evaluate the condition against actual observable state
  (git diff, changed files, etc.) — do not assume.
- If a todo fails or cannot be completed, report it clearly and continue the list.
- Do not modify, create, or delete todos — the user manages the list.
- In preview mode, never execute any todo action — only evaluate and display.

---

## Phase 1: Fetch the checklist

Call `list_todos` with the current project path:

```
list_todos(project_path="<cwd>")
```

If the result has zero todos, report "No post-work todos defined for this project" and stop.

Display what will be executed (or evaluated, in preview mode) before acting:

| # | Title | Status | Condition |
|---|-------|--------|-----------|
| 1 | Update README | always | — |
| 2 | Run type-check | conditional | if TS files changed |

---

## Phase 2a: Preview mode — evaluate only

For each todo, determine whether it would run given current state (or described hypothetical state):

- `always` todos: mark as **WOULD RUN**
- `conditional` todos: evaluate the condition against `git diff --name-only HEAD` (or the hypothetical file changes the user described), then mark as **WOULD RUN** or **WOULD SKIP (condition not met)**

Produce a preview table showing what would happen — but take no action on the tasks themselves.

---

## Phase 2b: Execute mode — run todos in order

### `always` todos

Run the task described by `title` + `description`. Report done or failed before moving on.

### `conditional` todos

1. Evaluate the `condition` field against current state — use `git diff --name-only HEAD`
   or inspect files as needed.
2. Condition met → execute and report result.
3. Condition not met → report "Condition not met — skipped" and move on.

---

## Phase 3: Final report

**Execute mode:**
```
Post-work checks complete for: /path/to/project

✓ Update README          [always]      — done
✓ Run type-check         [conditional] — condition met, done
– Lint CSS               [conditional] — condition not met, skipped
```

**Preview mode:**
```
Post-work check preview for: /path/to/project
(No actions were taken — this is a dry run)

→ Update README          [always]      — WOULD RUN
→ Run type-check         [conditional] — WOULD RUN (TS files changed)
– Lint CSS               [conditional] — WOULD SKIP (no CSS files changed)
```

If any todo failed (execute mode), list it with a brief error and suggest next steps.
