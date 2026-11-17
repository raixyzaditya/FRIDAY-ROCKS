"""
The `friday` command.

    friday              start Friday (first run walks you through setup)
    friday --setup      enter your API keys
    friday --email      set up email (reading and sending) with an app password
    friday --check      diagnose problems (add --online to also test your Groq key)
    friday --version

Installed by install.bat (see README.md). Works from any folder.
"""

import argparse
import ast
import getpass
import importlib.util
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VOICE = ROOT / "Voice"
CONFIG = VOICE / "Config.py"
EXAMPLE = VOICE / "Config.example.py"
VERSION = "1.0.0"

# (import name, pip name)
REQUIRED = [("openai", "openai"), ("whisper", "openai-whisper"), ("sounddevice", "sounddevice"),
            ("numpy", "numpy"), ("scipy", "scipy"), ("pyttsx3", "pyttsx3"), ("requests", "requests"),
            ("ddgs", "ddgs"), ("mss", "mss")]
OPTIONAL = [("PIL", "pillow", "vision: 'what's on my screen?'"),
            ("googleapiclient", "google-api-python-client", "Google Calendar and Gmail"),
            ("google_auth_oauthlib", "google-auth-oauthlib", "Google Calendar and Gmail")]


def _add_paths():
    for p in (str(VOICE), str(ROOT)):  # Friday's modules import each other by plain name
        if p not in sys.path:
            sys.path.insert(0, p)


# -------------------------------------------------------------- Config.py

def read_config_value(name: str, path: Path = None) -> str:
    """The string assigned to NAME in Config.py, or '' (never raises)."""
    try:
        text = (path or CONFIG).read_text(encoding="utf-8")
    except OSError:
        return ""
    found = re.search(rf'^\s*{re.escape(name)}\s*=\s*(".*?"|\'.*?\')\s*(?:#.*)?$', text, re.M)
    if not found:
        return ""
    try:
        return str(ast.literal_eval(found.group(1)))  # only ever a plain string literal, never code
    except (ValueError, SyntaxError):
        return ""


def set_config_value(text: str, name: str, value: str) -> str:
    """Return Config.py text with NAME set to value. Other lines and comments are left untouched."""
    literal = json.dumps(value, ensure_ascii=False)  # always a valid, safely escaped Python string
    pattern = re.compile(rf'^(\s*{re.escape(name)}\s*=\s*).*$', re.M)
    if pattern.search(text):
        return pattern.sub(lambda m: m.group(1) + literal, text, count=1)
    return text.rstrip("\n") + f"\n{name} = {literal}\n"


def config_error(path: Path = None):
    """A readable message if Config.py has a Python syntax error (usually a missing quote around a key),
    else None. It reports the line NUMBER only, never the line itself, because that line may hold a key."""
    try:
        source = (path or CONFIG).read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        ast.parse(source)
    except SyntaxError as e:
        return (f"Voice/Config.py has a typo on line {e.lineno} ({e.msg}). Keys must be inside quotes, "
                f'like GROQ_API_KEY = "gsk_...". Fix that line, or retype the key with:  friday --setup')
    return None


def ensure_config() -> bool:
    """Create Config.py from the example if it's missing. True if it was just created."""
    if CONFIG.exists():
        return False
    CONFIG.write_text(EXAMPLE.read_text(encoding="utf-8"), encoding="utf-8")
    return True


# ------------------------------------------------------------------ setup

def setup(ask=input, ask_secret=getpass.getpass, out=print) -> int:
    """Interactive first-time setup. Keys are typed hidden and written only to Voice/Config.py."""
    created = ensure_config()
    out("\nFriday setup")
    out("-" * 12)
    if created:
        out(f"Created {CONFIG}")
    out("\n1. Groq API key (needed: it's Friday's brain). Free at https://console.groq.com/keys")
    out("   What you type is hidden. Press Enter to keep the current one.")
    try:
        key = ask_secret("   Groq key: ").strip()
        out("\n2. Optional: news keys. Press Enter to skip each.")
        news = ask_secret("   NewsAPI key (newsapi.org): ").strip()
        guardian = ask_secret("   Guardian key (open-platform.theguardian.com): ").strip()
        out("\n3. Optional: email, so Friday can read and send mail for you.")
        want_email = ask("   Set it up now? [y/N] ").strip().lower() in ("y", "yes")
    except (EOFError, KeyboardInterrupt):
        out("\nSetup cancelled. Nothing was changed.")
        return 1

    text = CONFIG.read_text(encoding="utf-8")
    if key:
        if not key.startswith("gsk_"):
            out("   Note: Groq keys normally start with 'gsk_'. Saved anyway.")
        text = set_config_value(text, "GROQ_API_KEY", key)
    if news:
        text = set_config_value(text, "NEWS_API_KEY", news)
    if guardian:
        text = set_config_value(text, "GAURDIAN_API_KEY", guardian)
    CONFIG.write_text(text, encoding="utf-8")

    problem = config_error()
    if problem:
        out("\n" + problem)
        return 1
    if not read_config_value("GROQ_API_KEY"):
        out("\nNo Groq key is set yet, so Friday can't think. Run  friday --setup  again when you have one.")
        return 1
    if want_email:
        setup_email(ask=ask, ask_secret=ask_secret, out=out)  # a failed email test doesn't fail the whole setup
    out("\nAll set. Type  friday  to start, or  friday --check  to test your setup.")
    return 0


