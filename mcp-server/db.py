"""SQLite-backed storage: schema, migrations, FTS5 index for notes and project docs."""
from __future__ import annotations

import json
import re
import sqlite3
import threading
from pathlib import Path
from typing import Any, Iterable

from storage import (
    home,
    notes_dir,
    parse_frontmatter,
    project_doc_path,
    project_docs_dir,
    read_text,
)


_SCHEMA_VERSION = 1

# Single connection and write lock — sqlite WAL handles concurrent reads,
# writes are serialized via this lock to avoid "database is locked" under
# contention from the timer watcher thread.
_conn: sqlite3.Connection | None = None
_lock = threading.Lock()


def db_path() -> Path:
    return home() / "data.db"


def get_conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        p = db_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        _conn = sqlite3.connect(str(p), check_same_thread=False, isolation_level=None)
        _conn.row_factory = sqlite3.Row
        _conn.execute("PRAGMA journal_mode=WAL")
        _conn.execute("PRAGMA foreign_keys=ON")
        _conn.execute("PRAGMA synchronous=NORMAL")
    return _conn


def write_lock() -> threading.Lock:
    return _lock


# ---------- list <-> JSON helpers ----------

def pack_list(items: Iterable[Any] | None) -> str:
    return json.dumps(list(items or []))


def unpack_list(s: str | None) -> list[Any]:
    if not s:
        return []
    try:
        v = json.loads(s)
        return v if isinstance(v, list) else []
    except json.JSONDecodeError:
        return []


# ---------- schema ----------

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY);

