"""Filesystem layout, atomic IO, YAML frontmatter, and shared helpers.

Notes and project docs are canonical on disk (markdown + YAML frontmatter).
Todos, timers, and the project registry live in SQLite (see db.py).
"""
from __future__ import annotations

import fcntl
import json
import os
import re
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator


# ---------- paths ----------

def home() -> Path:
    """Root directory for all agent toolkit state."""
    p = os.environ.get("AGENT_TOOLKIT_HOME")
    if p:
        return Path(p).expanduser()
    return Path.home() / ".agent-toolkit"


def ensure_dirs() -> None:
    h = home()
    (h / "notes" / "_global").mkdir(parents=True, exist_ok=True)
    (h / "projects").mkdir(parents=True, exist_ok=True)


def notes_dir(project: str) -> Path:
    return home() / "notes" / (project or "_global")


def project_docs_dir(project: str) -> Path:
    return home() / "projects" / project / "docs"


def project_doc_path(project: str, name: str) -> Path:
    return project_docs_dir(project) / (slug(name) + ".md")


# ---------- time ----------

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------- atomic io ----------

def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".tmp-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


@contextmanager
def file_lock(path: Path) -> Iterator[None]:
    """Advisory exclusive lock on a sibling .lock file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_suffix(path.suffix + ".lock")
    with open(lock_path, "a+") as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)


# ---------- slug ----------

_SLUG_RE = re.compile(r"[^a-zA-Z0-9_.-]+")


def slug(name: str) -> str:
    s = _SLUG_RE.sub("-", name.strip())
    s = s.strip("-.")
    return s or "untitled"


# ---------- tag parsing ----------

def parse_tag_list(s: str) -> list[str]:
    if not s:
        return []
    return [t.strip() for t in s.split(",") if t.strip()]


# ---------- yaml frontmatter (mini) ----------
# Supports: scalars (str, int, float, bool, null) and flat list-of-strings.

_FM_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", re.DOTALL)


def _parse_scalar(v: str) -> Any:
    v = v.strip()
    if v == "" or v.lower() == "null" or v == "~":
        return None
    if v.lower() == "true":
        return True
    if v.lower() == "false":
        return False
    if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
        return v[1:-1]
    try:
        if "." in v:
            return float(v)
        return int(v)
    except ValueError:
        return v


def _parse_inline_list(v: str) -> list[str]:
    v = v.strip()
    if not (v.startswith("[") and v.endswith("]")):
        return []
    inner = v[1:-1].strip()
    if not inner:
        return []
    out = []
    for item in inner.split(","):
        item = item.strip()
        if (item.startswith('"') and item.endswith('"')) or (item.startswith("'") and item.endswith("'")):
            item = item[1:-1]
        if item:
            out.append(item)
    return out


def parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """Return (meta, body). If no frontmatter, meta is {}."""
    m = _FM_RE.match(text)
    if not m:
        return {}, text
    raw, body = m.group(1), m.group(2)
    meta: dict[str, Any] = {}
    lines = raw.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip() or line.lstrip().startswith("#"):
            i += 1
            continue
        if ":" not in line:
            i += 1
            continue
        key, _, val = line.partition(":")
        key = key.strip()
        val = val.strip()
        if val == "":
            items: list[str] = []
            j = i + 1
            while j < len(lines) and lines[j].lstrip().startswith("- "):
                v = lines[j].lstrip()[2:].strip()
                if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
                    v = v[1:-1]
                items.append(v)
                j += 1
            meta[key] = items
            i = j
            continue
        if val.startswith("["):
            meta[key] = _parse_inline_list(val)
        else:
            meta[key] = _parse_scalar(val)
        i += 1
    return meta, body


def _emit_scalar(v: Any) -> str:
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    s = str(v)
    if any(c in s for c in ":#[]{}\"'") or s.strip() != s:
        return '"' + s.replace('"', '\\"') + '"'
    return s


def render_frontmatter(meta: dict[str, Any], body: str) -> str:
    lines = ["---"]
    for k, v in meta.items():
        if isinstance(v, list):
            if not v:
                lines.append(f"{k}: []")
            else:
                inner = ", ".join(_emit_scalar(x) for x in v)
                lines.append(f"{k}: [{inner}]")
        else:
            lines.append(f"{k}: {_emit_scalar(v)}")
    lines.append("---")
    if not body.startswith("\n"):
        lines.append("")
    return "\n".join(lines) + body


# ---------- errors ----------

def err(code: str, message: str, **extra: Any) -> str:
    payload = {"error": True, "code": code, "message": message}
    payload.update(extra)
    return json.dumps(payload)


def ok(data: Any) -> str:
    return json.dumps(data, indent=2, sort_keys=False, default=str)


# ---------- project validation (DB-backed) ----------

def validate_project(project: str) -> tuple[bool, str | None]:
    """Return (ok, error_json). Empty string project means _global."""
    if not project:
        return True, None
    if project == "_global":
        return False, err("reserved_name", "'_global' is reserved.")
    # Lazy import: db imports storage for paths.
    import db
    conn = db.get_conn()
    row = conn.execute("SELECT 1 FROM projects WHERE name = ?", (project,)).fetchone()
    if row is None:
        return False, err("unknown_project", f"Project '{project}' is not registered.")
    return True, None
