"""Notes tools — persistent markdown notes with YAML frontmatter."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import db
from storage import (
    atomic_write_text,
    err,
    ensure_dirs,
    file_lock,
    notes_dir,
    now_iso,
    ok,
    parse_frontmatter,
    parse_tag_list,
    read_text,
    render_frontmatter,
    slug,
    validate_project,
)


def _path(name: str, project: str) -> Path:
    return notes_dir(project) / (slug(name) + ".md")


def _read_note(path: Path) -> tuple[dict[str, Any], str]:
    if not path.exists():
        return {}, ""
    return parse_frontmatter(read_text(path))


def _write_note(path: Path, meta: dict[str, Any], body: str) -> None:
    atomic_write_text(path, render_frontmatter(meta, body))


def _new_meta(tags: list[str]) -> dict[str, Any]:
    t = now_iso()
    return {
        "tags": tags,
        "revision": 1,
        "archived": False,
        "created": t,
        "updated": t,
    }


def _bump(meta: dict[str, Any]) -> None:
    meta["revision"] = int(meta.get("revision", 0)) + 1
    meta["updated"] = now_iso()


def _check_rev(meta: dict[str, Any], expected: int) -> str | None:
    if expected is None or expected < 0:
        return None
    cur = int(meta.get("revision", 0))
    if cur != expected:
        return err("revision_mismatch", f"expected revision {expected}, got {cur}", current_revision=cur)
    return None


def register(server) -> int:
    ensure_dirs()

    @server.tool()
    def note_list(project: str = "", tags: str = "", offset: int = 0, limit: int = 50) -> str:
        """List notes in scope with tags/revision; tags is a comma-separated filter."""
        okp, e = validate_project(project)
        if not okp:
            return e
        d = notes_dir(project)
        d.mkdir(parents=True, exist_ok=True)
        wanted = set(parse_tag_list(tags))
        results = []
        for p in sorted(d.glob("*.md")):
            meta, _ = _read_note(p)
            if meta.get("archived"):
                continue
            note_tags = set(meta.get("tags") or [])
            if wanted and not wanted.issubset(note_tags):
                continue
            results.append({
                "name": p.stem,
                "tags": sorted(note_tags),
                "revision": meta.get("revision", 0),
                "updated": meta.get("updated"),
            })
        total = len(results)
        sliced = results[offset:offset + limit] if limit > 0 else results[offset:]
        return ok({"total": total, "offset": offset, "limit": limit, "items": sliced})

    @server.tool()
    def note_tags_list(project: str = "") -> str:
        """List distinct tags used across notes in scope."""
        okp, e = validate_project(project)
        if not okp:
            return e
        d = notes_dir(project)
        d.mkdir(parents=True, exist_ok=True)
        tags: set[str] = set()
        for p in d.glob("*.md"):
            meta, _ = _read_note(p)
            for t in meta.get("tags") or []:
                tags.add(t)
        return ok(sorted(tags))

    @server.tool()
    def note_read(name: str, project: str = "", mode: str = "full", section: str = "") -> str:
        """Read a note. mode: full | headings | section (requires `section`)."""
        okp, e = validate_project(project)
        if not okp:
            return e
        p = _path(name, project)
        if not p.exists():
            return err("not_found", f"Note '{name}' not found.")
        meta, body = _read_note(p)
        if mode == "headings":
            outline = []
            for line in body.splitlines():
                m = re.match(r"^(#{1,6})\s+(.*)$", line)
                if m:
                    outline.append({"level": len(m.group(1)), "heading": m.group(2).strip()})
            return ok({"name": name, "revision": meta.get("revision", 0), "headings": outline})
        if mode == "section":
            if not section:
                return err("missing_arg", "section required for mode=section")
            sec = _extract_section(body, section)
            if sec is None:
                return err("not_found", f"section '{section}' not found")
            return ok({"name": name, "section": section, "content": sec})
        return ok({"name": name, "meta": meta, "content": body})

    @server.tool()
    def note_find(name: str, query: str, project: str = "", limit: int = 20) -> str:
        """Literal substring search within a single note. Returns matching line refs."""
        okp, e = validate_project(project)
        if not okp:
            return e
        p = _path(name, project)
        if not p.exists():
            return err("not_found", f"Note '{name}' not found.")
        _, body = _read_note(p)
        hits = []
        for i, line in enumerate(body.splitlines(), start=1):
            if query in line:
                hits.append({"line": i, "text": line})
                if len(hits) >= limit:
                    break
        return ok({"name": name, "query": query, "matches": hits})

    @server.tool()
    def note_tail(name: str, project: str = "", lines: int = 50) -> str:
        """Return the last N lines of a note's body."""
        okp, e = validate_project(project)
        if not okp:
            return e
        p = _path(name, project)
        if not p.exists():
            return err("not_found", f"Note '{name}' not found.")
        _, body = _read_note(p)
        tail = body.splitlines()[-max(0, lines):]
        return ok({"name": name, "lines": tail})

    @server.tool()
    def note_write(name: str, content: str, project: str = "", tags: str = "", expected_revision: int = -1) -> str:
        """Create or replace a note. Leading H1 in content is used as the title."""
        okp, e = validate_project(project)
        if not okp:
            return e
        p = _path(name, project)
        with file_lock(p):
            tlist = parse_tag_list(tags)
            if p.exists():
                meta, _ = _read_note(p)
                check = _check_rev(meta, expected_revision)
                if check:
                    return check
                if tlist:
                    meta["tags"] = tlist
                _bump(meta)
            else:
                meta = _new_meta(tlist)
            _write_note(p, meta, content if content.endswith("\n") else content + "\n")
        db.reindex_note(p.stem, project)
        return ok({"name": p.stem, "revision": meta["revision"]})

    @server.tool()
    def note_rename(name: str, new_name: str, project: str = "", expected_revision: int = -1) -> str:
        """Rename a note within the same project scope."""
        okp, e = validate_project(project)
        if not okp:
            return e
        p = _path(name, project)
        np = _path(new_name, project)
        if not p.exists():
            return err("not_found", f"Note '{name}' not found.")
        if np.exists():
            return err("conflict", f"Destination '{new_name}' already exists.")
        with file_lock(p):
            meta, body = _read_note(p)
            check = _check_rev(meta, expected_revision)
            if check:
                return check
            _bump(meta)
            _write_note(np, meta, body)
            p.unlink()
        db.delete_note_from_index(p.stem, project)
        db.reindex_note(np.stem, project)
        return ok({"name": np.stem, "revision": meta["revision"]})

    @server.tool()
    def note_add_tags(name: str, tags: str, project: str = "") -> str:
        """Add comma-separated tags to a note."""
        return _tag_op(name, project, tags, add=True)

    @server.tool()
    def note_remove_tags(name: str, tags: str, project: str = "") -> str:
        """Remove comma-separated tags from a note."""
        return _tag_op(name, project, tags, add=False)

    @server.tool()
    def note_append(name: str, content: str, project: str = "", expected_revision: int = -1) -> str:
        """Append content to the end of a note's body."""
        okp, e = validate_project(project)
        if not okp:
            return e
        p = _path(name, project)
        if not p.exists():
            return err("not_found", f"Note '{name}' not found.")
        with file_lock(p):
            meta, body = _read_note(p)
            check = _check_rev(meta, expected_revision)
            if check:
                return check
            if body and not body.endswith("\n"):
                body += "\n"
            body += content if content.endswith("\n") else content + "\n"
            _bump(meta)
            _write_note(p, meta, body)
        db.reindex_note(p.stem, project)
        return ok({"name": p.stem, "revision": meta["revision"]})

    @server.tool()
    def note_append_section(name: str, heading: str, content: str, project: str = "") -> str:
        """Append content under an existing heading in a note."""
        okp, e = validate_project(project)
        if not okp:
            return e
        p = _path(name, project)
        if not p.exists():
            return err("not_found", f"Note '{name}' not found.")
        with file_lock(p):
            meta, body = _read_note(p)
            new_body = _append_under_heading(body, heading, content)
            if new_body is None:
                return err("not_found", f"heading '{heading}' not found")
            _bump(meta)
            _write_note(p, meta, new_body)
        db.reindex_note(p.stem, project)
        return ok({"name": p.stem, "revision": meta["revision"]})

    @server.tool()
    def note_edit(name: str, content: str, project: str = "", section: str = "", line_start: int = 0, line_end: int = 0, expected_revision: int = -1) -> str:
        """Replace a section (by heading) or a line range (1-indexed, inclusive) in a note."""
        okp, e = validate_project(project)
        if not okp:
            return e
        p = _path(name, project)
        if not p.exists():
            return err("not_found", f"Note '{name}' not found.")
        with file_lock(p):
            meta, body = _read_note(p)
            check = _check_rev(meta, expected_revision)
            if check:
                return check
            if section:
                new_body = _replace_section(body, section, content)
                if new_body is None:
                    return err("not_found", f"section '{section}' not found")
            elif line_start > 0 and line_end >= line_start:
                lines = body.splitlines()
                if line_end > len(lines):
                    return err("out_of_range", f"line_end {line_end} exceeds {len(lines)}")
                new_lines = lines[:line_start - 1] + content.splitlines() + lines[line_end:]
                new_body = "\n".join(new_lines)
                if body.endswith("\n"):
                    new_body += "\n"
            else:
                return err("missing_arg", "provide either section or line_start+line_end")
            _bump(meta)
            _write_note(p, meta, new_body)
        db.reindex_note(p.stem, project)
        return ok({"name": p.stem, "revision": meta["revision"]})

    @server.tool()
    def note_clear(name: str, project: str = "", expected_revision: int = -1) -> str:
        """Clear a note's body while keeping its frontmatter."""
        okp, e = validate_project(project)
        if not okp:
            return e
        p = _path(name, project)
        if not p.exists():
            return err("not_found", f"Note '{name}' not found.")
        with file_lock(p):
            meta, _ = _read_note(p)
            check = _check_rev(meta, expected_revision)
            if check:
                return check
            _bump(meta)
            _write_note(p, meta, "")
        db.reindex_note(p.stem, project)
        return ok({"name": p.stem, "revision": meta["revision"]})

    @server.tool()
    def note_delete(name: str, project: str = "", expected_revision: int = -1) -> str:
        """Delete a note file."""
        okp, e = validate_project(project)
        if not okp:
            return e
        p = _path(name, project)
        if not p.exists():
            return err("not_found", f"Note '{name}' not found.")
        with file_lock(p):
            meta, _ = _read_note(p)
            check = _check_rev(meta, expected_revision)
            if check:
                return check
            p.unlink()
        db.delete_note_from_index(p.stem, project)
        return ok({"deleted": p.stem})

    @server.tool()
    def note_archive(name: str, project: str = "") -> str:
        """Mark a note as archived; archived notes are hidden from default list."""
        okp, e = validate_project(project)
        if not okp:
            return e
        p = _path(name, project)
        if not p.exists():
            return err("not_found", f"Note '{name}' not found.")
        with file_lock(p):
            meta, body = _read_note(p)
            meta["archived"] = True
            _bump(meta)
            _write_note(p, meta, body)
        db.delete_note_from_index(p.stem, project)
        return ok({"name": p.stem, "archived": True})

    @server.tool()
    def note_search(query: str, project: str = "", limit: int = 20, kinds: str = "note,project_doc") -> str:
        """FTS5 search across notes and (optionally) project docs.

        - query: FTS5 MATCH expression (e.g. 'foo bar', '"exact phrase"', 'foo OR bar').
        - project: empty = search across ALL scopes (including _global and all projects);
          named project = restrict to that scope only.
        - kinds: comma-separated subset of {note, project_doc}.
        Returns: list of {kind, project, name, title, snippet}.
        """
        if not query.strip():
            return err("missing_arg", "query required")
        klist = [k.strip() for k in kinds.split(",") if k.strip()]
        for k in klist:
            if k not in ("note", "project_doc"):
                return err("invalid_arg", f"unknown kind '{k}'; use note,project_doc")
        try:
            rows = db.fts_search(query, project, limit, klist)
        except Exception as ex:
            return err("fts_error", str(ex))
        return ok({"count": len(rows), "items": rows})

    # Hooks for note tag changes — re-index so the FTS row's tags column stays fresh.
    # _tag_op is at module scope; we wrap by re-indexing on every tag mutation
    # via post-call reindex in note_add_tags / note_remove_tags handlers below.

    return 16


