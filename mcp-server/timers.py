"""Timers tools — durable scheduled wake-ups with a background watcher thread (SQLite-backed)."""
from __future__ import annotations

import threading
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import db
from storage import err, now_iso, ok


def _parse_iso(s: str) -> datetime | None:
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


def _row_to_dict(row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "name": row["name"],
        "fire_at": row["fire_at"],
        "recurring_seconds": row["recurring_seconds"],
        "message": row["message"],
        "paused": bool(row["paused"]),
        "created": row["created"],
    }


def _check_once() -> None:
    """Move due timers from `timers` to `fired_timers`; re-arm recurring ones."""
    conn = db.get_conn()
    now = datetime.now(timezone.utc)
    with db.write_lock():
        rows = conn.execute("SELECT * FROM timers WHERE paused = 0").fetchall()
        for r in rows:
            fire_at = _parse_iso(r["fire_at"])
            if fire_at is None:
                conn.execute("DELETE FROM timers WHERE id = ?", (r["id"],))
                continue
            if fire_at > now:
                continue
            fired_key = f"{r['id']}-{int(now.timestamp() * 1000)}"
            conn.execute(
                "INSERT OR IGNORE INTO fired_timers(id, name, fired_at, fire_at, message) VALUES (?,?,?,?,?)",
                (fired_key, r["name"], now_iso(), r["fire_at"], r["message"]),
            )
            rec = r["recurring_seconds"] or 0
            if rec and rec > 0:
                next_fire = fire_at
                while next_fire <= now:
                    next_fire = next_fire + timedelta(seconds=rec)
                conn.execute(
                    "UPDATE timers SET fire_at = ? WHERE id = ?",
                    (next_fire.isoformat(), r["id"]),
                )
            else:
                conn.execute("DELETE FROM timers WHERE id = ?", (r["id"],))


_DONE_STATUSES = {"done", "cancelled"}


def _check_idle_watches() -> None:
    """Fire idle watches whose todo conditions are satisfied."""
    conn = db.get_conn()
    with db.write_lock():
        watches = conn.execute(
            "SELECT * FROM idle_watches WHERE fired = 0"
        ).fetchall()
        for w in watches:
            todo_ids = db.unpack_list(w["todo_ids"])
            if not todo_ids:
                continue
            mode = w["mode"]
            statuses = []
            for tid in todo_ids:
                row = conn.execute("SELECT status FROM todos WHERE id = ?", (tid,)).fetchone()
                statuses.append(row["status"] if row else "done")

            if mode == "all":
                triggered = all(s in _DONE_STATUSES for s in statuses)
            else:
                triggered = any(s in _DONE_STATUSES for s in statuses)

            if triggered:
                fired_key = f"idle-{w['id']}-{int(datetime.now(timezone.utc).timestamp() * 1000)}"
                conn.execute(
                    "INSERT OR IGNORE INTO fired_timers(id, name, fired_at, fire_at, message) VALUES (?,?,?,?,?)",
                    (fired_key, w["name"], now_iso(), now_iso(), w["message"]),
                )
                conn.execute("UPDATE idle_watches SET fired = 1 WHERE id = ?", (w["id"],))


def _watcher_loop(stop_event: threading.Event) -> None:
    while not stop_event.is_set():
        try:
            _check_once()
            _check_idle_watches()
        except Exception:
            pass
        stop_event.wait(5.0)


_watcher_stop: threading.Event | None = None
_watcher_thread: threading.Thread | None = None


def start_watcher() -> None:
    global _watcher_stop, _watcher_thread
    if _watcher_thread and _watcher_thread.is_alive():
        return
    _watcher_stop = threading.Event()
    _watcher_thread = threading.Thread(target=_watcher_loop, args=(_watcher_stop,), daemon=True, name="timer-watcher")
    _watcher_thread.start()


