"""
Keyboard and scroll control: typing into the active window and pressing allowed keys.

Safety design (a voice assistant that can press keys is powerful, so it is fenced in):
  * Every type_text / press_keys call needs a spoken yes first, and reads back what it will do.
  * Only an allowlist of keys and shortcuts works. No Alt+F4, Win+R, Ctrl+Alt+Del, Ctrl+Shift+Esc...
  * Text is limited to 500 characters. There is no mouse clicking at all.
  * The system prompt tells Friday to act only on the user's own request, never because text on
    the screen, in an email or on a web page tells her to.
Uses Windows SendInput via ctypes, so no extra packages are needed.
"""

import ctypes
import re
import time

from .PCControl import _confirm

MAX_TYPE_CHARS = 500
INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
WHEEL_DELTA = 120

VK_KEYS = {
    "enter": 0x0D, "tab": 0x09, "escape": 0x1B, "backspace": 0x08, "delete": 0x2E, "space": 0x20,
    "up": 0x26, "down": 0x28, "left": 0x25, "right": 0x27,
    "pageup": 0x21, "pagedown": 0x22, "home": 0x24, "end": 0x23, "f5": 0x74,
}
VK_MODS = {"ctrl": 0x11, "shift": 0x10, "alt": 0x12}
_LETTERS = {ch: ord(ch.upper()) for ch in "abcdefghijklmnopqrstuvwxyz"}

# Everything not on this list is refused.
ALLOWED_COMBOS = (
    {"ctrl+" + k for k in "acvxzysftwnpr"}
    | {"ctrl+tab", "ctrl+shift+tab", "alt+tab", "alt+left", "alt+right", "ctrl+shift+t"}
)
ALLOWED_SINGLE = set(VK_KEYS)


def normalize_keys(keys: str) -> str:
    k = (keys or "").lower().strip()
    k = k.replace("control", "ctrl").replace("esc", "escape").replace("escapeape", "escape")
    k = re.sub(r"\s*\+\s*|\s+plus\s+|\s+", "+", k)
    return k.replace("pgup", "pageup").replace("pgdn", "pagedown").replace("return", "enter")


def key_codes(normalized: str):
    """-> list of virtual-key codes (modifiers first), or None if the keys are not allowed."""
    if normalized in ALLOWED_SINGLE:
        return [VK_KEYS[normalized]]
    if normalized in ALLOWED_COMBOS:
        parts = normalized.split("+")
        codes = [VK_MODS[p] for p in parts[:-1]]
        last = parts[-1]
        codes.append(VK_KEYS.get(last) or _LETTERS[last])
        return codes
    return None


# ----------------------------------------------------------- low-level input

class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", ctypes.c_ushort), ("wScan", ctypes.c_ushort), ("dwFlags", ctypes.c_ulong),
                ("time", ctypes.c_ulong), ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))]


class _MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", ctypes.c_long), ("dy", ctypes.c_long), ("mouseData", ctypes.c_ulong),
                ("dwFlags", ctypes.c_ulong), ("time", ctypes.c_ulong),
                ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))]


class _HARDWAREINPUT(ctypes.Structure):
    _fields_ = [("uMsg", ctypes.c_ulong), ("wParamL", ctypes.c_ushort), ("wParamH", ctypes.c_ushort)]


class _INPUT_UNION(ctypes.Union):
    _fields_ = [("ki", _KEYBDINPUT), ("mi", _MOUSEINPUT), ("hi", _HARDWAREINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", ctypes.c_ulong), ("ii", _INPUT_UNION)]


def text_events(text: str) -> list:
    """Text -> [(virtual_key, scan_code, flags)]. Unicode characters (even emoji) are sent as UTF-16 units."""
    events = []
    for ch in text:
        if ch == "\n":
            events += [(VK_KEYS["enter"], 0, 0), (VK_KEYS["enter"], 0, KEYEVENTF_KEYUP)]
        elif ch == "\t":
            events += [(VK_KEYS["tab"], 0, 0), (VK_KEYS["tab"], 0, KEYEVENTF_KEYUP)]
        elif ch == "\r":
            continue
        else:
            data = ch.encode("utf-16-le")
            for i in range(0, len(data), 2):
                unit = int.from_bytes(data[i:i + 2], "little")
                events += [(0, unit, KEYEVENTF_UNICODE), (0, unit, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP)]
    return events


def combo_events(codes: list) -> list:
    """Hold the modifiers, tap the key, release in reverse order."""
    return [(c, 0, 0) for c in codes] + [(c, 0, KEYEVENTF_KEYUP) for c in reversed(codes)]


def _send(events: list):
    arr = (INPUT * len(events))()
    for i, (vk, scan, flags) in enumerate(events):
        arr[i].type = INPUT_KEYBOARD
        arr[i].ii.ki = _KEYBDINPUT(vk, scan, flags, 0, None)
    sent = ctypes.windll.user32.SendInput(len(events), arr, ctypes.sizeof(INPUT))
    if sent != len(events):
        raise OSError(f"Windows accepted only {sent} of {len(events)} key events (the window may be elevated)")


def _wheel(delta: int):
    ctypes.windll.user32.mouse_event(0x0800, 0, 0, delta, 0)  # MOUSEEVENTF_WHEEL


# ------------------------------------------------------------------- tools

def type_text(text: str) -> str:
    text = text or ""
    if not text.strip():
        return "Sorry boss, what should I type?"
    if len(text) > MAX_TYPE_CHARS:
        return f"Sorry boss, that's too long to type. I'll only type up to {MAX_TYPE_CHARS} characters."
    preview = " ".join(text.split())
    preview = preview if len(preview) <= 60 else preview[:60] + "..."
    if not _confirm(f"I'll type '{preview}' into whatever window is active. Say yes to confirm."):
        return "Okay boss, I didn't type anything."
    try:
        time.sleep(0.3)
        _send(text_events(text))
    except Exception as e:
        print(f"[type_text] {e}")
        return "Sorry boss, I couldn't type that."
    return "Typed it."


def press_keys(keys: str) -> str:
    normalized = normalize_keys(keys)
    codes = key_codes(normalized)
    if codes is None:
        return f"Sorry boss, I'm not allowed to press '{keys}'. I can do things like enter, tab, ctrl+c, ctrl+v or alt+tab."
    if not _confirm(f"I'll press {normalized.replace('+', ' plus ')} in the active window. Say yes to confirm."):
        return "Okay boss, I didn't press anything."
    try:
        time.sleep(0.3)
        _send(combo_events(codes))
    except Exception as e:
        print(f"[press_keys] {e}")
        return "Sorry boss, I couldn't press those keys."
    return f"Pressed {normalized}."


def scroll(direction: str, amount: int = 3) -> str:
    direction = (direction or "").lower().strip()
    if direction not in ("up", "down"):
        return "Sorry boss, scroll up or down?"
    try:
        amount = max(1, min(int(float(amount)), 20))
    except (TypeError, ValueError):
        amount = 3
    try:
        _wheel(WHEEL_DELTA * amount * (1 if direction == "up" else -1))
    except Exception as e:
        print(f"[scroll] {e}")
        return "Sorry boss, I couldn't scroll."
    return f"Scrolled {direction}."
