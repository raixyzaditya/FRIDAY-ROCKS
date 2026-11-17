# Copy this file to Config.py (which is gitignored) and fill in your own keys.

# LLM (Groq, OpenAI-compatible endpoint)
GROQ_API_KEY = ""

# Tools
NEWS_API_KEY = ""
GAURDIAN_API_KEY = ""

# Voice
WAKE_WORDS = ["hey friday", "friday"]
WHISPER_MODEL = "base"      # tiny / base / small / medium
SAMPLE_RATE = 16000
RECORD_SECONDS = 5

# Wake word: "whisper" (offline, local) or "google" (online)
WAKE_ENGINE = "whisper"
# Interrupt Friday mid-answer by talking over her; what you say becomes your next question.
# There's no echo cancellation: headphones are the most reliable. Set False if she interrupts herself.
BARGE_IN = True
BARGE_IN_DEBUG = False  # True prints live mic levels while Friday speaks, to tune interruptions

# On the first wake of each day, give a spoken briefing (weather, reminders, calendar, email, news).
AUTO_BRIEFING = True
# Optional: backup Groq models to try, in order, when the main one is busy or rate-limited.
# FALLBACK_MODELS = ["openai/gpt-oss-20b", "llama-3.1-8b-instant"]
# Optional: a Groq vision model for "what's on my screen?"
# VISION_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"

# Email (read and send mail): set up with  friday --email  rather than editing these by hand.
# It uses an APP PASSWORD (a separate password for Friday, revocable any time), not your normal one.
EMAIL_ADDRESS = ""
EMAIL_APP_PASSWORD = ""
EMAIL_PROVIDER = ""          # filled in automatically: gmail, outlook, yahoo, icloud, or custom
# Only for providers Friday doesn't know (EMAIL_PROVIDER = "custom"):
# EMAIL_IMAP_HOST = "imap.example.com"
# EMAIL_SMTP_HOST = "smtp.example.com"

# Email safety: True = Friday only emails saved contacts (saving one needs a spelled-out spoken yes).
# False = she can also email any address you dictate, after reading it back.
EMAIL_CONTACTS_ONLY = True

# TTS: "pyttsx3" (offline) or "elevenlabs"
TTS_ENGINE = "pyttsx3"
ELEVENLABS_API_KEY = ""
ELEVENLABS_VOICE_ID = ""
