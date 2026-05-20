# agent-toolkit-mcp-server

A user-facing MCP server that augments Claude Code's built-in harness with four
capability areas the harness does not have natively:

- **Notes** — persistent, named markdown notes (plans, designs, scratch)
- **Todos** — persistent todos, cross-session, optionally project-scoped
- **Timers** — durable scheduled wake-ups (file-based; poll fired events)
- **Projects** — a cross-project registry of repos/folders by name

## Install / run

```sh
uvx agent-toolkit-mcp-server
```

Or register it as an MCP server in your Claude Code config.

## Storage layout

All state lives under a single directory, configurable via `AGENT_TOOLKIT_HOME`
(default `~/.agent-toolkit/`):

```
~/.agent-toolkit/
├── projects.json
├── notes/
│   ├── _global/
│   └── <project>/
├── todos/
│   ├── _global/
│   └── <project>/
└── timers/
    ├── pending.json
    └── fired/
```

Notes are markdown files with YAML frontmatter (`tags`, `revision`, `archived`,
`created`, `updated`). Mutating tools bump `revision`; pass `expected_revision`
to detect concurrent writes.

Project scope: omit `project` (or pass an empty string) for the global scope.
Otherwise the value must match a name registered via `project_register`.

## Tool index

### Notes (15)
`note_list`, `note_tags_list`, `note_read`, `note_find`, `note_tail`,
`note_write`, `note_rename`, `note_add_tags`, `note_remove_tags`, `note_append`,
`note_append_section`, `note_edit`, `note_clear`, `note_delete`, `note_archive`

### Todos (11)
`todo_create`, `todo_list`, `todo_get`, `todo_update`, `todo_complete`,
`todo_delete`, `todo_add_tag`, `todo_remove_tag`, `todo_tags_list`,
`todo_add_blocker`, `todo_remove_blocker`

### Timers (7)
`timer_set`, `timer_list`, `timer_cancel`, `timer_pause`, `timer_resume`,
`timer_fired`, `timer_ack`

A daemon thread inside the server wakes every 5 seconds, flips due timers into
`timers/fired/`, and re-arms recurring ones.

### Projects (6)
`project_register`, `project_list`, `project_get`, `project_update`,
`project_remove`, `project_resolve`

## Errors

All tool errors are returned as JSON, never raised:

```json
{ "error": true, "code": "not_found", "message": "..." }
```

Revision conflicts return `code: "revision_mismatch"` along with the current
revision so agents can re-read and retry.
