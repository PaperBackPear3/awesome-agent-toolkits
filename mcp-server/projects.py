"""Projects tools — cross-project registry, name -> absolute path mapping."""
from __future__ import annotations

import os
from pathlib import Path

from storage import (
    err,
    ensure_dirs,
    file_lock,
    load_json,
    now_iso,
    ok,
    parse_tag_list,
    projects_path,
    save_json,
)


_RESERVED = {"_global"}


def _load() -> dict:
    return load_json(projects_path(), {}) or {}


def _save(reg: dict) -> None:
    save_json(projects_path(), reg)


def register(server) -> int:
    ensure_dirs()

    @server.tool()
    def project_register(name: str, path: str, description: str = "", tags: str = "") -> str:
        """Register a repo or folder by name. Path must be absolute and exist."""
        if not name or name in _RESERVED:
            return err("invalid_name", f"name must be non-empty and not in {sorted(_RESERVED)}")
        abs_path = Path(path).expanduser()
        if not abs_path.is_absolute():
            return err("invalid_path", "path must be absolute")
        if not abs_path.exists():
            return err("not_found", f"path does not exist: {abs_path}")
        with file_lock(projects_path()):
            reg = _load()
            if name in reg:
                return err("conflict", f"project '{name}' already registered")
            now = now_iso()
            reg[name] = {
                "name": name,
                "path": str(abs_path),
                "description": description,
                "tags": parse_tag_list(tags),
                "created": now,
                "updated": now,
            }
            _save(reg)
        return ok(reg[name])

    @server.tool()
    def project_list(tags: str = "") -> str:
        """List registered projects, optionally filtered by comma-separated tags."""
        reg = _load()
        wanted = set(parse_tag_list(tags))
        out = []
        for v in reg.values():
            if wanted and not wanted.issubset(set(v.get("tags") or [])):
                continue
            out.append(v)
        return ok({"count": len(out), "items": out})

    @server.tool()
    def project_get(name: str) -> str:
        """Look up a single registered project by name."""
        reg = _load()
        if name not in reg:
            return err("not_found", f"project '{name}' not registered")
        return ok(reg[name])

    @server.tool()
    def project_update(name: str, path: str = "", description: str = "", tags: str = "") -> str:
        """Update path, description, or tags on a registered project."""
        with file_lock(projects_path()):
            reg = _load()
            if name not in reg:
                return err("not_found", f"project '{name}' not registered")
            entry = reg[name]
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
            entry["updated"] = now_iso()
            _save(reg)
        return ok(entry)

    @server.tool()
    def project_remove(name: str) -> str:
        """Remove a project from the registry (does not delete files)."""
        with file_lock(projects_path()):
            reg = _load()
            if name not in reg:
                return err("not_found", f"project '{name}' not registered")
            del reg[name]
            _save(reg)
        return ok({"removed": name})

    @server.tool()
    def project_resolve(name: str, relative_path: str = "") -> str:
        """Return the absolute path for a project, optionally joined with a relative subpath."""
        reg = _load()
        if name not in reg:
            return err("not_found", f"project '{name}' not registered")
        base = Path(reg[name]["path"])
        if relative_path:
            p = (base / relative_path).resolve()
            # Soft containment check
            try:
                p.relative_to(base.resolve())
            except ValueError:
                return err("escape", "relative_path escapes project root")
            return ok({"path": str(p), "exists": p.exists()})
        return ok({"path": str(base), "exists": base.exists()})

    return 6
