# F.R.I.D.A.Y.

**A voice-first personal AI assistant that runs on your own Windows PC.**

Say "Hey Friday" and talk to her like a person. She answers out loud, you can interrupt her mid-sentence, and she
can do things for you: look things up, set reminders, find and create files, read your screen, read and send your
email, and check your calendar. Her brain is a Groq language model; speech recognition runs locally on your machine;
your memory, contacts and settings stay on your PC.

> **New here?** Go to **[INSTALL.md](INSTALL.md)** for the step-by-step setup. Short version: run `install.bat`, then
> `friday --setup`, then `friday`.

---

## What she can do

### Talk naturally
- **Wake word.** "Hey Friday" wakes her. The listening runs on your PC (offline).
- **Real conversation.** After waking she keeps listening, so you don't repeat the wake word. She goes back to sleep
  after 60 seconds of silence, or when you say goodbye.
- **Interrupt her.** Talk over her at any point: she stops at once, and what you said becomes your next question.
- **Fast replies.** She starts speaking after the first sentence instead of waiting for the whole answer.
- **Follow-ups.** She remembers the conversation and what her tools just did, so "where did you save it?" works.
- **Honest about facts.** For things that change (who runs a company, prices, scores) she checks the web first. If you
  push back on an answer, she re-checks, then either holds her ground or corrects herself.
- **Morning briefing.** The first time you wake her each day she summarizes the date, weather, reminders, calendar,
  email and news. Any part that isn't set up is skipped.

### Find out things
- Web search (no key needed), weather for any city, and news headlines (free Guardian and NewsAPI keys).

### Remember and remind
- **Memory.** Tell her lasting facts about you and she remembers them across restarts. Ask her to forget any of them.
- **Reminders and timers.** They survive restarts, and she speaks up by herself when one is due. She also tells you
  about any she missed while she was off.

### Use your computer
- Open apps and websites, or search in your browser.
- **Find files** even when you describe the name loosely. She ignores spaces, hyphens, case and extensions,
  understands numbers said aloud, ranks the best match first, labels close guesses as guesses, and searches your whole
  user folder if the usual places have nothing.
- Create folders and text files (she never overwrites, and refuses file types Windows would run), and move files after
  your spoken approval.
- Take screenshots, and **look at your screen** to read an error or describe what's open.
- Control volume, mute and media keys, and lock the screen. Report battery, memory and disk space.
- Read your clipboard, or put text on it.
- Type for you, press an approved list of keys and shortcuts, and scroll. Each of these needs your spoken "yes".

---

## Email

Friday can read, summarize and send email. There are two ways to connect an account; the first is the easy one.

| | **App password (recommended)** | **Google sign-in** |
|---|---|---|
| Set up with | `friday --email` | `.venv\Scripts\python Voice\google_login.py` (see [INSTALL.md](INSTALL.md)) |
| Works with | Gmail, Outlook/Hotmail, Yahoo, iCloud, and custom servers | Gmail only |
| You provide | Your address and an app password | A Google Cloud project and a browser sign-in |
| Also gives you | Mail only | Mail **and Calendar** |

If both are set up, the app-password mailbox is used for email. Calendar always uses the Google sign-in.

### Reading and summarizing
- Ask for your unread mail, the latest messages, or a summary. She reads the newest first, up to 10 at a time, with
  roughly the first 1,200 characters of each when you ask for the text.
- You can search: by sender, recipient, subject, words in the message, read or unread, or how recent. Gmail accounts
  use Gmail's own search language.
- **Reading never changes your mail.** She opens the inbox read-only: nothing is marked as read, moved or deleted, and
  attachments aren't downloaded.

### Sending
- She emails **only people you've saved as contacts**. Add one by voice: she asks which email service they use
  (gmail, yahoo...), you spell only the part before the @, and she spells the whole address back before saving.
- Before anything is sent she **reads back the recipient, the subject and the whole message** and waits for a clear
  "yes". Any "no", "wait" or "not sure" cancels it.
- Limits: up to 3 recipients, a 600-character plain-text message, 10 emails a day. Every email sent is logged.
- She can't send attachments, reply inside an existing thread (a reply goes out as a new email), or delete mail.
- Text inside an email is treated as data, never as instructions, so a message can't make her do anything.

---

## Calendar

Calendar uses your Google account and needs the one-time Google sign-in described in [INSTALL.md](INSTALL.md).

- **See what's coming.** Ask about today or the next few days (up to 14). She reads out up to 15 events, in order, with
  start times. All-day events are included.
- **Add an event.** Give her a title, a start time (a clock time for today or tomorrow, or a date and time) and
  optionally how long it lasts (default one hour). She reads the details back and adds it only after you say yes.
- She works with your **main calendar** only. She can't edit or delete existing events, invite people, or see other
  calendars. Calendar events also feed the morning briefing.

---

## Safety

Friday is built so that she only does what **you** ask.

- Only your spoken words are instructions. Text on your screen, in an email, on a web page, in a file or on the
  clipboard is treated as data and never obeyed.
- Typing, key presses, moving files, sending email and adding calendar events each need a spoken "yes" that can't be
  mistaken for something else.
- The riskier tools aren't even offered to the model unless what you said suggests them, and she refuses any tool that
  wasn't offered.
- File actions stay inside your user folder.
- Your keys and passwords are never printed or logged, and personal data files are excluded from git.

One thing to know: an email **app password** can do more than Friday does (providers don't offer a read-and-send-only
one), and it's stored in plain text in `Voice\Config.py` on your PC. Keep that file private, and revoke the app
password at your provider if you stop using Friday.

---

## The `friday` command

| Command | What it does |
|---|---|
| `friday` | Start Friday |
| `friday --setup` | Enter or change your API keys |
| `friday --email` | Set up email with an app password |
| `friday --check` | Diagnose problems. Add `--online` to also test your Groq key and email login |
| `friday --version` | Show the version |

---

## What's under the hood

- **Brain:** Groq (`gpt-oss-120b`) with automatic fallback to other models, plus tool routing to keep each request small
  enough for Groq's free tier.
- **Ears:** Whisper speech recognition, running locally. **Voice:** the offline Windows voice, or ElevenLabs if you
  prefer.
- **Tools:** over 30 small tools (search, files, reminders, email, calendar, screen, keyboard and more) that the
  model calls on your behalf.

```
friday_cli.py     the `friday` command: setup, diagnostics, launcher
Voice/            the voice loop: Main, Brain, Stt, Tts, BargeIn, Config.py
Tools/            what she can do: Mail, Google, Contacts, Reminders, PCControl, Vision, Briefing, ...
install.bat       installs everything and creates the command
```

## Limits to know about

- **Windows only.** Several features (volume keys, typing, screen lock) use Windows.
- **Groq's free tier has daily and per-minute token limits.** She tells you how long to wait if you hit one. A paid
  Groq tier removes the limit.
- She can't click the mouse, and she can't reach other drives unless you tell her which folder to search.
- **Your setup matters.** How well voice recognition works depends on your microphone and room, and your mail
  provider's and Google's own rules apply to those connections.

## Your data

Your memory, reminders, contacts, mail log and Google login are plain files in this folder, excluded from git. Delete
them whenever you like. Nothing is uploaded except what each request needs: your question goes to Groq, and screen
captures go to Groq only when you ask about your screen.
