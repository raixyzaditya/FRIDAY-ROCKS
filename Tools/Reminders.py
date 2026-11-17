"""
Reminders and timers that survive restarts.

Stored in friday_reminders.json at the project root (gitignored). A background thread started
by start_scheduler() checks every second and calls on_due(text) when something is due, so
Friday speaks up even when nobody is talking to her.
"""

import json
import os
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

REMINDER_FILE = Path(__file__).resolve().parent.parent / "friday_reminders.json"
MAX_DAYS = 366
MISSED_AFTER = timedelta(minutes=5)  # due this long ago (Friday was off) counts as "missed"

_lock = threading.RLock()
_scheduler = None
_stop = threading.Event()


def _load() -> list:
    try:
        data = json.loads(REMINDER_FILE.read_text(encoding="utf-8"))
        return [r for r in data if isinstance(r, dict) and "due" in r and "message" in r] if isinstance(data, list) else []
    except (OSError, ValueError):
        return []


def _save(items: list):
    tmp = REMINDER_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(items, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, REMINDER_FILE)


def _parse_at(at: str, now: datetime):
    """'2026-11-18 09:30', '18:30', '6:30 pm' -> datetime. A bare time that has passed means tomorrow."""
    at = at.strip()
    try:
        return datetime.fromisoformat(at)
    except ValueError:
        pass
    for fmt in ("%H:%M", "%H:%M:%S", "%I:%M %p", "%I:%M%p", "%I %p", "%I%p"):
        try:
            t = datetime.strptime(at.upper(), fmt).time()
        except ValueError:
            continue
        due = datetime.combine(now.date(), t)
        return due if due > now else due + timedelta(days=1)
    return None


def _when(due: datetime, now: datetime) -> str:
    clock = due.strftime("%I:%M %p").lstrip("0")
    if due.date() == now.date():
        return f"at {clock}"
    if due.date() == (now + timedelta(days=1)).date():
        return f"tomorrow at {clock}"
    return f"on {due.strftime('%A %d %B')} at {clock}"


def set_reminder(message: str, minutes=None, at: str = None) -> str:
    message = " ".join((message or "").split())
    if not message:
        return "Sorry boss, what should I remind you about?"
    now = datetime.now()
    try:
        if minutes not in (None, "", 0, "0"):
            minutes = float(minutes)
            if minutes <= 0:
                return "Sorry boss, the time has to be in the future."
            due = now + timedelta(minutes=minutes)
        elif at:
            due = _parse_at(str(at), now)
            if due is None:
                return f"Sorry boss, I couldn't understand the time '{at}'."
        else:
            return "Sorry boss, when should I remind you? Give me a time or a number of minutes."
    except (TypeError, ValueError):
        return "Sorry boss, I couldn't understand that time."

    if due <= now:
        return "Sorry boss, that time has already passed."
    if due - now > timedelta(days=MAX_DAYS):
        return "Sorry boss, I can only set reminders up to a year ahead."

    with _lock:
        items = _load()
        items.append({"id": int(time.time() * 1000), "message": message, "due": due.isoformat(timespec="seconds")})
        _save(items)
    delta = due - now
    if delta < timedelta(hours=1):
        mins = max(1, round(delta.total_seconds() / 60))
        return f"Okay boss, I'll remind you in {mins} minute{'s' if mins != 1 else ''}: {message}."
    return f"Okay boss, I'll remind you {_when(due, now)}: {message}."


def list_reminders() -> str:
    with _lock:
        items = sorted(_load(), key=lambda r: r["due"])
    if not items:
        return "You have no reminders set."
    now = datetime.now()
    lines = [f"You have {len(items)} reminder{'s' if len(items) != 1 else ''}:"]
    for r in items:
        lines.append(f"{r['message']}, {_when(datetime.fromisoformat(r['due']), now)}.")
    return " ".join(lines)


def cancel_reminder(keyword: str) -> str:
    words = (keyword or "").lower().split()
    if not words:
        return "Sorry boss, which reminder should I cancel?"
    with _lock:
        items = _load()
        kept = [r for r in items if not all(w in r["message"].lower() for w in words)]
        removed = len(items) - len(kept)
        if removed:
            _save(kept)
    if not removed:
        return f"I couldn't find a reminder about {keyword}."
    return f"Cancelled {removed} reminder{'s' if removed != 1 else ''} about {keyword}."


def check_due(now: datetime = None) -> list:
    """Remove and return the spoken text of every reminder that is due."""
    now = now or datetime.now()
    due_texts = []
    with _lock:
        items = _load()
        remaining = []
        for r in sorted(items, key=lambda r: r["due"]):
            when = datetime.fromisoformat(r["due"])
            if when > now:
                remaining.append(r)
            elif now - when > MISSED_AFTER:
                due_texts.append(f"You missed a reminder from {_when(when, now)}: {r['message']}.")
            else:
                due_texts.append(f"Reminder: {r['message']}.")
        if len(remaining) != len(items):
            _save(remaining)
    return due_texts


def start_scheduler(on_due, interval: float = 1.0):
    """Start (once) the background thread that calls on_due(text) for each due reminder."""
    global _scheduler
    with _lock:
        if _scheduler is not None:
            return
        _stop.clear()

        def loop():
            while not _stop.is_set():
                try:
                    for text in check_due():
                        on_due(text)
                except Exception as e:  # a bad reminder must never kill the scheduler
                    print(f"[Reminders] {e}")
                _stop.wait(interval)

        _scheduler = threading.Thread(target=loop, daemon=True, name="reminders")
        _scheduler.start()


def stop_scheduler():
    global _scheduler
    _stop.set()
    with _lock:
        thread, _scheduler = _scheduler, None
    if thread:
        thread.join(timeout=2)