# ------------------------------------------------------------ email setup

def _email_settings_from_config():
    """MailServers settings from Config.py, or None if email isn't set up there."""
    _add_paths()
    from Tools import MailServers as ms
    address = read_config_value("EMAIL_ADDRESS")
    password = read_config_value("EMAIL_APP_PASSWORD")
    if not (address and password):
        return None
    provider = read_config_value("EMAIL_PROVIDER") or ms.detect(address) or "custom"
    custom = {"imap_host": read_config_value("EMAIL_IMAP_HOST"), "smtp_host": read_config_value("EMAIL_SMTP_HOST")}
    return ms.settings_for(provider, address, password, custom)


def setup_email(ask=input, ask_secret=getpass.getpass, out=print, test=True) -> int:
    """Set up email in two answers: the address (the provider and servers are worked out from it) and an
    app password. Then the login is tested without sending anything. Returns 0 if ready or skipped."""
    _add_paths()
    from Tools import MailServers as ms
    ensure_config()
    out("\nEmail setup")
    out("-" * 11)
    out("Friday reads and sends mail through YOUR account with an app password: a separate password just for her,")
    out("which you can revoke any time. She only emails people you've saved as contacts, and always reads the")
    out("message back and waits for your 'yes' first. Press Enter at the first question to skip.\n")
    try:
        address = ask("   Your email address: ").strip()
        if not address:
            out("   Skipped. Run  friday --email  whenever you want to set it up.")
            return 0
        if not ms.valid_address(address):
            out("   That doesn't look like an email address. Run  friday --email  to try again.")
            return 1
        provider = ms.detect(address)
        custom = {}
        if provider:
            info = ms.PROVIDERS[provider]
            out(f"\n   Detected {info['label']}. Create an app password first:")
            out(f"   {info['help']}")
        else:
            out("\n   I don't know this provider's mail servers. Search for '<your provider> IMAP SMTP settings'.")
            custom = {"imap_host": ask("   IMAP server (for reading), e.g. imap.example.com: ").strip(),
                      "smtp_host": ask("   SMTP server (for sending), e.g. smtp.example.com: ").strip()}
            if not (custom["imap_host"] and custom["smtp_host"]):
                out("   Both servers are needed. Nothing was saved.")
                return 1
        password = ask_secret("\n   App password (hidden; spaces are fine): ").strip()
    except (EOFError, KeyboardInterrupt):
        out("\nEmail setup cancelled. Nothing was changed.")
        return 1
    if not password:
        out("   No password entered. Nothing was saved.")
        return 1

    settings = ms.settings_for(provider or "custom", address, password, custom)
    if settings is None:
        out("   I couldn't work out the mail server settings. Nothing was saved.")
        return 1
    text = CONFIG.read_text(encoding="utf-8")
    text = set_config_value(text, "EMAIL_ADDRESS", address)
    text = set_config_value(text, "EMAIL_APP_PASSWORD", settings["password"])
    text = set_config_value(text, "EMAIL_PROVIDER", settings["provider"])
    if not provider:
        text = set_config_value(text, "EMAIL_IMAP_HOST", custom["imap_host"])
        text = set_config_value(text, "EMAIL_SMTP_HOST", custom["smtp_host"])
    CONFIG.write_text(text, encoding="utf-8")
    problem = config_error()
    if problem:
        out("\n" + problem)
        return 1
    out("\n   Saved in Voice\\Config.py on this PC only (it is never uploaded or committed to git).")
    if not test:
        return 0

    out("   Testing the login. Nothing is sent or changed...")
    results = ms.test_connection(settings)
    everything_ok = True
    for key, label in (("imap", "Reading mail"), ("smtp", "Sending mail")):
        good, message = results[key]
        everything_ok = everything_ok and good
        out(f"   [{'OK' if good else 'FAIL'}] {label}: {message}")
    if everything_ok:
        out("\nEmail is ready. Try: 'Summarize my latest emails'. To send, first say 'Add Dad as a contact'.")
        return 0
    out("\nSaved, but the test failed. Check the address and app password, then run  friday --email  again.")
    return 1


# -------------------------------------------------------------- preflight

def _have(module: str) -> bool:
    try:
        return importlib.util.find_spec(module) is not None
    except (ImportError, ValueError):
        return False


def missing_required() -> list:
    return [pip for module, pip in REQUIRED if not _have(module)]


