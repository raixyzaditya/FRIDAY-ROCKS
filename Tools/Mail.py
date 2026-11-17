"""
Email over IMAP/SMTP with an app password: works with Gmail, Outlook, Yahoo, iCloud and others,
with no Google Cloud project and no browser sign-in. Set up with:  friday --email

Safety design (same rules as the Gmail-API backend, because sending uses the same shared flow):
  * READING IS HANDS-OFF: the inbox is opened read-only (IMAP EXAMINE) and messages are fetched with
    BODY.PEEK, so Friday never marks anything as read, moves it or deletes it. Attachments aren't downloaded:
    only the first part of each message is fetched.
  * SENDING goes through Google.send_with: saved contacts only, a spoken read-back of the recipient, subject
    and whole message, a clear "yes", a daily cap and a log of everything sent.
  * Email text is returned labelled as data, so a message can't give Friday instructions.
  * The app password is only ever used to log in. It is never printed or logged.
A caveat the user accepted: an app password can do more than Friday does (providers don't offer a read-and-send
-only app password). It lives in plain text in Voice/Config.py, which is gitignored. Revoke it at the provider
any time.
"""

import email
import email.policy
import imaplib
import os
import re
import smtplib
import ssl
import sys
from datetime import date, timedelta
from email.message import EmailMessage
from email.utils import parseaddr

from . import Google, MailServers

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'Voice'))
import Config

IMAP_TIMEOUT = 20
SMTP_TIMEOUT = 25
PREVIEW_FETCH_BYTES = 30000    # enough for the start of any message, without downloading attachments
BODY_FETCH_BYTES = 200000
MAX_SEARCH_TOKENS = 8
NOT_SET_UP = "Sorry boss, email isn't set up yet. Run friday --email in a terminal and I'll be able to read and send mail."
AUTH_FAILED = ("Sorry boss, your email provider rejected the login. "
               "Check your address and app password with:  friday --email")
_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


# ------------------------------------------------------------------ settings

def settings():
    """Connection settings from Config.py (read fresh each time), or None if email isn't set up."""
    address = str(getattr(Config, "EMAIL_ADDRESS", "") or "").strip()
    password = str(getattr(Config, "EMAIL_APP_PASSWORD", "") or "").strip()
    if not address or not password:
        return None
    provider = str(getattr(Config, "EMAIL_PROVIDER", "") or "").strip().lower() or MailServers.detect(address) or "custom"
    custom = {
        "imap_host": getattr(Config, "EMAIL_IMAP_HOST", ""), "imap_port": getattr(Config, "EMAIL_IMAP_PORT", ""),
        "smtp_host": getattr(Config, "EMAIL_SMTP_HOST", ""), "smtp_port": getattr(Config, "EMAIL_SMTP_PORT", ""),
        "smtp_security": getattr(Config, "EMAIL_SMTP_SECURITY", ""),
    }
    return MailServers.settings_for(provider, address, password, custom)


def is_configured() -> bool:
    return settings() is not None


def describe() -> str:
    s = settings()
    return f"{s['address']} ({s['label']})" if s else "not set up"


def _failure(tool: str, e: Exception) -> str:
    s = settings() or {}
    detail = f"[{tool}] {type(e).__name__}: {e}"
    if s.get("password"):
        detail = detail.replace(s["password"], "***")  # never log the password, even inside an error message
    print(detail)
    if isinstance(e, (imaplib.IMAP4.error, smtplib.SMTPAuthenticationError)):
        return AUTH_FAILED
    host = s.get("imap_host" if tool == "check_email" else "smtp_host", "your email server")
    return f"Sorry boss, I couldn't reach your email server: {MailServers.plain_error(e, host)}."


# ------------------------------------------------------------------- reading

def _quote(term: str) -> str:
    """One IMAP search term, safely quoted: control characters (including line breaks, which would let a
    search term smuggle in extra IMAP commands) are removed, and quotes and backslashes are escaped."""
    term = re.sub(r"[\x00-\x1f\x7f]", " ", term).strip()[:100]
    return '"' + term.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _criteria(query: str, gmail: bool) -> list:
    """Turn a spoken search ('from:amazon', 'unread', 'subject:invoice newer_than:7d') into IMAP search keys."""
    query = (query or "").strip()
    if not query or query.lower() in ("is:unread", "is:unread in:inbox", "unread", "in:inbox is:unread"):
        return ["UNSEEN"]
    if gmail:
        return ["X-GM-RAW", _quote(query)]  # Gmail accepts its own full search syntax
    keys = []
    for token in re.findall(r'(\w+:"[^"]*"|\w+:\S+|"[^"]*"|\S+)', query)[:MAX_SEARCH_TOKENS]:
        field, colon, value = token.partition(":")
        value = (value if colon else token).strip('"')
        field = field.lower() if colon else ""
        if field == "is" and value.lower() in ("unread", "new"):
            keys.append("UNSEEN")
        elif field == "is" and value.lower() in ("read", "seen"):
            keys.append("SEEN")
        elif field in ("from", "to", "cc", "subject", "body") and value:
            keys += [field.upper(), _quote(value)]
        elif field == "newer_than" and re.fullmatch(r"\d{1,3}[dwm]", value):
            days = int(value[:-1]) * {"d": 1, "w": 7, "m": 30}[value[-1]]
            since = date.today() - timedelta(days=days)
            keys += ["SINCE", f"{since.day}-{_MONTHS[since.month - 1]}-{since.year}"]  # locale-proof month name
        elif value:
            keys += ["TEXT", _quote(token if colon else value)]
    return keys or ["UNSEEN"]


