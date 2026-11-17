"""
Email contacts: names -> addresses, saved in friday_contacts.json (gitignored).

Why this exists: speech recognition can mishear an email address, and a typo would send your message
to a stranger. So in contacts-only mode (the default) Friday only emails saved contacts.

Adding a contact is a short spoken conversation (add_contact): she asks which email service
("gmail", "yahoo"...), you spell only the part before the @, and she adds the domain herself. Then she
spells the whole address back letter by letter and nothing is saved without a clear yes.
"""

import json
import os
import re
import threading
from pathlib import Path

CONTACTS_FILE = Path(__file__).resolve().parent.parent / "friday_contacts.json"
MAX_CONTACTS = 200
MAX_NAME_CHARS = 40
MAX_LOCAL_CHARS = 64
EMAIL_PATTERN = re.compile(r"^[^@\s,;<>\"']+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}$")
COMMON_DOMAINS = {"gmail.com", "yahoo.com", "outlook.com", "hotmail.com", "icloud.com", "live.com",
                  "proton.me", "protonmail.com", "rediffmail.com", "yahoo.co.in", "me.com"}

# What the user says -> the domain. Matched against the answer with spaces and punctuation removed,
# so "G mail", "gmail dot com" and "Gmail." all work. Longer names first.
DOMAIN_WORDS = [("googlemail", "gmail.com"), ("gmail", "gmail.com"), ("hotmail", "hotmail.com"),
                ("outlook", "outlook.com"), ("icloud", "icloud.com"), ("protonmail", "proton.me"),
                ("proton", "proton.me"), ("rediff", "rediffmail.com"), ("yahoo", "yahoo.com"),
                ("live", "live.com")]
OTHER_DOMAIN_WORDS = ("other", "else", "company", "work", "custom", "different", "own domain", "none of")

_lock = threading.RLock()


def valid_address(address: str) -> bool:
    return bool(EMAIL_PATTERN.match(address or ""))


def spoken(address: str) -> str:
    """'ravi.k@gmail.com' -> 'ravi dot k at gmail dot com'."""
    return address.replace("@", " at ").replace(".", " dot ").replace("_", " underscore ").replace("-", " dash ")


_SYMBOLS = {".": "dot", "_": "underscore", "-": "dash", "+": "plus"}


def _spell(text: str) -> str:
    return " ".join(_SYMBOLS.get(ch, ch) for ch in text)


def spelled(address: str) -> str:
    """Letter by letter, so a mishearing is easy to catch: 'ravi.k@gmail.com' -> 'r a v i dot k at gmail dot com'.
    Well-known domains are read as words; unusual ones are spelled out too."""
    local, _, domain = address.partition("@")
    domain_part = " ".join(spoken(domain).split()) if domain.lower() in COMMON_DOMAINS else _spell(domain)
    return f"{_spell(local)} at {domain_part}"


# --------------------------------------------------- understanding spoken answers

_SPOKEN_SYMBOLS = {"dot": ".", "period": ".", "point": ".", "underscore": "_", "dash": "-", "hyphen": "-",
                   "minus": "-", "plus": "+"}
_DIGITS = {"zero": "0", "one": "1", "two": "2", "three": "3", "four": "4", "five": "5", "six": "6",
           "seven": "7", "eight": "8", "nine": "9"}
# How speech recognition often writes the NAME of a letter
_LETTER_NAMES = {"bee": "b", "see": "c", "sea": "c", "dee": "d", "gee": "g", "jay": "j", "kay": "k", "ell": "l",
                 "em": "m", "en": "n", "oh": "o", "pea": "p", "queue": "q", "are": "r", "tee": "t", "you": "u",
                 "vee": "v", "why": "y", "zee": "z", "ex": "x", "ay": "a", "eye": "i"}
_FILLER = {"it", "its", "it's", "is", "my", "email", "address", "the", "um", "uh", "so", "okay", "ok", "and", "then",
           "letters", "spelled", "spelling", "that", "this", "please"}


def parse_domain(text: str):
    """'gmail', 'G mail', 'yahoo please' -> a domain, or None if no known service was named."""
    squashed = re.sub(r"[^a-z0-9.]", "", (text or "").lower())
    for word, domain in DOMAIN_WORDS:
        if word in squashed:
            return domain
    return None


def wants_other_domain(text: str) -> bool:
    low = (text or "").lower()
    return any(w in low for w in OTHER_DOMAIN_WORDS)


