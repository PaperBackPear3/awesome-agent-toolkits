"""Todos tools — persistent todo items, optionally project-scoped (SQLite-backed)."""
from __future__ import annotations

import uuid
from typing import Any

import db
from storage import err, now_iso, ok, parse_tag_list, validate_project


_VALID_STATUS = {"open", "in_progress", "done", "cancelled"}


def _row_to_dict(row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "text": row["text"],
        "status": row["status"],
        "project": row["project"],
        "tags": db.unpack_list(row["tags"]),
        "blockers": db.unpack_list(row["blockers"]),
        "notes": row["notes"],
        "created": row["created"],
        "updated": row["updated"],
        "completed": row["completed"],
    }


def _get(tid: str) -> dict[str, Any] | None:
    row = db.get_conn().execute("SELECT * FROM todos WHERE id = ?", (tid,)).fetchone()
    return _row_to_dict(row) if row else None


def register(server) -> int:

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
        proj = project or "_global"
        with db.write_lock():
            db.get_conn().execute(
                "INSERT INTO todos(id, text, status, project, tags, blockers, notes, created, updated, completed) "
                "VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    tid, text, "open", proj,
                    db.pack_list(parse_tag_list(tags)),
                    db.pack_list(parse_tag_list(blockers)),
                    "", now, now, None,
                ),
            )
        return ok({"id": tid})

    @server.tool()
    def todo_list(project: str = "", status: str = "open", tags: str = "") -> str:
        """List todos. project='' means _global scope (use project_register name otherwise).
        status: open|in_progress|done|cancelled|active|all. 'active' = open + in_progress.
        tags: comma-separated; a todo must have ALL listed tags to match.
        """
        okp, e = validate_project(project)
        if not okp:
            return e
        proj = project or "_global"
        clauses = ["project = ?"]
        params: list[Any] = [proj]
        if status == "active":
            clauses.append("status IN ('open','in_progress')")
        elif status != "all":
            clauses.append("status = ?")
            params.append(status)
        sql = "SELECT * FROM todos WHERE " + " AND ".join(clauses) + " ORDER BY created"
        rows = db.get_conn().execute(sql, params).fetchall()
        wanted = set(parse_tag_list(tags))
        out = []
        for r in rows:
            d = _row_to_dict(r)
            if wanted and not wanted.issubset(set(d["tags"])):
                continue
            out.append(d)
        return ok({"count": len(out), "items": out})

    @server.tool()
    def todo_get(id: str) -> str:
        """Get a todo's full details."""
        t = _get(id)
        if not t:
            return err("not_found", f"Todo '{id}' not found.")
        return ok(t)

    @server.tool()
    def todo_update(id: str, text: str = "", status: str = "", project: str = "") -> str:
        """Partial update — change text, status, and/or move to a different project."""
        t = _get(id)
        if not t:
            return err("not_found", f"Todo '{id}' not found.")
        if status and status not in _VALID_STATUS:
            return err("invalid_status", f"status must be one of {sorted(_VALID_STATUS)}")
        if project:
            okp, e = validate_project(project)
            if not okp:
                return e
        sets = []
        params: list[Any] = []
        if text:
            sets.append("text = ?")
            params.append(text)
        if status:
            sets.append("status = ?")
            params.append(status)
            sets.append("completed = ?")
            params.append(now_iso() if status == "done" else None)
        if project and project != t["project"]:
            sets.append("project = ?")
            params.append(project)
        sets.append("updated = ?")
        params.append(now_iso())
        params.append(id)
        with db.write_lock():
            db.get_conn().execute(f"UPDATE todos SET {', '.join(sets)} WHERE id = ?", params)
        return ok(_get(id))

    @server.tool()
    def todo_complete(id: str) -> str:
        """Mark a todo as done."""
        return _set_status(id, "done")

    @server.tool()
    def todo_delete(id: str) -> str:
        """Delete a todo."""
        if _get(id) is None:
            return err("not_found", f"Todo '{id}' not found.")
        with db.write_lock():
            db.get_conn().execute("DELETE FROM todos WHERE id = ?", (id,))
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
        proj = project or "_global"
        rows = db.get_conn().execute("SELECT tags FROM todos WHERE project = ?", (proj,)).fetchall()
        tags: set[str] = set()
        for r in rows:
            for tg in db.unpack_list(r["tags"]):
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
    t = _get(tid)
    if not t:
        return err("not_found", f"Todo '{tid}' not found.")
    with db.write_lock():
        db.get_conn().execute(
            "UPDATE todos SET status=?, completed=?, updated=? WHERE id=?",
            (status, now_iso() if status == "done" else None, now_iso(), tid),
        )
    return ok(_get(tid))


def _tag_op(tid: str, tag: str, add: bool) -> str:
    t = _get(tid)
    if not t:
        return err("not_found", f"Todo '{tid}' not found.")
    cur = set(t["tags"])
    if add:
        cur.add(tag)
    else:
        cur.discard(tag)
    with db.write_lock():
        db.get_conn().execute(
            "UPDATE todos SET tags=?, updated=? WHERE id=?",
            (db.pack_list(sorted(cur)), now_iso(), tid),
        )
    return ok(_get(tid))


def _blocker_op(tid: str, blocker_id: str, add: bool) -> str:
    t = _get(tid)
    if not t:
        return err("not_found", f"Todo '{tid}' not found.")
    cur = set(t["blockers"])
    if add:
        cur.add(blocker_id)
    else:
        cur.discard(blocker_id)
    with db.write_lock():
        db.get_conn().execute(
            "UPDATE todos SET blockers=?, updated=? WHERE id=?",
            (db.pack_list(sorted(cur)), now_iso(), tid),
        )
    return ok(_get(tid))