def _open_inbox(s: dict):
    conn = imaplib.IMAP4_SSL(s["imap_host"], s["imap_port"], timeout=IMAP_TIMEOUT)
    try:
        conn.login(s["address"], s["password"])
        status, _data = conn.select("INBOX", readonly=True)  # EXAMINE: nothing can be changed
        if status != "OK":
            raise imaplib.IMAP4.error("couldn't open the inbox")
    except Exception:
        _logout(conn)
        raise
    return conn


def _logout(conn):
    try:
        conn.logout()
    except Exception:
        pass


def _search(conn, criteria: list) -> list:
    if all(c.isascii() for c in criteria):
        status, data = conn.uid("SEARCH", None, *criteria)
    else:  # non-English search words need an explicit charset
        status, data = conn.uid("SEARCH", "CHARSET", "UTF-8", *[c.encode("utf-8") for c in criteria])
    if status != "OK":
        raise imaplib.IMAP4.error("the search was rejected")
    return data[0].split() if data and data[0] else []


def _message_text(msg, limit: int) -> str:
    """Readable text of a message: the text/plain part, or tag-stripped HTML."""
    try:
        part = msg.get_body(preferencelist=("plain", "html"))
        if part is None:
            return ""
        content = part.get_content()
    except Exception:  # an odd encoding or a truncated part: skip the text rather than fail
        return ""
    if part.get_content_type() == "text/html":
        content = Google.html_to_text(content)
    return " ".join(str(content).split())[:limit]


def _row(conn, uid, include_body: bool) -> str:
    limit = BODY_FETCH_BYTES if include_body else PREVIEW_FETCH_BYTES
    status, data = conn.uid("FETCH", uid, f"(BODY.PEEK[]<0.{limit}>)")  # PEEK: doesn't mark it as read
    raw = next((item[1] for item in (data or []) if isinstance(item, tuple)), None)
    if status != "OK" or not raw:
        return "unknown: (couldn't read this message)"
    msg = email.message_from_bytes(raw, policy=email.policy.default)
    name, address = parseaddr(str(msg["From"] or ""))
    sender = (name or address or "unknown").strip()
    subject = " ".join(str(msg["Subject"] or "(no subject)").split())[:150]
    text = _message_text(msg, Google.MAX_BODY_CHARS if include_body else Google.MAX_SNIPPET_CHARS)
    return f"{sender}: {subject} - {text}" if text else f"{sender}: {subject}"


def check_email(query: str = "", max_results: int = 5, include_body: bool = False) -> str:
    """Read-only. Default: unread mail in the inbox, newest first. include_body=True reads the message text."""
    try:
        max_results = max(1, min(int(max_results), 10))
    except (TypeError, ValueError):
        max_results = 5
    s = settings()
    if not s:
        return NOT_SET_UP
    conn = None
    try:
        conn = _open_inbox(s)
        uids = _search(conn, _criteria(query, s["provider"] == "gmail"))
        rows = [_row(conn, uid, include_body) for uid in reversed(uids[-max_results:])]  # newest first
    except Exception as e:
        return _failure("check_email", e)
    finally:
        if conn is not None:
            _logout(conn)
    return Google.format_email_summary(rows, len(uids), include_body, bool((query or "").strip()))


# ------------------------------------------------------------------- sending

def _ready():
    return None if settings() else NOT_SET_UP


def _deliver(message: EmailMessage):
    s = settings()
    message["From"] = s["address"]
    context = ssl.create_default_context()
    if s["smtp_security"] == "ssl":
        server = smtplib.SMTP_SSL(s["smtp_host"], s["smtp_port"], timeout=SMTP_TIMEOUT, context=context)
    else:
        server = smtplib.SMTP(s["smtp_host"], s["smtp_port"], timeout=SMTP_TIMEOUT)
        server.ehlo()
        server.starttls(context=context)
        server.ehlo()
    try:
        server.login(s["address"], s["password"])
        server.send_message(message)
    finally:
        try:
            server.quit()
        except Exception:
            pass


def send_email(to: str, subject: str, body: str) -> str:
    """Same safety flow as every email backend: saved contacts only, spoken read-back, a clear yes,
    a daily cap and a log."""
    return Google.send_with(to, subject, body, ready=_ready, deliver=_deliver, fail=_failure)
