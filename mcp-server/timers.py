"""Timers tools — durable scheduled wake-ups with a background watcher thread."""
from __future__ import annotations

import json
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from storage import (
    err,
    ensure_dirs,
    file_lock,
    load_json,
    now_iso,
    ok,
    save_json,
    timers_fired_dir,
    timers_pending_path,
)


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


def _load_pending() -> list[dict[str, Any]]:
    return load_json(timers_pending_path(), []) or []


def _save_pending(pending: list[dict[str, Any]]) -> None:
    save_json(timers_pending_path(), pending)


def _check_once() -> None:
    """Inspect pending; move fired ones into fired/, reschedule recurring."""
    pending_path = timers_pending_path()
    with file_lock(pending_path):
        pending = _load_pending()
        now = datetime.now(timezone.utc)
        changed = False
        new_pending: list[dict[str, Any]] = []
        for t in pending:
            if t.get("paused"):
                new_pending.append(t)
                continue
            fire_at = _parse_iso(t.get("fire_at", ""))
            if fire_at is None:
                # malformed — drop
                changed = True
                continue
            if fire_at <= now:
                # fire
                fired = dict(t)
                fired["fired_at"] = now_iso()
                fired_file = timers_fired_dir() / f"{t['id']}-{int(now.timestamp() * 1000)}.json"
                save_json(fired_file, fired)
                changed = True
                rec = t.get("recurring_seconds") or 0
                if rec and rec > 0:
                    # re-arm
                    next_fire = fire_at
                    while next_fire <= now:
                        next_fire = next_fire + timedelta(seconds=rec)
                    t["fire_at"] = next_fire.isoformat()
                    new_pending.append(t)
                # else: drop (one-shot)
            else:
                new_pending.append(t)
        if changed:
            _save_pending(new_pending)


def _watcher_loop(stop_event: threading.Event) -> None:
    while not stop_event.is_set():
        try:
            _check_once()
        except Exception:
            pass
        stop_event.wait(5.0)


_watcher_stop: threading.Event | None = None
_watcher_thread: threading.Thread | None = None


def start_watcher() -> None:
    global _watcher_stop, _watcher_thread
    if _watcher_thread and _watcher_thread.is_alive():
        return
    ensure_dirs()
    _watcher_stop = threading.Event()
    _watcher_thread = threading.Thread(target=_watcher_loop, args=(_watcher_stop,), daemon=True, name="timer-watcher")
    _watcher_thread.start()


def register(server) -> int:
    ensure_dirs()

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
        timer = {
            "id": tid,
            "name": name,
            "fire_at": dt.isoformat(),
            "recurring_seconds": recurring_seconds if recurring_seconds > 0 else None,
            "message": message,
            "paused": False,
            "created": now_iso(),
        }
        with file_lock(timers_pending_path()):
            pending = _load_pending()
            pending.append(timer)
            _save_pending(pending)
        return ok(timer)

    @server.tool()
    def timer_list(include_paused: bool = True) -> str:
        """List pending timers."""
        pending = _load_pending()
        if not include_paused:
            pending = [t for t in pending if not t.get("paused")]
        return ok({"count": len(pending), "items": pending})

    @server.tool()
    def timer_cancel(id: str) -> str:
        """Cancel a pending timer."""
        with file_lock(timers_pending_path()):
            pending = _load_pending()
            new = [t for t in pending if t.get("id") != id]
            if len(new) == len(pending):
                return err("not_found", f"Timer '{id}' not found.")
            _save_pending(new)
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
        d = timers_fired_dir()
        d.mkdir(parents=True, exist_ok=True)
        items = []
        for p in sorted(d.glob("*.json")):
            data = load_json(p, None)
            if data:
                items.append(data)
            if ack:
                try:
                    p.unlink()
                except OSError:
                    pass
        return ok({"count": len(items), "items": items})

    @server.tool()
    def timer_ack(id: str) -> str:
        """Clear all fired events for a specific timer id."""
        d = timers_fired_dir()
        d.mkdir(parents=True, exist_ok=True)
        removed = 0
        for p in d.glob(f"{id}-*.json"):
            try:
                p.unlink()
                removed += 1
            except OSError:
                pass
        # also try unprefixed match
        legacy = d / f"{id}.json"
        if legacy.exists():
            try:
                legacy.unlink()
                removed += 1
            except OSError:
                pass
        if removed == 0:
            return err("not_found", f"No fired events for timer '{id}'.")
        return ok({"acked": id, "removed": removed})

    return 7


def _set_paused(tid: str, paused: bool) -> str:
    with file_lock(timers_pending_path()):
        pending = _load_pending()
        found = False
        for t in pending:
            if t.get("id") == tid:
                t["paused"] = paused
                found = True
                break
        if not found:
            return err("not_found", f"Timer '{tid}' not found.")
        _save_pending(pending)
    return ok({"id": tid, "paused": paused})
