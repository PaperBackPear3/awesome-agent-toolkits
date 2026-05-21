"""Post-Work Checks MCP server.

Manages per-project post-work todo lists. Each todo has:
  - title / description
  - status: "always" | "conditional" | "disabled"
  - condition: optional string (for conditional todos, describes when to act)

State lives in a single JSON file: ~/.post-work-checks/todos.json
Override the directory with POST_WORK_CHECKS_HOME env var.
"""
from __future__ import annotations

import json
import os
import uuid
from pathlib import Path

from mcp.server.fastmcp import FastMCP

# ---------------------------------------------------------------------------
# Storage helpers
# ---------------------------------------------------------------------------

_VALID_STATUSES = {"always", "conditional", "disabled"}


def _home() -> Path:
    base = os.environ.get("POST_WORK_CHECKS_HOME", "")
    if base:
        return Path(base)
    return Path.home() / ".post-work-checks"


def _db_path() -> Path:
    return _home() / "todos.json"


def _load() -> dict[str, list[dict]]:
    path = _db_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def _save(data: dict[str, list[dict]]) -> None:
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))


def _resolve_project(project_path: str) -> str:
    return str(Path(project_path).resolve())


# ---------------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------------

mcp = FastMCP(
    name="post-work-checks",
    instructions=(
        "Post-Work Checks MCP. Manages per-project checklists of tasks the agent "
        "should perform after finishing work. Each todo has a status: 'always' "
        "(always run) or 'conditional' (run only when a stated condition is met). "
        "Disabled todos are hidden from normal listing — use include_disabled=true "
        "only when managing (re-enabling) them. "
        "Pass the project directory as project_path; defaults to cwd."
    ),
)


@mcp.tool()
def list_todos(project_path: str = "", include_disabled: bool = False) -> dict:
    """List post-work todos for a project.

    By default disabled todos are excluded — they don't appear in the workflow.
    Set include_disabled=true only when you need to inspect or re-enable them.

    project_path: absolute or relative path to the project directory (defaults to cwd).
    include_disabled: when true, disabled todos are included in the result.
    """
    project = _resolve_project(project_path or os.getcwd())
    data = _load()
    all_todos = data.get(project, [])

    if include_disabled:
        todos = all_todos
    else:
        todos = [t for t in all_todos if t["status"] != "disabled"]

    return {
        "project": project,
        "todos": todos,
        "summary": {
            "always": sum(1 for t in todos if t["status"] == "always"),
            "conditional": sum(1 for t in todos if t["status"] == "conditional"),
        },
    }


@mcp.tool()
def create_todo(
    title: str,
    project_path: str = "",
    description: str = "",
    status: str = "always",
    condition: str = "",
) -> dict:
    """Create a new post-work todo for a project.

    title: short label for the task (e.g. "Update README").
    description: longer explanation of what to do.
    status: 'always' | 'conditional' | 'disabled'.
    condition: when status is 'conditional', describe the trigger
               (e.g. "if documentation files changed").
    project_path: project directory (defaults to cwd).
    """
    if status not in _VALID_STATUSES:
        return {"error": f"Invalid status '{status}'. Must be one of: {sorted(_VALID_STATUSES)}"}

    project = _resolve_project(project_path or os.getcwd())
    data = _load()
    todos = data.setdefault(project, [])

    todo = {
        "id": str(uuid.uuid4())[:8],
        "title": title,
        "description": description,
        "status": status,
        "condition": condition,
    }
    todos.append(todo)
    _save(data)
    return {"created": todo, "project": project}


@mcp.tool()
def update_todo(
    todo_id: str,
    project_path: str = "",
    title: str = "",
    description: str = "",
    condition: str = "",
) -> dict:
    """Update the content of an existing todo (title, description, condition).

    Searches all todos including disabled ones so you can edit a todo before re-enabling it.
    To change status use set_todo_status instead.

    todo_id: the id field returned by list_todos or create_todo.
    project_path: project directory (defaults to cwd).
    """
    project = _resolve_project(project_path or os.getcwd())
    data = _load()
    todos = data.get(project, [])

    for todo in todos:
        if todo["id"] == todo_id:
            if title:
                todo["title"] = title
            if description:
                todo["description"] = description
            if condition:
                todo["condition"] = condition
            _save(data)
            return {"updated": todo, "project": project}

    return {"error": f"Todo '{todo_id}' not found in project '{project}'"}


@mcp.tool()
def set_todo_status(
    todo_id: str,
    status: str,
    project_path: str = "",
) -> dict:
    """Change the status of a todo: 'always', 'conditional', or 'disabled'.

    'always'      — run this check every time work finishes.
    'conditional' — run only when the todo's condition is met (check condition field).
    'disabled'    — exclude from workflow; hidden from list_todos unless include_disabled=true.

    todo_id: the id field returned by list_todos (use include_disabled=true to find disabled ones).
    project_path: project directory (defaults to cwd).
    """
    if status not in _VALID_STATUSES:
        return {"error": f"Invalid status '{status}'. Must be one of: {sorted(_VALID_STATUSES)}"}

    project = _resolve_project(project_path or os.getcwd())
    data = _load()
    todos = data.get(project, [])

    for todo in todos:
        if todo["id"] == todo_id:
            old_status = todo["status"]
            todo["status"] = status
            _save(data)
            return {"todo_id": todo_id, "old_status": old_status, "new_status": status, "project": project}

    return {"error": f"Todo '{todo_id}' not found in project '{project}'"}


@mcp.tool()
def delete_todo(
    todo_id: str,
    project_path: str = "",
) -> dict:
    """Permanently delete a post-work todo.

    Searches all todos including disabled ones.
    todo_id: the id field returned by list_todos.
    project_path: project directory (defaults to cwd).
    """
    project = _resolve_project(project_path or os.getcwd())
    data = _load()
    todos = data.get(project, [])

    before = len(todos)
    data[project] = [t for t in todos if t["id"] != todo_id]
    if len(data[project]) == before:
        return {"error": f"Todo '{todo_id}' not found in project '{project}'"}

    _save(data)
    return {"deleted": todo_id, "project": project}


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
