---
name: post-work-checks
description: >
  Run through a project's post-work checklist after the agent finishes a task.
  Fetches todos scoped to the current project directory and acts on each one
  according to its status: executes 'always' todos unconditionally, evaluates
  the condition for 'conditional' todos and acts only when the condition is met,
  and skips 'disabled' todos.
  Use when the user asks to run post-work checks, when work is finishing and
  there may be a checklist defined, when the user says "check the post-work list",
  or when managing (creating, editing, toggling) post-work todos.
  Do NOT use for general task management, project planning, or any todo that is
  not scoped to post-work agent activities.
version: 1
requires_mcp:
  - post-work-checks
tags: [productivity, checklist, post-work, todos, agent]
---

# Post-Work Checks

Run this skill after finishing work to execute any tasks the user has defined
in the project's post-work checklist.

**Hard rules — never violate:**

- Always resolve the project path to an absolute path before calling tools.
- Never skip an `always` todo — if it is listed, it must be executed.
- For `conditional` todos, evaluate the condition against actual observable state
  (git diff, changed files, etc.) — do not assume.
- For `disabled` todos, report them as skipped; do not execute.
- If a todo fails or cannot be completed, report it clearly and continue the list.
- Never modify todo statuses without explicit user instruction.

---

## Phase 1: Fetch the checklist

Call `list_todos` with the current project path:

```
list_todos(project_path="<cwd>")
```

If the result has zero todos, report "No post-work todos defined for this project"
and offer to create the first one.

Display a summary table before acting:

| # | Title | Status | Condition |
|---|-------|--------|-----------|
| 1 | Update README | always | — |
| 2 | Run type-check | conditional | if TS files changed |
| 3 | Deploy to staging | disabled | — |

---

## Phase 2: Execute todos in order

Work through each todo sequentially.

### `always` todos

Run the task described by `title` + `description`. Report the result (done /
skipped / failed) before moving to the next item.

### `conditional` todos

1. Evaluate the `condition` field against the current state:
   - Use `git diff --name-only HEAD` or similar to check what changed.
   - Check file existence, timestamps, or other observable signals.
2. If the condition **is met** → execute the task and report result.
3. If the condition **is not met** → report "Condition not met — skipped" and move on.

### `disabled` todos

Report "Disabled — skipped" and move on. Do not execute.

---

## Phase 3: Managing todos (when user asks)

### Create a todo

Ask for (or accept inline):
- `title` — short label
- `description` — what the agent should do
- `status` — `always`, `conditional`, or `disabled`
- `condition` — required when status is `conditional`

Then call `create_todo`.

### Change a todo's status

Call `set_todo_status(todo_id=<id>, status=<new_status>)`.

Valid transitions:

| From | To | Effect |
|------|----|--------|
| `always` | `conditional` | Will require a condition — prompt user to set one via `update_todo` |
| `always` | `disabled` | Will skip on next run |
| `conditional` | `always` | Will always run from now on |
| `conditional` | `disabled` | Will skip on next run |
| `disabled` | `always` | Re-enables unconditionally |
| `disabled` | `conditional` | Re-enables with condition |

### Edit a todo's content

Call `update_todo(todo_id=<id>, ...)` with the fields to change
(title, description, condition). Status changes must go through `set_todo_status`.

### Delete a todo

Confirm with the user before calling `delete_todo` — deletion is permanent.

---

## Phase 4: Final report

After running all todos, output a structured summary:

```
Post-work checks complete for: /path/to/project

✓ Update README          [always]     — done
✓ Run type-check         [conditional] — condition met, done
– Deploy to staging      [disabled]   — skipped
```

If any todo failed, list it with a brief error and suggest next steps.

---

## Reference

See `references/status-guide.md` for guidance on choosing todo statuses
and writing effective conditions.