CREATE TABLE IF NOT EXISTS projects (
    name TEXT PRIMARY KEY,
    path TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    tags TEXT NOT NULL DEFAULT '[]',
    members TEXT NOT NULL DEFAULT '[]',
    created TEXT NOT NULL,
    updated TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS todos (
    id TEXT PRIMARY KEY,
    text TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open',
    project TEXT NOT NULL DEFAULT '_global',
    tags TEXT NOT NULL DEFAULT '[]',
    blockers TEXT NOT NULL DEFAULT '[]',
    notes TEXT NOT NULL DEFAULT '',
    created TEXT NOT NULL,
    updated TEXT NOT NULL,
    completed TEXT
);
CREATE INDEX IF NOT EXISTS idx_todos_project ON todos(project);
CREATE INDEX IF NOT EXISTS idx_todos_status ON todos(status);

CREATE TABLE IF NOT EXISTS timers (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    fire_at TEXT NOT NULL,
    recurring_seconds INTEGER,
    message TEXT NOT NULL DEFAULT '',
    paused INTEGER NOT NULL DEFAULT 0,
    created TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_timers_fire_at ON timers(fire_at);

CREATE TABLE IF NOT EXISTS fired_timers (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    fired_at TEXT NOT NULL,
    fire_at TEXT NOT NULL,
    message TEXT NOT NULL DEFAULT ''
);

CREATE VIRTUAL TABLE IF NOT EXISTS notes_fts USING fts5(
    kind UNINDEXED,
    name UNINDEXED,
    project UNINDEXED,
    title,
    content,
    tags,
    tokenize='porter unicode61'
);
"""


def init_db() -> None:
    conn = get_conn()
    with _lock:
        conn.executescript(_SCHEMA_SQL)


def _current_schema_version(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT MAX(version) AS v FROM schema_version").fetchone()
    return int(row["v"] or 0) if row else 0


def _set_schema_version(conn: sqlite3.Connection, v: int) -> None:
    conn.execute("INSERT OR IGNORE INTO schema_version(version) VALUES (?)", (v,))


# ---------- migration from on-disk files ----------

def migrate_if_needed() -> dict[str, Any]:
    """Idempotent migration from JSON files into SQLite. Returns a summary dict."""
    conn = get_conn()
    summary: dict[str, Any] = {
        "schema_was": _current_schema_version(conn),
        "projects": 0,
        "todos": 0,
        "timers_pending": 0,
        "timers_fired": 0,
        "renamed": [],
    }
    with _lock:
        if summary["schema_was"] >= _SCHEMA_VERSION:
            return summary
        h = home()
        # projects.json
        pj = h / "projects.json"
        if pj.exists():
            try:
                data = json.loads(pj.read_text(encoding="utf-8")) or {}
            except json.JSONDecodeError:
                data = {}
            for name, entry in (data.items() if isinstance(data, dict) else []):
                if not isinstance(entry, dict):
                    continue
                conn.execute(
                    "INSERT OR IGNORE INTO projects(name, path, description, tags, members, created, updated) VALUES (?,?,?,?,?,?,?)",
                    (
                        name,
                        entry.get("path", ""),
                        entry.get("description", "") or "",
                        pack_list(entry.get("tags") or []),
                        pack_list(entry.get("members") or []),
                        entry.get("created") or entry.get("updated") or "",
                        entry.get("updated") or entry.get("created") or "",
                    ),
                )
                summary["projects"] += 1
            _safe_rename(pj, pj.with_suffix(".json.migrated"), summary)

        # todos/<scope>/*.json
        todos_root = h / "todos"
        if todos_root.exists() and todos_root.is_dir():
            for scope_dir in sorted(todos_root.iterdir()):
                if not scope_dir.is_dir():
                    continue
                for f in sorted(scope_dir.glob("*.json")):
                    try:
                        t = json.loads(f.read_text(encoding="utf-8"))
                    except (json.JSONDecodeError, OSError):
                        continue
                    if not isinstance(t, dict) or "id" not in t:
                        continue
                    conn.execute(
                        "INSERT OR IGNORE INTO todos(id, text, status, project, tags, blockers, notes, created, updated, completed) VALUES (?,?,?,?,?,?,?,?,?,?)",
                        (
                            t["id"],
                            t.get("text", ""),
                            t.get("status", "open"),
                            t.get("project") or "_global",
                            pack_list(t.get("tags") or []),
                            pack_list(t.get("blockers") or []),
                            t.get("notes", "") or "",
                            t.get("created") or "",
                            t.get("updated") or "",
                            t.get("completed"),
                        ),
                    )
                    summary["todos"] += 1
            _safe_rename(todos_root, h / "todos.migrated", summary)

        # timers/pending.json + timers/fired/*.json
        timers_root = h / "timers"
        if timers_root.exists() and timers_root.is_dir():
            pending = timers_root / "pending.json"
            if pending.exists():
                try:
                    arr = json.loads(pending.read_text(encoding="utf-8")) or []
                except json.JSONDecodeError:
                    arr = []
                for t in arr if isinstance(arr, list) else []:
                    if not isinstance(t, dict) or "id" not in t:
                        continue
                    conn.execute(
                        "INSERT OR IGNORE INTO timers(id, name, fire_at, recurring_seconds, message, paused, created) VALUES (?,?,?,?,?,?,?)",
                        (
                            t["id"],
                            t.get("name", ""),
                            t.get("fire_at", ""),
                            t.get("recurring_seconds"),
                            t.get("message", "") or "",
                            1 if t.get("paused") else 0,
                            t.get("created") or "",
                        ),
                    )
                    summary["timers_pending"] += 1
            fired_dir = timers_root / "fired"
            if fired_dir.exists():
                for f in sorted(fired_dir.glob("*.json")):
                    try:
                        t = json.loads(f.read_text(encoding="utf-8"))
                    except (json.JSONDecodeError, OSError):
                        continue
                    if not isinstance(t, dict) or "id" not in t:
                        continue
                    # Make a unique key — original id is reused across firings.
                    key = f"{t['id']}-{f.stem}"
                    conn.execute(
                        "INSERT OR IGNORE INTO fired_timers(id, name, fired_at, fire_at, message) VALUES (?,?,?,?,?)",
                        (
                            key,
                            t.get("name", ""),
                            t.get("fired_at", "") or "",
                            t.get("fire_at", "") or "",
                            t.get("message", "") or "",
                        ),
                    )
                    summary["timers_fired"] += 1
            _safe_rename(timers_root, h / "timers.migrated", summary)

        _set_schema_version(conn, _SCHEMA_VERSION)
    return summary


def _safe_rename(src: Path, dst: Path, summary: dict[str, Any]) -> None:
    if not src.exists():
        return
    if dst.exists():
        return
    try:
        src.rename(dst)
        summary["renamed"].append(str(dst))
    except OSError:
        pass


# ---------- FTS helpers ----------

_H1_RE = re.compile(r"^#\s+(.+)$", re.MULTILINE)


def _extract_title(body: str) -> str:
    m = _H1_RE.search(body or "")
    return m.group(1).strip() if m else ""


def reindex_note(name: str, project: str) -> None:
    """Re-index a single note in FTS. project may be '' meaning _global."""
    proj = project or "_global"
    p = notes_dir(project) / (name + ".md")
    conn = get_conn()
    with _lock:
        conn.execute(
            "DELETE FROM notes_fts WHERE kind='note' AND name=? AND project=?",
            (name, proj),
        )
        if not p.exists():
            return
        meta, body = parse_frontmatter(read_text(p))
        if meta.get("archived"):
            return
        title = _extract_title(body)
        tags = " ".join(meta.get("tags") or [])
        conn.execute(
            "INSERT INTO notes_fts(kind, name, project, title, content, tags) VALUES (?,?,?,?,?,?)",
            ("note", name, proj, title, body, tags),
        )


def delete_note_from_index(name: str, project: str) -> None:
    proj = project or "_global"
    conn = get_conn()
    with _lock:
        conn.execute(
            "DELETE FROM notes_fts WHERE kind='note' AND name=? AND project=?",
            (name, proj),
        )


def reindex_project_doc(name: str, project: str) -> None:
    p = project_doc_path(project, name)
    conn = get_conn()
    with _lock:
        conn.execute(
            "DELETE FROM notes_fts WHERE kind='project_doc' AND name=? AND project=?",
            (name, project),
        )
        if not p.exists():
            return
        meta, body = parse_frontmatter(read_text(p))
        title = _extract_title(body)
        conn.execute(
            "INSERT INTO notes_fts(kind, name, project, title, content, tags) VALUES (?,?,?,?,?,?)",
            ("project_doc", name, project, title, body, ""),
        )


def delete_project_doc_from_index(name: str, project: str) -> None:
    conn = get_conn()
    with _lock:
        conn.execute(
            "DELETE FROM notes_fts WHERE kind='project_doc' AND name=? AND project=?",
            (name, project),
        )


def reindex_all_notes() -> dict[str, int]:
    """Full rebuild from disk. Cheap and avoids drift."""
    conn = get_conn()
    h = home()
    notes_root = h / "notes"
    projects_root = h / "projects"
    counts = {"notes": 0, "project_docs": 0}
    with _lock:
        conn.execute("DELETE FROM notes_fts")
        # notes
        if notes_root.exists():
            for scope_dir in sorted(notes_root.iterdir()):
                if not scope_dir.is_dir():
                    continue
                proj = scope_dir.name
                for f in sorted(scope_dir.glob("*.md")):
                    try:
                        meta, body = parse_frontmatter(read_text(f))
                    except OSError:
                        continue
                    if meta.get("archived"):
                        continue
                    title = _extract_title(body)
                    tags = " ".join(meta.get("tags") or [])
                    conn.execute(
                        "INSERT INTO notes_fts(kind, name, project, title, content, tags) VALUES (?,?,?,?,?,?)",
                        ("note", f.stem, proj, title, body, tags),
                    )
                    counts["notes"] += 1
        # project docs
        if projects_root.exists():
            for proj_dir in sorted(projects_root.iterdir()):
                if not proj_dir.is_dir():
                    continue
                docs = proj_dir / "docs"
                if not docs.exists():
                    continue
                for f in sorted(docs.glob("*.md")):
                    try:
                        meta, body = parse_frontmatter(read_text(f))
                    except OSError:
                        continue
                    title = _extract_title(body)
                    conn.execute(
                        "INSERT INTO notes_fts(kind, name, project, title, content, tags) VALUES (?,?,?,?,?,?)",
                        ("project_doc", f.stem, proj_dir.name, title, body, ""),
                    )
                    counts["project_docs"] += 1
    return counts


def fts_search(query: str, project: str, limit: int, kinds: list[str]) -> list[dict[str, Any]]:
    conn = get_conn()
    if not kinds:
        kinds = ["note", "project_doc"]
    placeholders = ",".join("?" for _ in kinds)
    params: list[Any] = list(kinds)
    where_extra = ""
    if project:
        where_extra = " AND project = ?"
        params.append(project)
    sql = (
        "SELECT kind, name, project, title, "
        "snippet(notes_fts, 4, '[', ']', '...', 12) AS snippet "
        f"FROM notes_fts WHERE kind IN ({placeholders}){where_extra} "
        "AND notes_fts MATCH ? ORDER BY rank LIMIT ?"
    )
    params.append(query)
    params.append(max(1, int(limit)))
    rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]
