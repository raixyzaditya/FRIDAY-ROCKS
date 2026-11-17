"""
One-time Google sign-in for Calendar and Gmail (read-only mail). Run from this folder:

    python google_login.py

Before the first run:
  1. Go to https://console.cloud.google.com and create a project.
  2. APIs & Services > Library: enable "Google Calendar API" and "Gmail API".
  3. APIs & Services > OAuth consent screen: choose External, add yourself as a Test user.
  4. APIs & Services > Credentials > Create credentials > OAuth client ID > "Desktop app".
  5. Download the JSON and save it as  google_credentials.json  in the project's top folder
     (next to the Tools and Voice folders).
  6. pip install google-api-python-client google-auth-oauthlib

The browser opens once so YOU can approve access. Friday gets: read your Gmail, send email (only
after you say yes to a read-back), and view or add calendar events. She cannot delete or edit mail.
Both Google files stay on this PC and are gitignored.

Already logged in before sending existed? Just run this again and approve the new "send email"
permission: it replaces the old token.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from Tools import Google


def main():
    try:
        path = Google.login()
    except FileNotFoundError as e:
        print(f"\n{e}\nFollow the setup steps at the top of this file first.")
        return
    except ImportError:
        print("\nMissing libraries. Run:  pip install google-api-python-client google-auth-oauthlib")
        return
    print(f"\nConnected. Token saved to {path}. Restart Friday and try: 'What's on my calendar today?'")


if __name__ == "__main__":
    main()