def _tag_op(name: str, project: str, tags: str, add: bool) -> str:
    okp, e = validate_project(project)
    if not okp:
        return e
    p = _path(name, project)
    if not p.exists():
        return err("not_found", f"Note '{name}' not found.")
    with file_lock(p):
        meta, body = _read_note(p)
        cur = set(meta.get("tags") or [])
        ops = parse_tag_list(tags)
        if add:
            cur.update(ops)
        else:
            cur.difference_update(ops)
        meta["tags"] = sorted(cur)
        _bump(meta)
        _write_note(p, meta, body)
    db.reindex_note(p.stem, project)
    return ok({"name": p.stem, "tags": meta["tags"], "revision": meta["revision"]})


def _extract_section(body: str, heading: str) -> str | None:
    lines = body.splitlines()
    start = None
    level = 0
    for i, line in enumerate(lines):
        m = re.match(r"^(#{1,6})\s+(.*)$", line)
        if m and m.group(2).strip() == heading.strip():
            start = i
            level = len(m.group(1))
            break
    if start is None:
        return None
    end = len(lines)
    for j in range(start + 1, len(lines)):
        m = re.match(r"^(#{1,6})\s+", lines[j])
        if m and len(m.group(1)) <= level:
            end = j
            break
    return "\n".join(lines[start + 1:end]).strip("\n")


