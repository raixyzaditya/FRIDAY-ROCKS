import os
import re
import sys
import time
import shutil
import subprocess
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'Voice'))

HOME = Path.home()
SEARCH_ROOTS = [HOME / "Desktop", HOME / "Documents", HOME / "Downloads"]
if os.environ.get("OneDrive"):  # Windows often moves Desktop/Documents into OneDrive
    SEARCH_ROOTS.append(Path(os.environ["OneDrive"]))
SCREENSHOT_DIR = HOME / "Pictures" / "FRIDAY_Screenshots"
SKIP_DIRS = {"node_modules", ".git", "__pycache__", "venv", ".venv", "AppData"}
MAX_RESULTS = 5
SEARCH_TIMEOUT = 8  # seconds
FUZZY_THRESHOLD = 0.72  # how similar a file name must be to count as "close" when nothing matches exactly
EXACT_SCORE = 0.9       # scores at or above this are real matches; below it they are only close guesses

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
# Any of these anywhere in the reply cancels, so "yes... no wait" or "I'm not sure" is never a yes.
NO_WORDS = {"no", "nope", "nah", "not", "don't", "dont", "cancel", "stop", "wait", "never",
            "abort", "negative", "hold", "change", "isn't", "wrong"}


def is_yes(answer: str) -> bool:
    """True only for a clear yes. Whole words only, and any negative word vetoes it."""
    words = re.findall(r"[a-z']+", (answer or "").lower())
    if not words or any(w in NO_WORDS for w in words):
        return False
    text = " ".join(words)
    return any(re.search(rf"\b{re.escape(w)}\b", text) for w in YES_WORDS)


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


def _ask(prompt: str, max_wait: int = 12) -> str:
    """Speak a question and listen for the answer. Returns what was heard, or '' if nothing was
    heard or anything failed (a failure never counts as an answer)."""
    try:
        from Tts import speak, wait_idle
        from Stt import record_and_transcribe
        print(f"[Ask] {prompt}")
        wait_idle()  # let any queued speech finish so the mic doesn't hear Friday
        speak(prompt)
        answer = (record_and_transcribe(max_wait=max_wait) or "").strip()
        print(f"[Ask] Heard: '{answer}'")
        return answer
    except Exception as e:
        print(f"[Ask] failed: {e}")
        return ""


def _say(text: str):
    """Speak without listening for an answer."""
    try:
        from Tts import speak, wait_idle
        wait_idle()
        speak(text)
    except Exception as e:
        print(f"[Say] failed: {e}")


def _confirm(prompt: str) -> bool:
    """Ask the user by voice; anything other than a clear yes counts as no."""
    return is_yes(_ask(prompt, max_wait=10))


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


_NUMBER_WORDS = {"zero": "0", "one": "1", "two": "2", "three": "3", "four": "4", "five": "5",
                 "six": "6", "seven": "7", "eight": "8", "nine": "9", "ten": "10"}


def _digits(text: str) -> str:
    """'so w three six two six' -> 'so w 3 6 2 6' (speech recognition often spells numbers as words)."""
    return " ".join(_NUMBER_WORDS.get(w, w) for w in text.lower().split())


def _squash(text: str) -> str:
    """Letters and digits only, lowercase: 'SoW 3-6-26.docx' -> 'sow3626docx'."""
    return re.sub(r"[^a-z0-9]", "", text.lower())


def _score(filename: str, query: str) -> float:
    """How well a file name matches what was asked for. 1.0 = same name, >= EXACT_SCORE = a real match,
    below that = a close guess (typo or mis-heard), 0 = unrelated. Spaces, hyphens, underscores, case,
    the file extension and spoken number words don't matter."""
    as_said = query.lower()
    as_digits = _digits(query)  # 'three six' -> '3 6'; also tried as said, so 'one note' still finds OneNote
    best = _score_text(filename, as_said)
    return max(best, _score_text(filename, as_digits)) if as_digits != as_said else best


