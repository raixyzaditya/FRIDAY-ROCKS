"""
The two email tools Friday offers, routed to whichever account is set up:

  1. an app-password mailbox (Tools/Mail.py)  <- `friday --email`; works with Gmail, Outlook, Yahoo, iCloud...
  2. the Google sign-in (Tools/Google.py)     <- the advanced route: python Voice/google_login.py

If both are set up, the app-password mailbox wins. Both use the same safety flow for sending.
"""

from . import Google, Mail

NOT_SET_UP = ("Sorry boss, email isn't set up yet. Run friday --email in a terminal "
              "and I'll be able to read and send mail.")


def _backend():
    if Mail.is_configured():
        return Mail
    if Google.is_connected():
        return Google
    return None


def available() -> bool:
    return _backend() is not None


def check_email(query: str = "", max_results: int = 5, include_body: bool = False) -> str:
    backend = _backend()
    if backend is None:
        return NOT_SET_UP
    return backend.check_email(query=query, max_results=max_results, include_body=include_body)


def send_email(to: str, subject: str, body: str) -> str:
    backend = _backend()
    if backend is None:
        return NOT_SET_UP
    return backend.send_email(to=to, subject=subject, body=body)
