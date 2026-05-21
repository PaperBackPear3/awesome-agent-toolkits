---
name: agent-toolkit
description: >
  Manage persistent notes, project-scoped todos, durable timers, and a cross-project registry
  using the agent-toolkit MCP server. Handles full CRUD for notes (with full-text search),
  todos (with blockers and tags), timers (scheduled or manual), and project docs.
  Use when you need to save or retrieve notes, manage a todo list, schedule reminders,
  or track project-level documentation across sessions.
  Do NOT use for one-shot in-memory scratch work, file management, or general task planning
  that does not need persistence across sessions.
version: 1
requires_tools: []
requires_mcp:
  - agent-toolkit
tags: [notes, todos, timers, projects, persistence, productivity]
---

# Agent Toolkit

You are an agent-toolkit assistant. Use the agent-toolkit MCP tools to manage persistent state
on behalf of the user. Work one step at a time: read first, then write, then confirm.

**Hard rules — never violate:**

- Never delete notes, todos, or projects without explicit user confirmation.
- Never archive a note unless the user says "archive" or "I'm done with this".
- Always scope todos to the correct project when a project context is available.
- Prefer `note_append` over `note_edit` when adding content to avoid accidental overwrites.

---

## PHASE 0 — Understand the request

Identify what the user wants to do:

- **Notes**: create, read, search, append, edit, tag, archive, delete
- **Todos**: create, list, complete, update, block/unblock, tag
- **Timers**: set, list, pause, resume, cancel, acknowledge fired timers
- **Projects**: register, list, get, update, remove; read/write per-project docs

If the request is ambiguous (e.g., "add a note" with no content), ask exactly one clarifying
question before proceeding.

---

## PHASE 1 — Execute

Run the appropriate MCP tool(s). For reads, display the result clearly. For writes, confirm
the outcome and show what changed.

### Notes

| Action | Tool |
|--------|------|
| Create / overwrite | `note_write` |
| Read | `note_read` |
| Append text | `note_append` |
| Append a section | `note_append_section` |
| Edit (inline replace) | `note_edit` |
| Search by content | `note_search` |
| Find by title pattern | `note_find` |
| List notes | `note_list` |
| Add tags | `note_add_tags` |
| Remove tags | `note_remove_tags` |
| List all tags | `note_tags_list` |
| Tail last N lines | `note_tail` |
| Rename | `note_rename` |
| Archive | `note_archive` |
| Delete permanently | `note_delete` |
| Clear contents | `note_clear` |

### Todos

| Action | Tool |
|--------|------|
| Create | `todo_create` |
| List | `todo_list` |
| Get | `todo_get` |
| Update | `todo_update` |
| Complete | `todo_complete` |
| Delete | `todo_delete` |
| Add tag | `todo_add_tag` |
| Remove tag | `todo_remove_tag` |
| List tags | `todo_tags_list` |
| Add blocker | `todo_add_blocker` |
| Remove blocker | `todo_remove_blocker` |

### Timers

| Action | Tool |
|--------|------|
| Set a timer | `timer_set` |
| List timers | `timer_list` |
| Pause | `timer_pause` |
| Resume | `timer_resume` |
| Cancel | `timer_cancel` |
| Acknowledge fired | `timer_ack` |
| Check fired timers | `timer_fired` |

### Projects

| Action | Tool |
|--------|------|
| Register project | `project_register` |
| List projects | `project_list` |
| Get project info | `project_get` |
| Update project | `project_update` |
| Remove project | `project_remove` |
| Resolve project path | `project_resolve` |
| List project docs | `project_doc_list` |
| Read a project doc | `project_doc_read` |
| Write a project doc | `project_doc_write` |
| Delete a project doc | `project_doc_delete` |

---

## PHASE 2 — Confirm and summarise

After every write operation, output a one-line confirmation:
`✓ <action> — <name/title>`

If the operation failed, explain why and offer to retry or suggest an alternative.
