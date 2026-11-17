# Installing Friday

Follow this once to get Friday running on your own Windows PC. It takes about 15 minutes, most of it a download.
For what she can do, see the [README](README.md).

## 1. What you need first

- **Windows 10 or 11.** Friday uses Windows features, so Mac and Linux aren't supported.
- **Python 3.10 or newer.** Check with `python --version`. If you don't have it, install it from a terminal:
  ```
  winget install Python.Python.3.12
  ```
  Then open a **new** terminal so Python is found.
- **A microphone**, and speakers or headphones. Headphones work best if you want to interrupt her, because her own
  voice can leak into the microphone.
- **A free Groq API key.** Create an account at https://console.groq.com and make a key at
  https://console.groq.com/keys. This is Friday's brain. Keep the key private.
- **About 2 GB of free disk space** (the installed environment is roughly 1.2 GB), and an internet connection for the
  first install.

## 2. Get the project

Clone it or download it as a ZIP and unzip it somewhere permanent, for example `C:\Friday`. Don't move the folder
afterwards, because the `friday` command points to it.

## 3. Install

Double-click **`install.bat`** in the project folder, or run it from a terminal:

```
install.bat
```

It will:
1. find Python (and tell you how to get it if it can't),
2. create a private environment in `.venv` inside the folder,
3. install Friday and her libraries (**the first time this is a large download**, roughly 1 GB or more, for PyTorch
   and the Whisper speech model, so allow 5 to 15 minutes),
4. create `Voice\Config.py` from the example,
5. create the `friday` command and add it to **your user PATH only**. No administrator rights are needed, and nothing
   system-wide is changed.

Want to preview first? Run `install.bat -DryRun` and it prints what it would do without changing anything.

When it finishes, **open a new terminal.** The command only appears in windows opened after the install.

## 4. Enter your keys

```
friday --setup
```

- Paste your **Groq key** when asked. What you type is hidden.
- The two **news keys** are optional. Press Enter to skip, or get free keys from newsapi.org and
  open-platform.theguardian.com for headlines.
- It then asks whether to set up **email**. Answer `n` for now if you'd rather do that later (see section 6).

Your keys are saved only in `Voice\Config.py` on your PC.

## 5. Check and run

```
friday --check
```

Every line should say `OK`. Lines marked `WARN` are optional features that aren't set up yet. A `FAIL` line names the
problem and the fix. To also test that your Groq key works, run `friday --check --online`.

Then start her from any folder:

```
friday
```

The first start loads the speech model and takes a moment. When you see she is waiting, say **"Hey Friday"**.

---

## 6. Email (optional)

Friday can read, summarize and send your email. The simplest way uses an **app password**.

### What's an app password?
A separate password made just for Friday. You create it on your email provider's security page, and you can revoke it
at any time without changing your real password. Most providers require **two-step verification** to be turned on
first.

### Set it up
```
friday --email
```

It asks for two things only:
1. **Your email address.** Friday recognizes Gmail, Outlook/Hotmail, Yahoo and iCloud and fills in the mail servers
   herself. For any other provider she also asks for its IMAP and SMTP server names.
2. **Your app password.** What you type is hidden, and spaces (as Google shows them) are fine.

Before it asks for the password, Friday prints the link for creating one at your provider:

| Provider | Where to create an app password |
|---|---|
| Gmail | https://myaccount.google.com/apppasswords (turn on 2-Step Verification first) |
| Outlook / Hotmail | https://account.microsoft.com/security, under Advanced security options |
| Yahoo | https://login.yahoo.com/account/security |
| iCloud | https://appleid.apple.com, under Sign-In and Security |

Friday then **tests the login without sending or changing anything** and tells you whether reading and sending both
work. If a test fails, check the address and app password, then run `friday --email` again.

> **Outlook note:** Microsoft work and school accounts usually don't allow app passwords, and Microsoft's rules for
> personal accounts have been changing. If it won't connect, that's the likely cause.

### Using email
- Ask her to read or summarize your newest or unread mail, or to search for something.
- To send, **first save the person as a contact** by asking her to add them. She asks which email service they use,
  you spell the part before the @, and she spells the full address back letter by letter and waits for your "yes".
- Then ask her to email them. She reads back the recipient, subject and the whole message, and sends only after you say
  yes. Limits: 3 recipients, 600 characters, 10 emails a day, plain text, no attachments.
- Reading is read-only: she never marks mail as read, moves it or deletes it.

### Good to know
- The app password is stored in plain text in `Voice\Config.py` (excluded from git). An app password can do more than
  Friday does, so keep that file private and revoke the password if you stop using Friday.
- By default she emails **saved contacts only**. To allow any address you dictate, set `EMAIL_CONTACTS_ONLY = False`
  in `Voice\Config.py`. She still reads everything back first.

---

## 7. Calendar (optional)

Calendar needs a one-time **Google sign-in**, because Google only allows an app to see your calendar with your own
consent. It takes about 10 minutes. Gmail through this same sign-in is optional (use `friday --email` for mail if you
prefer).

### One-time Google setup
1. Go to https://console.cloud.google.com and **create a project**.
2. In **APIs & Services > Library**, enable the **Google Calendar API** (and the **Gmail API** if you want mail through
   Google instead of an app password).
3. In **APIs & Services > OAuth consent screen**, choose **External** and add your own Google address as a **Test user**.
4. In **APIs & Services > Credentials**, choose **Create credentials > OAuth client ID** and pick **Desktop app**.
   Download the JSON file.
5. Save that file as **`google_credentials.json`** in the project's top folder, next to `install.bat`.
6. Install the Google libraries. Run this in the project folder:
   ```
   .venv\Scripts\python -m pip install -e ".[google]"
   ```
   Use exactly this `.venv\Scripts\python` (not a plain `pip` or `python`), so the libraries go into Friday's own
   environment, where she can find them.
7. Sign in, again with Friday's own Python:
   ```
   .venv\Scripts\python Voice\google_login.py
   ```
   Your browser opens. Choose your account and approve access. Because this is your own app, Google shows an
   **"unverified app"** warning. That's expected: click **Advanced** and continue.

Restart Friday afterwards. Run `friday --check` and look for **Google is connected**.

### Using the calendar
- Ask what's on today, or over the next few days (up to 14). She reads up to 15 events with their times.
- Ask her to add an event with a title, a start time (a clock time, or a date and time) and, optionally, how long it
  lasts (default one hour). She reads the details back and adds it only after you say yes.
- She works with your **main calendar** only. She can't edit or delete existing events, invite people or read other
  calendars.
- Calendar events are included in the morning briefing.

### Good to know
- While your Google app is in "Testing" status, Google may ask you to sign in again about **every 7 days**. Re-run
  `.venv\Scripts\python Voice\google_login.py` when she tells you Google isn't connected.
- Only the Google addresses you added as **Test users** can sign in.
- The sign-in file `google_token.json` and `google_credentials.json` stay on your PC and are excluded from git.
- Everyone who installs Friday needs **their own** Google project and sign-in. Never share these two files: they give
  access to your account.

---

## Settings

Most people never need these. They live in `Voice\Config.py` (see `Voice\Config.example.py` for the full list).

| Setting | What it does |
|---|---|
| `GROQ_API_KEY` | Friday's brain. Set with `friday --setup` |
| `NEWS_API_KEY`, `GAURDIAN_API_KEY` | Optional news keys (note the spelling of the second name) |
| `WAKE_WORDS` | The phrases that wake her |
| `WAKE_ENGINE` | `"whisper"` (offline, default) or `"google"` (online) |
| `WHISPER_MODEL` | Speech accuracy vs speed: `tiny`, `base` (default), `small`, `medium` |
| `BARGE_IN` | `True` lets you interrupt her. Set `False` if she interrupts herself |
| `BARGE_IN_DEBUG` | `True` prints live microphone levels to tune interruptions |
| `AUTO_BRIEFING` | `True` gives a spoken briefing the first time she wakes each day |
| `EMAIL_CONTACTS_ONLY` | `True` (default): email only saved contacts |
| `TTS_ENGINE` | `"pyttsx3"` (offline, default) or `"elevenlabs"` (needs `.venv\Scripts\python -m pip install -e ".[elevenlabs]"` and a key) |
| `FALLBACK_MODELS` | Backup Groq models to try if the main one is busy |
| `VISION_MODEL` | The Groq model used when she looks at your screen |

Email settings (`EMAIL_ADDRESS`, `EMAIL_APP_PASSWORD`, `EMAIL_PROVIDER`) are written for you by `friday --email`.

## Troubleshooting

Start with `friday --check`. It marks anything broken and tells you the fix.

| Problem | What to do |
|---|---|
| `friday` is not recognized | Open a **new** terminal. If it still isn't found, run `install.bat` again |
| `Config.py has a typo on line N` | A key is missing its quotes. Run `friday --setup` and retype it |
| Libraries are missing | Run `install.bat` again, or `.venv\Scripts\python -m pip install -e .` in the project folder |
| She never wakes up | Check the Microphone line in `friday --check`, set your default recording device in Windows, and say "Hey Friday" clearly |
| She interrupts herself | Use headphones, or set `BARGE_IN = False` |
| "I've hit Groq's rate limit" | The free tier has daily and per-minute limits. She says how long to wait. A paid Groq tier removes it |
| Email login fails | Make sure it's an **app password**, not your normal one, and that two-step verification is on. Run `friday --email` again |
| "Google isn't connected" | Run `.venv\Scripts\python Voice\google_login.py`. In Testing status this is needed about every 7 days |
| The first start is slow | It's loading the speech model. Later starts are faster |

## Uninstall

```
uninstall.bat
```

This removes the `friday` command and its PATH entry. It does **not** delete the project folder, the `.venv`, your
`Config.py`, or your data (memory, reminders, contacts, mail log, Google sign-in). Delete those yourself if you want
them gone, and revoke any email app password at your provider.