def preflight(interactive: bool = None, out=print) -> int:
    """Everything Friday needs before starting. Returns 0 to go ahead, or an exit code after explaining."""
    if not (VOICE / "Main.py").exists():
        out("Friday can't find its Voice folder. Install it from the project folder with:  pip install -e .")
        return 4
    missing = missing_required()
    if missing:
        out("Some libraries are missing: " + ", ".join(missing))
        out(f"Install them with:  pip install -e \"{ROOT}\"   (or run install.bat again)")
        return 3
    if ensure_config():
        out(f"Created {CONFIG}")
    problem = config_error()
    if problem:  # otherwise Friday would crash on start with a traceback pointing deep into her code
        out(problem)
        return 5
    if not read_config_value("GROQ_API_KEY"):
        if interactive is None:
            interactive = sys.stdin is not None and sys.stdin.isatty()
        if not interactive:
            out("No Groq API key is set. Run  friday --setup  in a terminal first.")
            return 2
        out("Welcome! Friday needs a Groq API key before she can start.")
        if setup() != 0:
            return 2
    return 0


# ------------------------------------------------------------------ check

def check(online: bool = False, out=print) -> int:
    """Print a health report. Returns 1 if anything essential is broken. Never prints a key."""
    problems = 0

    def line(level, text):
        nonlocal problems
        if level == "FAIL":
            problems += 1
        out(f"[{level:^4}] {text}")

    py = sys.version_info
    line("OK" if py >= (3, 10) else "FAIL", f"Python {py.major}.{py.minor}.{py.micro}"
         + ("" if py >= (3, 10) else " (Friday needs 3.10 or newer)"))
    for module, pip in REQUIRED:
        line("OK" if _have(module) else "FAIL", f"{pip}" + ("" if _have(module) else f"   -> pip install {pip}"))
    for module, pip, why in OPTIONAL:
        line("OK" if _have(module) else "WARN", f"{pip} (optional, {why})" + ("" if _have(module) else f"   -> pip install {pip}"))

    if not CONFIG.exists():
        line("FAIL", "Voice/Config.py is missing -> run: friday --setup")
        key = ""
    elif config_error():
        line("FAIL", config_error())
        key = ""
    else:
        key = read_config_value("GROQ_API_KEY")
        line("OK" if key else "FAIL", "Groq API key " + (f"is set ({len(key)} characters)" if key else "is empty -> run: friday --setup"))
        for name, label in [("NEWS_API_KEY", "NewsAPI key"), ("GAURDIAN_API_KEY", "Guardian key")]:
            line("OK" if read_config_value(name) else "WARN", f"{label} " + ("is set" if read_config_value(name) else "is empty (news won't work)"))

    if _have("sounddevice"):
        try:
            import sounddevice as sd
            device = sd.query_devices(kind="input")
            line("OK", f"Microphone: {device['name']}")
        except Exception:
            line("FAIL", "No microphone found. Plug one in or set a default recording device in Windows.")
    google = ROOT / "google_token.json"
    line("OK" if google.exists() else "WARN", "Google " + ("is connected" if google.exists() else "isn't connected (optional: run python Voice/google_login.py)"))
    mail = _email_settings_from_config() if CONFIG.exists() and not config_error() else None
    if mail:
        line("OK", f"Email: {mail['address']} ({mail['label']}, app password set)")
    else:
        line("WARN", "Email isn't set up (optional) -> run: friday --email")

    if online:
        if not key:
            line("WARN", "Skipping the online test: no Groq key")
        elif not _have("openai"):
            line("WARN", "Skipping the online test: openai isn't installed")
        else:
            try:
                from openai import OpenAI
                models = OpenAI(api_key=key, base_url="https://api.groq.com/openai/v1", timeout=10, max_retries=0).models.list()
                line("OK", f"Groq accepted the key ({len(models.data)} models available)")
            except Exception as e:
                status = getattr(e, "status_code", None)
                line("FAIL", f"Groq rejected the request ({type(e).__name__}{f', HTTP {status}' if status else ''})")
        if mail:
            from Tools import MailServers as ms
            results = ms.test_connection(mail)  # logs in only; nothing is sent
            for kind, label in (("imap", "Reading mail"), ("smtp", "Sending mail")):
                good, message = results[kind]
                line("OK" if good else "FAIL", f"{label}: {message}")

    out("\nEverything essential is fine." if not problems else f"\n{problems} problem{'s' if problems != 1 else ''} to fix (marked FAIL).")
    return 1 if problems else 0


# ------------------------------------------------------------------- main

def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="friday", description="F.R.I.D.A.Y. - your voice assistant.")
    parser.add_argument("--setup", action="store_true", help="enter your API keys")
    parser.add_argument("--email", action="store_true", help="set up email (read and send mail) with an app password")
    parser.add_argument("--check", action="store_true", help="diagnose problems")
    parser.add_argument("--online", action="store_true", help="with --check: also test your Groq key over the internet")
    parser.add_argument("--version", action="store_true", help="show the version")
    args = parser.parse_args(argv)

    if args.version:
        print(f"Friday {VERSION}")
        return 0
    if args.setup:
        return setup()
    if args.email:
        return setup_email()
    if args.check:
        return check(online=args.online)

    code = preflight()
    if code:
        return code
    _add_paths()
    print("Starting Friday... (the first start loads the speech model and takes a moment)")
    try:
        import Main
        Main.run()
    except KeyboardInterrupt:
        print("\nGoodbye.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
