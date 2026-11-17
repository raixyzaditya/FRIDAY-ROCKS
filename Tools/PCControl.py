import os
import sys
import time
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'Voice'))

HOME = Path.home()
SEARCH_ROOTS = [HOME / "Desktop", HOME / "Documents", HOME / "Downloads"]
SCREENSHOT_DIR = HOME / "Pictures" / "FRIDAY_Screenshots"
SKIP_DIRS = {"node_modules", ".git", "__pycache__", "venv", ".venv", "AppData"}
MAX_RESULTS = 5
SEARCH_TIMEOUT = 8  # seconds

# Allowlist: spoken name -> command Windows `start` understands.
# Only these (plus anything found on PATH) can be launched.
APP_ALIASES = {
    "notepad": "notepad",
    "calculator": "calc", "calc": "calc",
    "paint": "mspaint",
    "file explorer": "explorer", "explorer": "explorer",
    "command prompt": "cmd", "cmd": "cmd",
    "terminal": "wt",
    "chrome": "chrome", "google chrome": "chrome",
    "edge": "msedge", "microsoft edge": "msedge",
    "firefox": "firefox",
    "vs code": "code", "vscode": "code", "visual studio code": "code",
    "word": "winword", "excel": "excel", "powerpoint": "powerpnt",
    "spotify": "spotify",
    "task manager": "taskmgr",
    "settings": "ms-settings:",
}

YES_WORDS = ("yes", "yeah", "yep", "confirm", "go ahead", "do it", "sure", "proceed")


# ---------------------------------------------------------------- helpers

def _resolve(path_str: str) -> Path:
    """Resolve a path and refuse anything outside the user's home folder."""
    path = Path(os.path.expanduser(path_str.strip()))
    if not path.is_absolute():
        path = HOME / path
    path = path.resolve()
    if path != HOME and HOME not in path.parents:
        raise ValueError("outside home folder")
    return path


def _confirm(prompt: str) -> bool:
    """Ask the user by voice; anything other than a clear yes counts as no."""
    try:
        from Tts import speak
        from Stt import record_and_transcribe
        print(f"[Confirm] {prompt}")
        speak(prompt)
        answer = (record_and_transcribe() or "").lower()
        print(f"[Confirm] Heard: '{answer}'")
        return any(w in answer for w in YES_WORDS)
    except Exception as e:
        print(f"[Confirm] failed: {e}")
        return False


def _locate(name: str):
    """Find a file by exact path, or by file name inside the search roots."""
    try:
        p = _resolve(name)
        if p.exists():
            return p
    except ValueError:
        return None
    hits = _walk_for(Path(name).name.lower(), SEARCH_ROOTS, exact=True)
    return hits[0] if hits else None


def _walk_for(query: str, roots, exact: bool = False):
    words = query.lower().split()
    deadline = time.time() + SEARCH_TIMEOUT
    hits = []
    for root in roots:
        if not root.exists():
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
            for fname in filenames:
                low = fname.lower()
                ok = (low == query.lower()) if exact else all(w in low for w in words)
                if ok:
                    hits.append(Path(dirpath) / fname)
                    if len(hits) >= MAX_RESULTS:
                        return hits
            if time.time() > deadline:
                return hits
    return hits


# ------------------------------------------------------------------ tools

def open_app(name: str) -> str:
    key = name.lower().strip()
    for prefix in ("open ", "launch ", "start ", "the "):
        if key.startswith(prefix):
            key = key[len(prefix):]
    key = key.replace(" app", "").strip()
    if not key:
        return "Sorry boss, which app should I open?"

    target = APP_ALIASES.get(key)
    try:
        if target:
            # target comes from the allowlist, so this is safe
            result = subprocess.run(["cmd", "/c", "start", "", target], capture_output=True)
            if result.returncode != 0:
                return f"Sorry boss, I couldn't open {key}. It may not be installed."
            return f"Opening {key}."
        exe = shutil.which(key)
        if exe:
            subprocess.Popen([exe])
            return f"Opening {key}."
        return f"Sorry boss, I don't know an app called {key}."
    except Exception as e:
        print(f"[open_app] {e}")
        return f"Sorry boss, something went wrong while opening {key}."


def search_files(query: str, folder: str = None) -> str:
    if not query or not query.strip():
        return "Sorry boss, what file should I look for?"
    try:
        roots = [_resolve(folder)] if folder else SEARCH_ROOTS
    except ValueError:
        return "Sorry boss, I can only search inside your user folder."
    hits = _walk_for(query, roots)
    if not hits:
        return f"Sorry boss, I couldn't find any file matching '{query}'."
    lines = [f"I found {len(hits)} file(s) matching '{query}':"]
    for i, p in enumerate(hits, 1):
        print(f"[search_files] {p}")  # full path in console, short form for speech
        lines.append(f"{i}. {p.name} in {p.parent.name}")
    return "\n".join(lines)


def take_screenshot() -> str:
    try:
        import mss
        SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
        out = SCREENSHOT_DIR / f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        with mss.mss() as sct:
            sct.shot(mon=1, output=str(out))
        print(f"[screenshot] saved {out}")
        return "Screenshot taken and saved in your Pictures folder."
    except ImportError:
        return "Sorry boss, the screenshot library is missing. Run pip install mss."
    except Exception as e:
        print(f"[screenshot] {e}")
        return "Sorry boss, I couldn't take the screenshot."


def create_folder(path: str) -> str:
    try:
        p = _resolve(path)
    except ValueError:
        return "Sorry boss, I can only create folders inside your user folder."
    try:
        if p.exists():
            return f"The folder {p.name} already exists."
        p.mkdir(parents=True)
        return f"Created the folder {p.name}."
    except Exception as e:
        print(f"[create_folder] {e}")
        return "Sorry boss, I couldn't create that folder."


def move_file(source: str, destination: str) -> str:
    src = _locate(source)
    if src is None:
        return f"Sorry boss, I couldn't find '{source}'."
    try:
        dst = _resolve(destination)
    except ValueError:
        return "Sorry boss, I can only move files inside your user folder."

    if dst.is_dir() or not dst.suffix:
        dst.mkdir(parents=True, exist_ok=True)
        dst = dst / src.name
    if dst.exists():
        return f"Sorry boss, {dst.name} already exists there, so I won't overwrite it."

    if not _confirm(f"Move {src.name} to {dst.parent.name}? Say yes to confirm."):
        return "Okay boss, I cancelled the move."
    try:
        shutil.move(str(src), str(dst))
        return f"Moved {src.name} to {dst.parent.name}."
    except Exception as e:
        print(f"[move_file] {e}")
        return "Sorry boss, I couldn't move that file."
