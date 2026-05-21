# post-work-checks

Per-project post-work todo lists for your agent.

Define tasks the agent should run after finishing work — update the README, run linters,
check for stale docs, etc. Each todo has a **status** that controls when it runs:

| Status | Behaviour |
|--------|-----------|
| `always` | Run every time work finishes |
| `conditional` | Run only when the todo's `condition` is met (e.g. "if docs changed") |
| `disabled` | Hidden from the workflow; skipped silently |

## MCP tools

| Tool | What it does |
|------|-------------|
| `list_todos` | List active todos (disabled excluded by default; pass `include_disabled=true` to see them) |
| `create_todo` | Add a new todo |
| `update_todo` | Edit title, description, or condition (works on disabled todos too) |
| `set_todo_status` | Toggle `always` / `conditional` / `disabled` |
| `delete_todo` | Remove a todo permanently |

All tools accept an optional `project_path` argument (defaults to cwd).

## Storage

Todos live in `~/.post-work-checks/todos.json`, keyed by resolved project path.
Override the directory with the `POST_WORK_CHECKS_HOME` env var.

## Installation

```bash
# 1. Install the MCP server as a uv tool (one-time)
cd plugins/post-work-checks/server
uv tool install .

# 2. Add the MCP server to your Claude Code config
#    Copy the mcpServers block from .mcp.json into your settings, or
#    point Claude Code at this plugin directory.

# 3. Restart Claude Code — run /mcp to confirm post-work-checks is listed.
```

## Example: defining todos for a project

```
You: create a todo titled "Update README" with status always
You: create a todo titled "Run type-check" with status conditional, condition "if TypeScript files changed"
```

The `post-work-checks` skill will automatically run these checks at the end of each session.

## Upgrading

```bash
cd plugins/post-work-checks/server
uv tool install . --force
```
