"""Prompt templates — CRUD for reusable, parameterised prompt templates (SQLite-backed)."""
from __future__ import annotations

import re
import uuid
from typing import Any

import db
from storage import err, now_iso, ok, parse_tag_list


# Matches {variable_name} placeholders (letters, digits, underscores)
_VAR_RE = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}")


def _extract_variables(template: str) -> list[str]:
    """Return sorted unique variable names found in the template."""
    return sorted(set(_VAR_RE.findall(template)))


def _row_to_dict(row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "name": row["name"],
        "description": row["description"],
        "template": row["template"],
        "variables": db.unpack_list(row["variables"]),
        "tags": db.unpack_list(row["tags"]),
        "created": row["created"],
        "updated": row["updated"],
    }


def _get(tid: str) -> dict[str, Any] | None:
    row = db.get_conn().execute(
        "SELECT * FROM prompt_templates WHERE id = ?", (tid,)
    ).fetchone()
    return _row_to_dict(row) if row else None


def _get_by_name(name: str) -> dict[str, Any] | None:
    row = db.get_conn().execute(
        "SELECT * FROM prompt_templates WHERE name = ?", (name,)
    ).fetchone()
    return _row_to_dict(row) if row else None


def register(server) -> int:

    @server.tool()
    def template_create(name: str, template: str, description: str = "", tags: str = "") -> str:
        """Create a reusable prompt template.
        Use {variable_name} placeholders in the template text; they are extracted automatically.
        name must be unique.
        """
        if not name.strip():
            return err("missing_arg", "name required")
        if not template.strip():
            return err("missing_arg", "template required")
        if _get_by_name(name):
            return err("duplicate", f"A template named '{name}' already exists.")
        tid = uuid.uuid4().hex
        now = now_iso()
        variables = _extract_variables(template)
        with db.write_lock():
            db.get_conn().execute(
                "INSERT INTO prompt_templates(id, name, description, template, variables, tags, created, updated) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (
                    tid, name, description,
                    template,
                    db.pack_list(variables),
                    db.pack_list(parse_tag_list(tags)),
                    now, now,
                ),
            )
        return ok(_get(tid))

    @server.tool()
    def template_list(tags: str = "") -> str:
        """List all prompt templates. Optionally filter by tags (comma-separated, must match ALL)."""
        rows = db.get_conn().execute(
            "SELECT * FROM prompt_templates ORDER BY name"
        ).fetchall()
        wanted = set(parse_tag_list(tags))
        out = []
        for r in rows:
            d = _row_to_dict(r)
            if wanted and not wanted.issubset(set(d["tags"])):
                continue
            out.append(d)
        return ok({"count": len(out), "items": out})

    @server.tool()
    def template_get(id_or_name: str) -> str:
        """Get a prompt template by id or name."""
        t = _get(id_or_name) or _get_by_name(id_or_name)
        if not t:
            return err("not_found", f"Template '{id_or_name}' not found.")
        return ok(t)

    @server.tool()
    def template_update(id_or_name: str, name: str = "", description: str = "", template: str = "", tags: str = "") -> str:
        """Partial update for a prompt template. Pass only the fields you want to change."""
        t = _get(id_or_name) or _get_by_name(id_or_name)
        if not t:
            return err("not_found", f"Template '{id_or_name}' not found.")
        if name and name != t["name"] and _get_by_name(name):
            return err("duplicate", f"A template named '{name}' already exists.")
        sets = []
        params: list[Any] = []
        if name:
            sets.append("name = ?")
            params.append(name)
        if description:
            sets.append("description = ?")
            params.append(description)
        if template:
            sets.append("template = ?")
            params.append(template)
            sets.append("variables = ?")
            params.append(db.pack_list(_extract_variables(template)))
        if tags:
            sets.append("tags = ?")
            params.append(db.pack_list(parse_tag_list(tags)))
        if not sets:
            return err("missing_arg", "provide at least one field to update")
        sets.append("updated = ?")
        params.append(now_iso())
        params.append(t["id"])
        with db.write_lock():
            db.get_conn().execute(f"UPDATE prompt_templates SET {', '.join(sets)} WHERE id = ?", params)
        return ok(_get(t["id"]))

    @server.tool()
    def template_delete(id_or_name: str) -> str:
        """Delete a prompt template by id or name."""
        t = _get(id_or_name) or _get_by_name(id_or_name)
        if not t:
            return err("not_found", f"Template '{id_or_name}' not found.")
        with db.write_lock():
            db.get_conn().execute("DELETE FROM prompt_templates WHERE id = ?", (t["id"],))
        return ok({"deleted": t["id"], "name": t["name"]})

    @server.tool()
    def template_render(id_or_name: str, variables: str = "") -> str:
        """Render a prompt template by substituting {variable} placeholders.
        variables: comma-separated key=value pairs, e.g. "lang=Python,topic=async".
        Returns the rendered text plus a list of any unresolved placeholders.
        """
        t = _get(id_or_name) or _get_by_name(id_or_name)
        if not t:
            return err("not_found", f"Template '{id_or_name}' not found.")

        var_map: dict[str, str] = {}
        for pair in (variables or "").split(","):
            pair = pair.strip()
            if "=" in pair:
                k, _, v = pair.partition("=")
                var_map[k.strip()] = v.strip()

        rendered = t["template"]
        unresolved: list[str] = []
        for var in _VAR_RE.findall(rendered):
            if var in var_map:
                rendered = rendered.replace(f"{{{var}}}", var_map[var])
            elif var not in unresolved:
                unresolved.append(var)

        return ok({
            "rendered": rendered,
            "unresolved": unresolved,
            "template_id": t["id"],
            "template_name": t["name"],
        })

    return 6