def parse_custom_domain(text: str):
    """'acme dot co dot in' / 'acme.com' -> 'acme.co.in', or None."""
    low = re.sub(r"\s+dot\s+", ".", (text or "").lower().strip())
    low = re.sub(r"\s+", "", low).strip(".,!?;:")
    return low if re.fullmatch(r"[a-z0-9-]+(?:\.[a-z0-9-]+)+", low) and re.search(r"\.[a-z]{2,}$", low) else None


def parse_spelled_local(text: str):
    """What the user spelled before the @ -> 'ravi.k', or None if it can't be a valid address part.

    Understands: single letters ('R A V I', 'R-A-V-I', 'R. A. V. I.'), 'dot / underscore / dash / plus',
    digits as words ('one two three') or numerals, letter names ('bee', 'dee'), 'double l', filler like
    "it's", and a whole address said by mistake ('ravi at gmail dot com' keeps only 'ravi')."""
    tokens = re.sub(r"[-,]", " ", (text or "").lower().replace("@", " at ")).split()
    out, repeat_next = [], False
    for token in tokens:
        if token == "at":  # they said the whole address: only the part before the @ matters
            break
        if token in _FILLER:
            continue
        if token == "double":
            repeat_next = True
            continue
        token = token.rstrip(".!?;:")
        if token in _SPOKEN_SYMBOLS:
            pieces = [_SPOKEN_SYMBOLS[token]]
        elif token in _DIGITS:
            pieces = [_DIGITS[token]]
        elif token in _LETTER_NAMES:
            pieces = [_LETTER_NAMES[token]]
        elif re.fullmatch(r"[a-z0-9]+(?:\.[a-z0-9]+)*", token):  # a letter, a number, 'r.a.v.i', or a word said at once
            parts = token.split(".")
            # 'R.A.V.I.' is how recognisers write spelled-out letters: those dots are abbreviation marks, not
            # part of the address. 'ravi.k' has a multi-letter part, so its dot is real and stays.
            pieces = ["".join(parts)] if all(len(p) == 1 for p in parts) else [token]
        else:
            return None
        if repeat_next:
            pieces = [pieces[0] * 2] + pieces[1:]
            repeat_next = False
        out.extend(pieces)
    local = "".join(out)
    if not local or len(local) > MAX_LOCAL_CHARS:
        return None
    if local.startswith(".") or local.endswith(".") or ".." in local or not re.fullmatch(r"[a-z0-9._+-]+", local):
        return None
    return local


def _wants_out(answer: str) -> bool:
    low = (answer or "").lower()
    return bool(re.search(r"\b(cancel|stop|nevermind|forget it|abort)\b|never mind", low))


# ------------------------------------------------------------------- storage

