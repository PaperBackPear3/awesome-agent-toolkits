"""Agent Toolkit MCP server entry point.

Provides four capability areas that augment Claude Code's built-in harness:
- Notes:    persistent, named markdown notes
- Todos:    persistent todos, cross-session, optionally project-scoped
- Timers:   durable scheduled wake-ups (file-based, agent polls fired events)
- Projects: cross-project registry of repos/folders
"""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

import notes
import projects
import timers
import todos
from storage import ensure_dirs, home


def build_server() -> FastMCP:
    ensure_dirs()
    server = FastMCP(
        name="agent-toolkit",
        instructions=(
            "Agent Toolkit MCP. Persistent notes, todos, timers, and a project registry. "
            f"State lives under {home()} (override with AGENT_TOOLKIT_HOME). "
            "Project-scoped tools take an optional `project` parameter; empty means global scope."
        ),
    )

    n_count = notes.register(server)
    t_count = todos.register(server)
    tm_count = timers.register(server)
    p_count = projects.register(server)

    server._tool_counts = {
        "notes": n_count,
        "todos": t_count,
        "timers": tm_count,
        "projects": p_count,
    }
    return server


def main() -> None:
    server = build_server()
    timers.start_watcher()
    server.run()


if __name__ == "__main__":
    main()