def _score_text(filename: str, q_text: str) -> float:
    q = _squash(q_text)
    if not q:
        return 0.0
    stem = _squash(Path(filename).stem)
    full = _squash(filename)
    if q == stem:
        return 1.0
    if q in full:  # 'sow3626' inside 'sow3626docx', whatever the separators were
        return 0.95
    low = filename.lower()
    if all(w in low for w in q_text.split()):
        return EXACT_SCORE
    if len(q) >= 4 and abs(len(stem) - len(q)) <= max(3, len(q) // 2):  # close spelling: typo or mis-heard
        sm = SequenceMatcher(None, q, stem)
        if sm.real_quick_ratio() >= FUZZY_THRESHOLD and sm.quick_ratio() >= FUZZY_THRESHOLD:
            ratio = sm.ratio()
            if ratio >= FUZZY_THRESHOLD:
                return min(ratio, EXACT_SCORE - 0.01)
    return 0.0


def _rank_files(query: str, roots):
    """Score every file under roots (until the time limit) and return (best_hits, timed_out)."""
    deadline = time.time() + SEARCH_TIMEOUT
    scored, seen, timed_out = [], set(), False
    for root in roots:
        if not root.exists():
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
            for fname in filenames:
                path = Path(dirpath) / fname
                if path in seen:  # overlapping roots (e.g. OneDrive contains Documents)
                    continue
                seen.add(path)
                score = _score(fname, query)
                if score > 0:
                    scored.append((score, len(str(path)), path))
            if time.time() > deadline:
                timed_out = True
                break
        if timed_out:
            break
    scored.sort(key=lambda s: (-s[0], s[1]))  # best match first, then the shortest path
    return scored[:MAX_RESULTS], timed_out


def search_files(query: str, folder: str = None) -> str:
    if not query or not query.strip():
        return "Sorry boss, what file should I look for?"
    try:
        roots = [_resolve(folder)] if folder else SEARCH_ROOTS
    except ValueError:
        return "Sorry boss, I can only search inside your user folder."
    hits, timed_out = _rank_files(query, roots)
    widened = False
    if not folder and not timed_out and (not hits or hits[0][0] < EXACT_SCORE):
        # No real match in the usual places (nothing, or only close guesses): look through the whole
        # user folder, and use that result if it found something better.
        wide, timed_out = _rank_files(query, [HOME])
        if wide and (not hits or wide[0][0] > hits[0][0]):
            hits, widened = wide, True
    more = " I ran out of time, so there may be more." if timed_out else ""
    if not hits:
        where = ("your whole user folder" if not folder else ", ".join(r.name for r in roots if r.exists()))
        where = where or "your folders"
        return (f"Sorry boss, I couldn't find any file matching '{query}'. I searched {where}. "
                f"If it's somewhere else, like another drive, tell me which folder.{more}")
    close_only = hits[0][0] < EXACT_SCORE
    if widened:
        header = ("Not in your usual folders, but searching your whole user folder, " +
                  (f"I couldn't find an exact match for '{query}'; these look close:" if close_only
                   else f"I found {len(hits)} file(s) matching '{query}':"))
    else:
        header = (f"I couldn't find an exact match for '{query}', but these look close:" if close_only
                  else f"I found {len(hits)} file(s) matching '{query}':")
    lines = [header]
    for i, (_score_value, _length, p) in enumerate(hits, 1):
        print(f"[search_files] {p}")  # full path in console, short form for speech
        lines.append(f"{i}. {p.name} in {p.parent.name}")
    if more:
        lines.append(more.strip())
    return "\n".join(lines)


VK_KEYS = {
    "mute": 0xAD, "volume_down": 0xAE, "volume_up": 0xAF,
    "next_track": 0xB0, "previous_track": 0xB1, "play_pause": 0xB3,
}
KEY_ACTIONS = {
    "mute": "Toggled mute.", "volume_up": "Turned the volume up.", "volume_down": "Turned the volume down.",
    "next_track": "Skipped to the next track.", "previous_track": "Went back a track.",
    "play_pause": "Toggled play and pause.",
}


def system_control(action: str, steps: int = 1) -> str:
    """Volume, media keys and screen lock, using only Windows' own key events (no extra libraries)."""
    action = (action or "").lower().strip().replace(" ", "_")
    try:
        import ctypes
        user32 = ctypes.windll.user32
    except (ImportError, AttributeError):
        return "Sorry boss, system controls only work on Windows."

    try:
        if action == "lock_screen":
            user32.LockWorkStation()
            return "Locking the screen."
        if action not in VK_KEYS:
            return f"Sorry boss, I can't do '{action}'. Try: {', '.join(list(VK_KEYS) + ['lock_screen'])}."
        try:
            steps = max(1, min(int(steps), 10))
        except (TypeError, ValueError):
            steps = 1
        # one volume key press is about 2%, so 5 presses is roughly one 10% step
        presses = steps * 5 if action in ("volume_up", "volume_down") else 1
        for _ in range(presses):
            user32.keybd_event(VK_KEYS[action], 0, 0, 0)  # key down
            user32.keybd_event(VK_KEYS[action], 0, 2, 0)  # key up
        return KEY_ACTIONS[action]
    except Exception as e:
        print(f"[system_control] {e}")
        return "Sorry boss, that system control didn't work."


def take_screenshot() -> str:
    try:
        import mss
        SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
        out = SCREENSHOT_DIR / f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        with mss.mss() as sct:
            sct.shot(mon=1, output=str(out))
        print(f"[screenshot] saved {out}")
        return f"Screenshot taken and saved as {out.name} in the folder {SCREENSHOT_DIR} (Pictures, then FRIDAY_Screenshots)."
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


# Files that Windows runs when opened. Friday never creates these: a prompt-injected "create file" must not
# be able to drop something that executes.
BLOCKED_EXTENSIONS = {".exe", ".bat", ".cmd", ".ps1", ".psm1", ".vbs", ".vbe", ".js", ".jse", ".wsf", ".wsh",
                      ".msi", ".scr", ".com", ".lnk", ".reg", ".hta", ".jar", ".dll", ".cpl", ".url", ".pif"}
MAX_FILE_CHARS = 20000
_BAD_NAME_CHARS = set('<>:"|?*')


def create_file(path: str, content: str = "") -> str:
    """Create a NEW file inside the user's home folder. A bare name goes in Documents. Never overwrites."""
    path = (path or "").strip()
    content = content or ""
    if not path:
        return "Sorry boss, what should I call the file?"
    if len(content) > MAX_FILE_CHARS:
        return f"Sorry boss, that's too much text for me to write in one go. The limit is {MAX_FILE_CHARS} characters."
    try:
        bare = Path(path)
        if not bare.is_absolute() and len(bare.parts) == 1 and not path.startswith("~"):
            target = HOME / "Documents" / bare.name  # just a name: put it somewhere sensible
        else:
            target = _resolve(path)
    except ValueError:
        return "Sorry boss, I can only create files inside your user folder."
    if not target.suffix:
        target = target.with_name(target.name + ".txt")
    if target.suffix.lower() in BLOCKED_EXTENSIONS:
        return f"Sorry boss, I don't create {target.suffix} files because Windows can run them."
    if not target.name or any(ch in _BAD_NAME_CHARS for ch in target.name):
        return "Sorry boss, that file name has characters Windows doesn't allow."
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
    except OSError as e:  # e.g. a FILE is sitting where the folder should be
        print(f"[create_file] {e}")
        return "Sorry boss, I couldn't create that file."
    try:
        with open(target, "x", encoding="utf-8") as f:  # 'x' = fail if it exists, so nothing is overwritten
            f.write(content)
    except FileExistsError:
        return f"Sorry boss, {target.name} already exists in {target.parent.name}, so I won't overwrite it."
    except OSError as e:
        print(f"[create_file] {e}")
        return "Sorry boss, I couldn't create that file."
    print(f"[create_file] {target}")
    return f"Created {target.name} in the {target.parent.name} folder."


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