def _key(name: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9 '.-]", "", (name or "").lower()).split())


def _load() -> dict:
    try:
        data = json.loads(CONTACTS_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {k: v for k, v in data.items()
            if isinstance(v, dict) and isinstance(v.get("name"), str) and valid_address(v.get("email", ""))}


def _save(contacts: dict):
    tmp = CONTACTS_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(contacts, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, CONTACTS_FILE)


def find(name: str) -> list:
    """Contacts matching a spoken name: an exact match wins; otherwise any contact whose full name starts
    with it or has it as a word ('ravi' finds 'Ravi Kumar'). Several results means it's ambiguous."""
    key = _key(name)
    if not key:
        return []
    with _lock:
        contacts = _load()
    if key in contacts:
        return [contacts[key]]
    return [c for k, c in contacts.items() if k.startswith(key) or key in k.split()]


def by_address(address: str):
    wanted = (address or "").strip().lower()
    with _lock:
        for contact in _load().values():
            if contact["email"].lower() == wanted:
                return contact
    return None


# ------------------------------------------------------------------- tools

def _check_new(name: str, email: str = None):
    """Validate before asking anything. Returns (display, key, existing, error)."""
    display = " ".join((name or "").split())
    key = _key(display)
    if not key:
        return None, None, None, "Sorry boss, what's the person's name?"
    if len(display) > MAX_NAME_CHARS:
        return None, None, None, f"Sorry boss, keep the name under {MAX_NAME_CHARS} characters."
    if email is not None and not valid_address(email):
        return None, None, None, (f"Sorry boss, '{spoken(email)}' doesn't look like a valid email address. "
                                  f"Can you say it again, slowly?")
    with _lock:
        contacts = _load()
        existing = contacts.get(key)
        if existing is None and len(contacts) >= MAX_CONTACTS:
            return None, None, None, f"Sorry boss, I can only keep {MAX_CONTACTS} contacts."
    return display, key, existing, None


def _question(display: str, email: str, existing) -> str:
    if existing:
        return (f"{existing['name']} is saved as {spelled(existing['email'])}. "
                f"Change it to {spelled(email)}? Say yes to change it.")
    return f"I'll save {display} as {spelled(email)}. Is that right? Say yes to save."


def _commit(display: str, key: str, email: str, existing) -> str:
    with _lock:
        contacts = _load()
        contacts[key] = {"name": existing["name"] if existing else display, "email": email}
        _save(contacts)
    return f"Saved {display} as {spoken(email)}."


def save_contact(name: str, email: str) -> str:
    """Save a contact from an address that was already given in full. Spelled back, needs a yes."""
    display, key, existing, error = _check_new(name, (email or "").strip())
    if error:
        return error
    email = email.strip()
    if existing and existing["email"].lower() == email.lower():
        return f"{existing['name']} is already saved with that address."
    from .PCControl import _confirm
    if not _confirm(_question(display, email, existing)):
        return "Okay boss, I didn't save it."
    return _commit(display, key, email, existing)


def add_contact(name: str) -> str:
    """Guided, spoken way to add a contact: she asks which email service (gmail, yahoo...), the user
    spells only the part before the @, and she completes the address. Nothing is saved until the user
    says yes to the full address spelled back."""
    display, key, existing, error = _check_new(name)
    if error:
        return error
    from .PCControl import _ask, _say, is_yes

    def ask_until(question, parse, reprompt, tries=3):
        """Ask, understand the answer, re-ask if needed. Returns (value, user_cancelled)."""
        for _ in range(tries):
            answer = _ask(question)
            if _wants_out(answer):
                return None, True
            value = parse(answer)
            if value:
                return value, False
            question = reprompt if answer else "Sorry, I didn't catch that. " + reprompt
        return None, False

    def parse_service(answer):
        """'gmail' -> gmail.com. 'other' leads to a follow-up question for the whole domain."""
        domain = parse_domain(answer)
        if domain:
            return domain
        if wants_other_domain(answer):
            return ask_until("Say the whole domain, like company dot com.", parse_custom_domain,
                             "Say the domain again, like company dot com.")[0]
        return parse_custom_domain(answer) if "dot" in answer.lower() or "." in answer else None

    gave_up = "Okay boss, I didn't add anyone."
    for attempt in range(3):
        domain, cancelled = ask_until(
            f"Which email service does {display} use? For example gmail, yahoo or outlook.",
            parse_service, "Please say one of gmail, yahoo, outlook, hotmail or icloud, or say other.")
        if cancelled:
            return gave_up
        if not domain:
            return "Sorry boss, I couldn't work out the email service, so I didn't add anyone."

        local, cancelled = ask_until(
            f"Okay, {domain.split('.')[0]}. Now spell the part before the at sign, letter by letter. "
            f"Say dot for a dot, and say numbers as digits.",
            parse_spelled_local, "Spell it again slowly, one letter at a time.")
        if cancelled:
            return gave_up
        if not local:
            return "Sorry boss, I couldn't make out the spelling, so I didn't add anyone."

        email = f"{local}@{domain}"
        if not valid_address(email):  # parsing pre-checks this, but never store anything unchecked
            continue
        if existing and existing["email"].lower() == email.lower():
            return f"{existing['name']} is already saved with that address."
        question = (_question(display, email, existing) if existing
                    else f"I heard {spelled(email)}. Is that right? Say yes to save {display}.")
        if is_yes(_ask(question, max_wait=10)):
            return _commit(display, key, email, existing)
        if attempt < 2:
            _say("No problem, let's try that again.")
    return "Okay boss, let's leave it for now. I didn't add anyone."


def forget_contact(name: str) -> str:
    matches = find(name)
    if not matches:
        return f"I don't have a contact called {name}."
    if len(matches) > 1:
        return "That matches more than one contact: " + ", ".join(c["name"] for c in matches) + ". Which one?"
    with _lock:
        contacts = _load()
        removed = contacts.pop(_key(matches[0]["name"]), None)
        if removed:
            _save(contacts)
    return f"Removed {matches[0]['name']} from your contacts."


def list_contacts() -> str:
    with _lock:
        names = sorted(c["name"] for c in _load().values())
    if not names:
        return "You have no saved contacts yet."
    return f"You have {len(names)} contact{'s' if len(names) != 1 else ''}: " + ", ".join(names) + "."
