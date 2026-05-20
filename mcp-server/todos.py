"""Todos tools — persistent todo items, optionally project-scoped."""
from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from storage import (
    err,
    ensure_dirs,
    file_lock,
    load_json,
    now_iso,
    ok,
    parse_tag_list,
    save_json,
    todos_dir,
    validate_project,
)


_VALID_STATUS = {"open", "in_progress", "done", "cancelled"}


def _path(tid: str, project: str) -> Path:
    return todos_dir(project) / f"{tid}.json"


def _load(tid: str, project: str) -> dict[str, Any] | None:
    p = _path(tid, project)
    if not p.exists():
        return None
    return load_json(p, None)


def _find_anywhere(tid: str) -> tuple[dict[str, Any] | None, Path | None]:
    """Find a todo across all project scopes."""
    base = todos_dir("").parent
    for sub in base.iterdir() if base.exists() else []:
        if not sub.is_dir():
            continue
        p = sub / f"{tid}.json"
        if p.exists():
            return load_json(p, None), p
    return None, None


def register(server) -> int:
    ensure_dirs()

    @server.tool()
    def todo_create(text: str, project: str = "", tags: str = "", blockers: str = "") -> str:
        """Create a new todo. Returns the new id."""
        okp, e = validate_project(project)
        if not okp:
            return e
        if not text.strip():
            return err("missing_arg", "text required")
        tid = uuid.uuid4().hex
        now = now_iso()
        todo = {
            "id": tid,
            "text": text,
            "status": "open",
            "tags": parse_tag_list(tags),
            "project": project or "_global",
            "created": now,
            "updated": now,
            "completed": None,
            "blockers": parse_tag_list(blockers),
            "notes": "",
        }
        p = _path(tid, project)
        with file_lock(p):
            save_json(p, todo)
        return ok({"id": tid})

    @server.tool()
    def todo_list(project: str = "", status: str = "open", tags: str = "") -> str:
        """List todos; status: open|in_progress|done|cancelled|active|all. 'active' = open + in_progress."""
        okp, e = validate_project(project)
        if not okp:
            return e
        d = todos_dir(project)
        d.mkdir(parents=True, exist_ok=True)
        wanted_tags = set(parse_tag_list(tags))
        out = []
        for p in sorted(d.glob("*.json")):
            t = load_json(p, None)
            if not t:
                continue
            t_status = t.get("status")
            if status == "active":
                if t_status not in ("open", "in_progress"):
                    continue
            elif status != "all" and t_status != status:
                continue
            if wanted_tags and not wanted_tags.issubset(set(t.get("tags") or [])):
                continue
            out.append(t)
        return ok({"count": len(out), "items": out})

    @server.tool()
    def todo_get(id: str) -> str:
        """Get a todo's full details."""
        t, _ = _find_anywhere(id)
        if not t:
            return err("not_found", f"Todo '{id}' not found.")
        return ok(t)

    @server.tool()
    def todo_update(id: str, text: str = "", status: str = "", project: str = "") -> str:
        """Partial update — change text, status, and/or move to a different project."""
        t, p = _find_anywhere(id)
        if not t or not p:
            return err("not_found", f"Todo '{id}' not found.")
        if status and status not in _VALID_STATUS:
            return err("invalid_status", f"status must be one of {sorted(_VALID_STATUS)}")
        if project:
            okp, e = validate_project(project)
            if not okp:
                return e
        with file_lock(p):
            if text:
                t["text"] = text
            if status:
                t["status"] = status
                t["completed"] = now_iso() if status == "done" else None
            t["updated"] = now_iso()
            if project and project != t.get("project"):
                # move file
                t["project"] = project
                new_p = _path(id, project)
                save_json(new_p, t)
                p.unlink()
                return ok(t)
            save_json(p, t)
        return ok(t)

    @server.tool()
    def todo_complete(id: str) -> str:
        """Mark a todo as done."""
        return _set_status(id, "done")

    @server.tool()
    def todo_delete(id: str) -> str:
        """Delete a todo."""
        t, p = _find_anywhere(id)
        if not t or not p:
            return err("not_found", f"Todo '{id}' not found.")
        with file_lock(p):
            p.unlink()
        return ok({"deleted": id})

    @server.tool()
    def todo_add_tag(id: str, tag: str) -> str:
        """Add a single tag to a todo."""
        return _tag_op(id, tag, add=True)

    @server.tool()
    def todo_remove_tag(id: str, tag: str) -> str:
        """Remove a single tag from a todo."""
        return _tag_op(id, tag, add=False)

    @server.tool()
    def todo_tags_list(project: str = "") -> str:
        """List distinct tags used by todos in scope."""
        okp, e = validate_project(project)
        if not okp:
            return e
        d = todos_dir(project)
        d.mkdir(parents=True, exist_ok=True)
        tags: set[str] = set()
        for p in d.glob("*.json"):
            t = load_json(p, None)
            if not t:
                continue
            for tg in t.get("tags") or []:
                tags.add(tg)
        return ok(sorted(tags))

    @server.tool()
    def todo_add_blocker(id: str, blocker_id: str) -> str:
        """Add another todo id as a blocker on this todo."""
        return _blocker_op(id, blocker_id, add=True)

    @server.tool()
    def todo_remove_blocker(id: str, blocker_id: str) -> str:
        """Remove a blocker from a todo."""
        return _blocker_op(id, blocker_id, add=False)

    return 11


def _set_status(tid: str, status: str) -> str:
    t, p = _find_anywhere(tid)
    if not t or not p:
        return err("not_found", f"Todo '{tid}' not found.")
    with file_lock(p):
        t["status"] = status
        t["completed"] = now_iso() if status == "done" else None
        t["updated"] = now_iso()
        save_json(p, t)
    return ok(t)


def _tag_op(tid: str, tag: str, add: bool) -> str:
    t, p = _find_anywhere(tid)
    if not t or not p:
        return err("not_found", f"Todo '{tid}' not found.")
    with file_lock(p):
        cur = set(t.get("tags") or [])
        if add:
            cur.add(tag)
        else:
            cur.discard(tag)
        t["tags"] = sorted(cur)
        t["updated"] = now_iso()
        save_json(p, t)
    return ok(t)


def _blocker_op(tid: str, blocker_id: str, add: bool) -> str:
    t, p = _find_anywhere(tid)
    if not t or not p:
        return err("not_found", f"Todo '{tid}' not found.")
    with file_lock(p):
        cur = set(t.get("blockers") or [])
        if add:
            cur.add(blocker_id)
        else:
            cur.discard(blocker_id)
        t["blockers"] = sorted(cur)
        t["updated"] = now_iso()
        save_json(p, t)
    return ok(t)
