# agent-toolkit-mcp-server

A user-facing MCP server that augments Claude Code's built-in harness with four
capability areas the harness does not have natively:

- **Notes** — persistent, named markdown notes with SQLite FTS5 full-text search
- **Todos** — persistent todos, cross-session, optionally project-scoped
- **Timers** — durable scheduled wake-ups (SQLite-backed; poll fired events)
- **Projects** — a cross-project registry of repos/folders by name, with
  optional member sub-paths and per-project markdown docs

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
├── data.db                       # SQLite: todos, timers, projects, FTS index
├── notes/
│   ├── _global/
│   └── <project>/                # markdown files with YAML frontmatter
└── projects/
    └── <project>/docs/           # per-project markdown docs
```

Notes and project docs are markdown files with YAML frontmatter — canonical,
human-editable, greppable on disk. The FTS5 index is rebuilt from disk on
startup and kept fresh by note/doc mutating tools. Mutating tools bump
`revision`; pass `expected_revision` to detect concurrent writes.

The first time you start v0.3.0 against an existing `~/.agent-toolkit/` from
v0.2.x, the server migrates `projects.json`, `todos/`, and `timers/` into
`data.db`, then renames the source paths with a `.migrated` suffix as backup.
Migration is idempotent.

Project scope: omit `project` (or pass an empty string) for the global scope.
Otherwise the value must match a name registered via `project_register`.

## Tool index

### Notes (16)
`note_list`, `note_tags_list`, `note_read`, `note_find`, `note_tail`,
`note_write`, `note_rename`, `note_add_tags`, `note_remove_tags`, `note_append`,
`note_append_section`, `note_edit`, `note_clear`, `note_delete`, `note_archive`,
`note_search`

`note_search` runs an FTS5 MATCH query across notes and (optionally) project
docs. Empty `project` = search all scopes; named project = restrict to that
scope. Returns `{kind, project, name, title, snippet}`.

### Todos (11)
`todo_create`, `todo_list`, `todo_get`, `todo_update`, `todo_complete`,
`todo_delete`, `todo_add_tag`, `todo_remove_tag`, `todo_tags_list`,
`todo_add_blocker`, `todo_remove_blocker`

`todo_list` status values: `open|in_progress|done|cancelled|active|all` where
`active` = open + in_progress.

### Timers (7)
`timer_set`, `timer_list`, `timer_cancel`, `timer_pause`, `timer_resume`,
`timer_fired`, `timer_ack`

A daemon thread inside the server wakes every 5 seconds, moves due timers from
`timers` into `fired_timers`, and re-arms recurring ones.

### Projects (10)
`project_register`, `project_list`, `project_get`, `project_update`,
`project_remove`, `project_resolve`, `project_doc_list`, `project_doc_read`,
`project_doc_write`, `project_doc_delete`

A project may include optional `members` — a JSON array of
`{path, label, description}` entries describing related folders/repos that make
up the logical project (e.g. frontend + backend in a polyrepo). `project_get`
returns `members` plus the list of attached doc names. Project docs live at
`<home>/projects/<project>/docs/<slug>.md` and are indexed by FTS together with
notes; surface them with `note_search` (or list with `project_doc_list`).

## Errors

All tool errors are returned as JSON, never raised:

```json
{ "error": true, "code": "not_found", "message": "..." }
```

Revision conflicts return `code: "revision_mismatch"` along with the current
revision so agents can re-read and retry.
