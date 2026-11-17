"""
Mail provider settings and a login test. Standard library only (no Friday imports), so `friday --email`
can use it without loading the rest of the assistant.

Friday reaches your mailbox with the standard IMAP (reading) and SMTP (sending) protocols and an APP
PASSWORD: a separate password you create just for Friday, which you can revoke any time without touching
your real password. Known providers are filled in automatically from the email address.
"""

import imaplib
import re
import smtplib
import socket
import ssl

PROVIDERS = {
    "gmail": {
        "label": "Gmail", "imap_host": "imap.gmail.com", "imap_port": 993,
        "smtp_host": "smtp.gmail.com", "smtp_port": 465, "smtp_security": "ssl",
        "help": "Turn on 2-Step Verification, then create an app password at https://myaccount.google.com/apppasswords",
    },
    "outlook": {
        "label": "Outlook / Hotmail", "imap_host": "outlook.office365.com", "imap_port": 993,
        "smtp_host": "smtp-mail.outlook.com", "smtp_port": 587, "smtp_security": "starttls",
        "help": "Turn on two-step verification, then create an app password under Security > Advanced security options "
                "at https://account.microsoft.com/security",
    },
    "yahoo": {
        "label": "Yahoo", "imap_host": "imap.mail.yahoo.com", "imap_port": 993,
        "smtp_host": "smtp.mail.yahoo.com", "smtp_port": 465, "smtp_security": "ssl",
        "help": "Create an app password under Account Security at https://login.yahoo.com/account/security",
    },
    "icloud": {
        "label": "iCloud", "imap_host": "imap.mail.me.com", "imap_port": 993,
        "smtp_host": "smtp.mail.me.com", "smtp_port": 587, "smtp_security": "starttls",
        "help": "Create an app-specific password at https://appleid.apple.com (Sign-In and Security)",
    },
}

_ADDRESS = re.compile(r"^[^@\s,;<>\"']+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}$")


def valid_address(address: str) -> bool:
    return bool(_ADDRESS.match(address or ""))


def detect(address: str):
    """'ravi@gmail.com' -> 'gmail'. None when the domain isn't one of the known providers."""
    domain = (address or "").rsplit("@", 1)[-1].strip().lower()
    if domain in ("gmail.com", "googlemail.com"):
        return "gmail"
    if re.match(r"^(outlook|hotmail|live|msn)\.", domain):
        return "outlook"
    if re.match(r"^yahoo\.", domain) or domain in ("ymail.com", "rocketmail.com"):
        return "yahoo"
    if domain in ("icloud.com", "me.com", "mac.com"):
        return "icloud"
    return None


def settings_for(provider: str, address: str, password: str, custom: dict = None):
    """The full connection settings, or None if the provider is unknown and no custom servers were given.
    custom may hold imap_host, imap_port, smtp_host, smtp_port and smtp_security."""
    custom = {k: v for k, v in (custom or {}).items() if v not in (None, "")}
    base = dict(PROVIDERS.get(provider, {}))
    unknown = not base
    if unknown:
        if not (custom.get("imap_host") and custom.get("smtp_host")):
            return None
        base = {"label": "your email provider", "imap_port": 993, "smtp_port": 465, "help": ""}
    base.update(custom)
    try:
        base["imap_port"], base["smtp_port"] = int(base["imap_port"]), int(base["smtp_port"])
    except (TypeError, ValueError):
        return None
    # Port 465 is implicit SSL, anything else (587...) is STARTTLS. Work that out whenever the security mode
    # wasn't stated, including when a known provider's port was overridden, so the two can't disagree.
    stated = custom.get("smtp_security") in ("ssl", "starttls")
    if stated:
        base["smtp_security"] = custom["smtp_security"]
    elif unknown or "smtp_port" in custom:
        base["smtp_security"] = "ssl" if base["smtp_port"] == 465 else "starttls"
    base.update(address=(address or "").strip(), password=(password or "").replace(" ", ""),
                provider=provider if provider in PROVIDERS else "custom")
    return base


def plain_error(e: Exception, host: str) -> str:
    """A short plain-language reason for a connection or login failure. Never includes the password."""
    if isinstance(e, (imaplib.IMAP4.error, smtplib.SMTPAuthenticationError)):
        return ("the server rejected the address or app password (it must be an app password, "
                "not your normal one)")
    if isinstance(e, socket.gaierror):
        return f"couldn't find {host} (check your internet connection)"
    if isinstance(e, (socket.timeout, TimeoutError)):
        return f"{host} didn't answer in time"
    if isinstance(e, ssl.SSLError):
        return f"the secure connection to {host} failed"
    if isinstance(e, (ConnectionError, OSError, smtplib.SMTPException)):
        return f"couldn't connect to {host}"
    return type(e).__name__


def test_connection(settings: dict, timeout: float = 15) -> dict:
    """Logs in to the reading (IMAP) and sending (SMTP) servers WITHOUT sending or changing anything.
    Returns {'imap': (ok, message), 'smtp': (ok, message)}."""
    return {"imap": _test_imap(settings, timeout), "smtp": _test_smtp(settings, timeout)}


def _test_imap(s: dict, timeout: float):
    conn = None
    try:
        conn = imaplib.IMAP4_SSL(s["imap_host"], s["imap_port"], timeout=timeout)
        conn.login(s["address"], s["password"])
        conn.select("INBOX", readonly=True)
        return True, "can read your inbox"
    except Exception as e:
        return False, plain_error(e, s["imap_host"])
    finally:
        if conn is not None:
            try:
                conn.logout()
            except Exception:
                pass


def _test_smtp(s: dict, timeout: float):
    server = None
    try:
        context = ssl.create_default_context()
        if s["smtp_security"] == "ssl":
            server = smtplib.SMTP_SSL(s["smtp_host"], s["smtp_port"], timeout=timeout, context=context)
        else:
            server = smtplib.SMTP(s["smtp_host"], s["smtp_port"], timeout=timeout)
            server.ehlo()
            server.starttls(context=context)
            server.ehlo()
        server.login(s["address"], s["password"])
        return True, "can send mail"
    except Exception as e:
        return False, plain_error(e, s["smtp_host"])
    finally:
        if server is not None:
            try:
                server.quit()
            except Exception:
                pass
