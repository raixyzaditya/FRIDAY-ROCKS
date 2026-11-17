"""
Long-term memory: short facts about the user that survive restarts.

Stored in friday_memory.json at the project root (gitignored, it's personal).
Brain.py injects facts_as_prompt() into the system prompt on every question.
"""

import json
import os
import threading
from pathlib import Path

MEMORY_FILE = Path(__file__).resolve().parent.parent / "friday_memory.json"
MAX_FACTS = 50
MAX_FACT_LENGTH = 200

_lock = threading.Lock()


def _load() -> list:
    try:
        data = json.loads(MEMORY_FILE.read_text(encoding="utf-8"))
        return [f for f in data if isinstance(f, str)] if isinstance(data, list) else []
    except (OSError, ValueError):
        return []


def _save(facts: list):
    tmp = MEMORY_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(facts, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, MEMORY_FILE)  # atomic, so a crash can't leave a half-written file


def remember(fact: str) -> str:
    fact = " ".join((fact or "").split())[:MAX_FACT_LENGTH]
    if not fact:
        return "Sorry boss, what should I remember?"
    with _lock:
        facts = _load()
        if any(f.lower() == fact.lower() for f in facts):
            return "I already know that."
        facts.append(fact)
        _save(facts[-MAX_FACTS:])  # oldest facts fall off first
    return f"Got it, I'll remember that: {fact}"


def forget(topic: str) -> str:
    words = (topic or "").lower().split()
    if not words:
        return "Sorry boss, what should I forget?"
    with _lock:
        facts = _load()
        kept = [f for f in facts if not all(w in f.lower() for w in words)]
        removed = len(facts) - len(kept)
        if removed:
            _save(kept)
    if not removed:
        return f"I don't have anything stored about {topic}."
    return f"Done, I forgot {removed} thing{'s' if removed > 1 else ''} about {topic}."


def facts_as_prompt() -> str:
    """Text appended to the system prompt, or '' when nothing is stored."""
    facts = _load()
    if not facts:
        return ""
    return "\n\nThings you remember about the user (long-term memory):\n" + "\n".join(f"- {f}" for f in facts)