def _replace_section(body: str, heading: str, content: str) -> str | None:
    lines = body.splitlines()
    start = None
    level = 0
    for i, line in enumerate(lines):
        m = re.match(r"^(#{1,6})\s+(.*)$", line)
        if m and m.group(2).strip() == heading.strip():
            start = i
            level = len(m.group(1))
            break
    if start is None:
        return None
    end = len(lines)
    for j in range(start + 1, len(lines)):
        m = re.match(r"^(#{1,6})\s+", lines[j])
        if m and len(m.group(1)) <= level:
            end = j
            break
    new_lines = lines[:start + 1] + content.splitlines() + lines[end:]
    new_body = "\n".join(new_lines)
    if body.endswith("\n"):
        new_body += "\n"
    return new_body


def _append_under_heading(body: str, heading: str, content: str) -> str | None:
    lines = body.splitlines()
    start = None
    level = 0
    for i, line in enumerate(lines):
        m = re.match(r"^(#{1,6})\s+(.*)$", line)
        if m and m.group(2).strip() == heading.strip():
            start = i
            level = len(m.group(1))
            break
    if start is None:
        return None
    end = len(lines)
    for j in range(start + 1, len(lines)):
        m = re.match(r"^(#{1,6})\s+", lines[j])
        if m and len(m.group(1)) <= level:
            end = j
            break
    insertion = content.splitlines()
    # Trim trailing blanks at section end before inserting
    section_end = end
    while section_end > start + 1 and lines[section_end - 1].strip() == "":
        section_end -= 1
    new_lines = lines[:section_end] + [""] + insertion + lines[section_end:]
    new_body = "\n".join(new_lines)
    if body.endswith("\n"):
        new_body += "\n"
    return new_body