def register(server) -> int:

    @server.tool()
    def timer_set(name: str, fire_in_seconds: int = 0, fire_at: str = "", recurring_seconds: int = 0, message: str = "") -> str:
        """Schedule a timer. Provide either fire_in_seconds or an ISO8601 fire_at."""
        if fire_in_seconds <= 0 and not fire_at:
            return err("missing_arg", "provide fire_in_seconds > 0 or fire_at")
        if fire_in_seconds > 0:
            dt = datetime.now(timezone.utc) + timedelta(seconds=fire_in_seconds)
        else:
            parsed = _parse_iso(fire_at)
            if parsed is None:
                return err("invalid_arg", f"could not parse fire_at: {fire_at}")
            dt = parsed
        tid = uuid.uuid4().hex
        rec = recurring_seconds if recurring_seconds > 0 else None
        with db.write_lock():
            db.get_conn().execute(
                "INSERT INTO timers(id, name, fire_at, recurring_seconds, message, paused, created) VALUES (?,?,?,?,?,?,?)",
                (tid, name, dt.isoformat(), rec, message, 0, now_iso()),
            )
        row = db.get_conn().execute("SELECT * FROM timers WHERE id = ?", (tid,)).fetchone()
        return ok(_row_to_dict(row))

    @server.tool()
    def timer_list(include_paused: bool = True) -> str:
        """List pending timers."""
        if include_paused:
            rows = db.get_conn().execute("SELECT * FROM timers ORDER BY fire_at").fetchall()
        else:
            rows = db.get_conn().execute("SELECT * FROM timers WHERE paused = 0 ORDER BY fire_at").fetchall()
        items = [_row_to_dict(r) for r in rows]
        return ok({"count": len(items), "items": items})

    @server.tool()
    def timer_cancel(id: str) -> str:
        """Cancel a pending timer."""
        with db.write_lock():
            cur = db.get_conn().execute("DELETE FROM timers WHERE id = ?", (id,))
            if cur.rowcount == 0:
                return err("not_found", f"Timer '{id}' not found.")
        return ok({"cancelled": id})

    @server.tool()
    def timer_pause(id: str) -> str:
        """Pause a pending timer."""
        return _set_paused(id, True)

    @server.tool()
    def timer_resume(id: str) -> str:
        """Resume a paused timer."""
        return _set_paused(id, False)

    @server.tool()
    def timer_fired(ack: bool = False) -> str:
        """List timers that have fired. If ack=true, also clear them."""
        rows = db.get_conn().execute("SELECT * FROM fired_timers ORDER BY fired_at").fetchall()
        items = [dict(r) for r in rows]
        if ack:
            with db.write_lock():
                db.get_conn().execute("DELETE FROM fired_timers")
        return ok({"count": len(items), "items": items})

    @server.tool()
    def timer_ack(id: str) -> str:
        """Clear all fired events for a specific timer id."""
        with db.write_lock():
            # fired keys are stored as `<id>-<ms>` or legacy bare id
            cur = db.get_conn().execute(
                "DELETE FROM fired_timers WHERE id = ? OR id LIKE ?",
                (id, f"{id}-%"),
            )
            removed = cur.rowcount or 0
        if removed == 0:
            return err("not_found", f"No fired events for timer '{id}'.")
        return ok({"acked": id, "removed": removed})

    # ── Idle-based triggers ────────────────────────────────────────────────

    @server.tool()
    def fire_when_idle_all(name: str, todo_ids: str, message: str = "") -> str:
        """Register a watch that fires once ALL listed todos reach done or cancelled status.
        todo_ids: comma-separated todo ids to watch.
        Fires into the same fired_timers table as time-based timers; use timer_fired to poll.
        """
        return _create_idle_watch(name, "all", todo_ids, message)

    @server.tool()
    def fire_when_idle_any(name: str, todo_ids: str, message: str = "") -> str:
        """Register a watch that fires once ANY of the listed todos reaches done or cancelled status.
        todo_ids: comma-separated todo ids to watch.
        Fires into the same fired_timers table as time-based timers; use timer_fired to poll.
        """
        return _create_idle_watch(name, "any", todo_ids, message)

    @server.tool()
    def idle_watch_list() -> str:
        """List all idle watches (both pending and already fired)."""
        rows = db.get_conn().execute("SELECT * FROM idle_watches ORDER BY created").fetchall()
        items = [_watch_row_to_dict(r) for r in rows]
        return ok({"count": len(items), "items": items})

    @server.tool()
    def idle_watch_cancel(id: str) -> str:
        """Cancel (delete) an idle watch that hasn't fired yet."""
        row = db.get_conn().execute("SELECT 1 FROM idle_watches WHERE id = ?", (id,)).fetchone()
        if not row:
            return err("not_found", f"Idle watch '{id}' not found.")
        with db.write_lock():
            db.get_conn().execute("DELETE FROM idle_watches WHERE id = ?", (id,))
        return ok({"cancelled": id})

    return 11


def _create_idle_watch(name: str, mode: str, todo_ids_str: str, message: str) -> str:
    if not name.strip():
        return err("missing_arg", "name required")
    if not todo_ids_str.strip():
        return err("missing_arg", "todo_ids required")
    id_list = [i.strip() for i in todo_ids_str.split(",") if i.strip()]
    if not id_list:
        return err("missing_arg", "todo_ids must contain at least one id")
    wid = uuid.uuid4().hex
    with db.write_lock():
        db.get_conn().execute(
            "INSERT INTO idle_watches(id, name, mode, todo_ids, message, fired, created) VALUES (?,?,?,?,?,?,?)",
            (wid, name, mode, db.pack_list(id_list), message, 0, now_iso()),
        )
    row = db.get_conn().execute("SELECT * FROM idle_watches WHERE id = ?", (wid,)).fetchone()
    return ok(_watch_row_to_dict(row))


def _watch_row_to_dict(row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "name": row["name"],
        "mode": row["mode"],
        "todo_ids": db.unpack_list(row["todo_ids"]),
        "message": row["message"],
        "fired": bool(row["fired"]),
        "created": row["created"],
    }


def _set_paused(tid: str, paused: bool) -> str:
    with db.write_lock():
        cur = db.get_conn().execute(
            "UPDATE timers SET paused = ? WHERE id = ?",
            (1 if paused else 0, tid),
        )
        if cur.rowcount == 0:
            return err("not_found", f"Timer '{tid}' not found.")
    return ok({"id": tid, "paused": paused})
