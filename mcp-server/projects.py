"""Projects tools — cross-project registry plus per-project markdown docs (SQLite + files)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import db
from storage import (
    atomic_write_text,
    err,
    file_lock,
    now_iso,
    ok,
    parse_frontmatter,
    parse_tag_list,
    project_doc_path,
    project_docs_dir,
    read_text,
    render_frontmatter,
    slug,
)


_RESERVED = {"_global"}


def _row_to_dict(row) -> dict[str, Any]:
    return {
        "name": row["name"],
        "path": row["path"],
        "description": row["description"],
        "tags": db.unpack_list(row["tags"]),
        "members": db.unpack_list(row["members"]),
        "created": row["created"],
        "updated": row["updated"],
    }


def _validate_members(members_json: str) -> tuple[list[dict[str, Any]] | None, str | None]:
    if members_json is None or members_json == "":
        return [], None
    try:
        v = json.loads(members_json)
    except json.JSONDecodeError as ex:
        return None, err("invalid_arg", f"members must be a JSON array: {ex}")
    if not isinstance(v, list):
        return None, err("invalid_arg", "members must be a JSON array")
    out: list[dict[str, Any]] = []
    for i, m in enumerate(v):
        if not isinstance(m, dict) or "path" not in m:
            return None, err("invalid_arg", f"members[{i}] must be an object with a 'path' key")
        p = Path(str(m["path"])).expanduser()
        if not p.is_absolute():
            return None, err("invalid_path", f"members[{i}].path must be absolute")
        if not p.exists():
            return None, err("not_found", f"members[{i}].path does not exist: {p}")
        out.append({
            "path": str(p),
            "label": str(m.get("label") or ""),
            "description": str(m.get("description") or ""),
        })
    return out, None


def _list_doc_names(project: str) -> list[str]:
    d = project_docs_dir(project)
    if not d.exists():
        return []
    return sorted(f.stem for f in d.glob("*.md"))


def register(server) -> int:

    @server.tool()
    def project_register(name: str, path: str, description: str = "", tags: str = "", members: str = "") -> str:
        """Register a repo or folder by name. Path must be absolute and exist.
        members: optional JSON array like '[{"path": "/abs", "label": "frontend", "description": "..."}]'.
        """
        if not name or name in _RESERVED:
            return err("invalid_name", f"name must be non-empty and not in {sorted(_RESERVED)}")
        abs_path = Path(path).expanduser()
        if not abs_path.is_absolute():
            return err("invalid_path", "path must be absolute")
        if not abs_path.exists():
            return err("not_found", f"path does not exist: {abs_path}")
        mlist, merr = _validate_members(members)
        if merr:
            return merr
        now = now_iso()
        with db.write_lock():
            exists = db.get_conn().execute("SELECT 1 FROM projects WHERE name = ?", (name,)).fetchone()
            if exists:
                return err("conflict", f"project '{name}' already registered")
            db.get_conn().execute(
                "INSERT INTO projects(name, path, description, tags, members, created, updated) VALUES (?,?,?,?,?,?,?)",
                (name, str(abs_path), description, db.pack_list(parse_tag_list(tags)), db.pack_list(mlist), now, now),
            )
        # Pre-create docs dir for convenience.
        project_docs_dir(name).mkdir(parents=True, exist_ok=True)
        row = db.get_conn().execute("SELECT * FROM projects WHERE name = ?", (name,)).fetchone()
        return ok(_row_to_dict(row))

    @server.tool()
    def project_list(tags: str = "") -> str:
        """List registered projects, optionally filtered by comma-separated tags."""
        wanted = set(parse_tag_list(tags))
        rows = db.get_conn().execute("SELECT * FROM projects ORDER BY name").fetchall()
        out = []
        for r in rows:
            d = _row_to_dict(r)
            if wanted and not wanted.issubset(set(d["tags"])):
                continue
            out.append(d)
        return ok({"count": len(out), "items": out})

    @server.tool()
    def project_get(name: str) -> str:
        """Look up a single registered project by name (includes members + doc names)."""
        row = db.get_conn().execute("SELECT * FROM projects WHERE name = ?", (name,)).fetchone()
        if not row:
            return err("not_found", f"project '{name}' not registered")
        d = _row_to_dict(row)
        d["docs"] = _list_doc_names(name)
        return ok(d)

    @server.tool()
    def project_update(name: str, path: str = "", description: str = "", tags: str = "", members: str = "") -> str:
        """Update path, description, tags, and/or members on a registered project.
        members: pass a JSON array to replace the list, '[]' to clear. Omit to leave unchanged.
        """
        row = db.get_conn().execute("SELECT * FROM projects WHERE name = ?", (name,)).fetchone()
        if not row:
            return err("not_found", f"project '{name}' not registered")
        entry = _row_to_dict(row)
        if path:
            abs_path = Path(path).expanduser()
            if not abs_path.is_absolute():
                return err("invalid_path", "path must be absolute")
            if not abs_path.exists():
                return err("not_found", f"path does not exist: {abs_path}")
            entry["path"] = str(abs_path)
        if description:
            entry["description"] = description
        if tags:
            entry["tags"] = parse_tag_list(tags)
        if members != "":
            mlist, merr = _validate_members(members)
            if merr:
                return merr
            entry["members"] = mlist
        entry["updated"] = now_iso()
        with db.write_lock():
            db.get_conn().execute(
                "UPDATE projects SET path=?, description=?, tags=?, members=?, updated=? WHERE name=?",
                (entry["path"], entry["description"], db.pack_list(entry["tags"]),
                 db.pack_list(entry["members"]), entry["updated"], name),
            )
        return ok(entry)

    @server.tool()
    def project_remove(name: str) -> str:
        """Remove a project from the registry (does not delete files)."""
        with db.write_lock():
            cur = db.get_conn().execute("DELETE FROM projects WHERE name = ?", (name,))
            if cur.rowcount == 0:
                return err("not_found", f"project '{name}' not registered")
        return ok({"removed": name})

    @server.tool()
    def project_resolve(name: str, relative_path: str = "") -> str:
        """Return the absolute path for a project, optionally joined with a relative subpath."""
        row = db.get_conn().execute("SELECT path FROM projects WHERE name = ?", (name,)).fetchone()
        if not row:
            return err("not_found", f"project '{name}' not registered")
        base = Path(row["path"])
        if relative_path:
            p = (base / relative_path).resolve()
            try:
                p.relative_to(base.resolve())
            except ValueError:
                return err("escape", "relative_path escapes project root")
            return ok({"path": str(p), "exists": p.exists()})
        return ok({"path": str(base), "exists": base.exists()})

    # ---------- project docs ----------

    @server.tool()
    def project_doc_list(project: str) -> str:
        """List markdown docs attached to a project (slug, title, size, updated)."""
        row = db.get_conn().execute("SELECT 1 FROM projects WHERE name = ?", (project,)).fetchone()
        if not row:
            return err("not_found", f"project '{project}' not registered")
        d = project_docs_dir(project)
        items = []
        if d.exists():
            for f in sorted(d.glob("*.md")):
                try:
                    meta, body = parse_frontmatter(read_text(f))
                except OSError:
                    continue
                title = ""
                for line in body.splitlines():
                    if line.startswith("# "):
                        title = line[2:].strip()
                        break
                items.append({
                    "name": f.stem,
                    "title": title,
                    "revision": meta.get("revision", 0),
                    "updated": meta.get("updated"),
                    "size": f.stat().st_size,
                })
        return ok({"count": len(items), "items": items})

    @server.tool()
    def project_doc_read(project: str, name: str) -> str:
        """Read a project doc's full markdown content."""
        row = db.get_conn().execute("SELECT 1 FROM projects WHERE name = ?", (project,)).fetchone()
        if not row:
            return err("not_found", f"project '{project}' not registered")
        p = project_doc_path(project, name)
        if not p.exists():
            return err("not_found", f"doc '{name}' not found in project '{project}'")
        meta, body = parse_frontmatter(read_text(p))
        return ok({"name": slug(name), "project": project, "meta": meta, "content": body})

    @server.tool()
    def project_doc_write(project: str, name: str, content: str, expected_revision: int = -1) -> str:
        """Create or replace a project doc. Leading H1 in content is used as the title."""
        row = db.get_conn().execute("SELECT 1 FROM projects WHERE name = ?", (project,)).fetchone()
        if not row:
            return err("not_found", f"project '{project}' not registered")
        s = slug(name)
        p = project_doc_path(project, name)
        with file_lock(p):
            if p.exists():
                meta, _ = parse_frontmatter(read_text(p))
                if expected_revision >= 0 and int(meta.get("revision", 0)) != expected_revision:
                    return err("revision_mismatch",
                               f"expected revision {expected_revision}, got {meta.get('revision', 0)}",
                               current_revision=meta.get("revision", 0))
                meta["revision"] = int(meta.get("revision", 0)) + 1
                meta["updated"] = now_iso()
            else:
                t = now_iso()
                meta = {"revision": 1, "created": t, "updated": t}
            atomic_write_text(p, render_frontmatter(meta, content if content.endswith("\n") else content + "\n"))
        db.reindex_project_doc(s, project)
        return ok({"name": s, "project": project, "revision": meta["revision"]})

    @server.tool()
    def project_doc_delete(project: str, name: str, expected_revision: int = -1) -> str:
        """Delete a project doc."""
        row = db.get_conn().execute("SELECT 1 FROM projects WHERE name = ?", (project,)).fetchone()
        if not row:
            return err("not_found", f"project '{project}' not registered")
        s = slug(name)
        p = project_doc_path(project, name)
        if not p.exists():
            return err("not_found", f"doc '{name}' not found in project '{project}'")
        with file_lock(p):
            meta, _ = parse_frontmatter(read_text(p))
            if expected_revision >= 0 and int(meta.get("revision", 0)) != expected_revision:
                return err("revision_mismatch",
                           f"expected revision {expected_revision}, got {meta.get('revision', 0)}",
                           current_revision=meta.get("revision", 0))
            p.unlink()
        db.delete_project_doc_from_index(s, project)
        return ok({"deleted": s, "project": project})

    return 10
