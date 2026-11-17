

import re
import time
from datetime import datetime

import Config
from Stt import record_and_transcribe, listen_for_wake_phrase, transcribe_audio, is_garbage
from Brain import ask_friday
from Tts import speak, speak_queued, wait_idle, reset_interrupt, is_interrupted
from BargeIn import BargeInMonitor
from Tools import Reminders, Briefing
from Config import WAKE_WORDS

# Optional Config.py settings, so an older Config.py keeps working:
#   WAKE_ENGINE = "whisper" (offline, default) or "google" (online, lighter on the CPU)
#   BARGE_IN    = True (default) lets you interrupt Friday by talking over her (see BargeIn.py)
WAKE_ENGINE = getattr(Config, "WAKE_ENGINE", "whisper")
BARGE_IN = getattr(Config, "BARGE_IN", True)
AUTO_BRIEFING = getattr(Config, "AUTO_BRIEFING", True)  # spoken briefing on the first wake of each day

IDLE_TIMEOUT = 60     # seconds of silence in active mode before Friday goes back to sleep
LISTEN_WINDOW = 8     # how long each listen waits for speech before re-checking the idle timer


def startup_message() -> str:
    hour = datetime.now().hour
    greeting = "Good morning" if hour < 12 else "Good afternoon" if hour < 18 else "Good evening"
    return f"{greeting}, boss. I'm listening."


# Whole-utterance matches only, so "stop the music" or "how does sleep work" don't put Friday to sleep.
SLEEP_PHRASES = {"stop", "bye", "goodbye", "sleep", "go to sleep", "that's all", "thats all",
                 "that is all", "good night", "goodnight"}

def _normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", text.lower())


def listen_for_wake_word() -> bool:
    """
    Listens passively in short bursts.
    Returns True only when a wake word is heard.
    """
    if WAKE_ENGINE != "google":
        # Offline: Whisper runs locally, and only when the mic hears speech.
        heard = _normalize(listen_for_wake_phrase())
        if heard:
            print(f"[Wake] Heard: '{heard}'")
        return any(_normalize(word) in heard for word in WAKE_WORDS)

    import speech_recognition as sr
    recognizer = sr.Recognizer()
    recognizer.energy_threshold = 300
    recognizer.dynamic_energy_threshold = True
    with sr.Microphone() as source:
        recognizer.adjust_for_ambient_noise(source, duration=0.3)
        try:
            audio = recognizer.listen(source, timeout=3, phrase_time_limit=3)
        except sr.WaitTimeoutError:
            return False

    try:
        heard = recognizer.recognize_google(audio).lower()
        print(f"[Wake] Heard: '{heard}'")
        for word in WAKE_WORDS:
            if word in heard:
                return True
    except sr.UnknownValueError:
        pass
    except sr.RequestError:
        print("[Wake] Google STT unavailable, retrying...")

    return False



def listen_for_command() -> str:
    
    print("[Friday] Listening for your command...")
    text = record_and_transcribe(max_wait=LISTEN_WINDOW)
    return text.strip() if text else ""



def is_sleep_command(text: str) -> bool:
    """Returns True if the user wants Friday to go back to sleep."""
    t = re.sub(r"[^a-z' ]", "", text.lower()).strip()
    t = re.sub(r"^(ok|okay|alright|hey friday|friday)\s+", "", t)
    return t in SLEEP_PHRASES or t.startswith(("bye", "goodbye", "go to sleep"))



def respond(text: str):
    """Answer `text` out loud, speaking each sentence as it is generated.

    If the user talks over Friday, she stops at once and this returns what they said, so the
    caller can treat it as the next question. Returns None when she finished uninterrupted."""
    reset_interrupt()
    try:
        return _respond(text)
    finally:
        reset_interrupt()  # otherwise a reminder firing later would be dropped as "interrupted"


def _respond(text: str):
    if not BARGE_IN:
        reply = ask_friday(text, on_sentence=speak_queued)
        print(f"[Friday]  {reply}\n")
        wait_idle()
        return None

    with BargeInMonitor() as monitor:
        reply = ask_friday(text, on_sentence=speak_queued, should_stop=is_interrupted)
        if reply:
            print(f"[Friday]  {reply}\n")
        wait_idle()
        monitor.wait_capture()  # if the user cut in, let them finish their sentence

    if not monitor.triggered or monitor.audio is None or len(monitor.audio) == 0:
        return None
    print("[Friday]  (interrupted, listening...)")
    heard = transcribe_audio(monitor.audio)
    return None if is_garbage(heard) else heard.strip()


def maybe_brief():
    """On the first wake of each day, speak the daily briefing. Returns what the user said if they
    interrupted it (to be used as their first question), otherwise None."""
    if not (AUTO_BRIEFING and Briefing.briefing_due()):
        return None
    Briefing.mark_briefed()  # marked first, so a crash mid-briefing can't make it repeat all day
    return respond("Give me my daily briefing.")


def run():
    Reminders.start_scheduler(speak_queued)  # reminders and timers speak up on their own
    print("=" * 50)
    print("  F.R.I.D.A.Y.  —  Phase 1 Voice Loop")
    print("=" * 50)
    print(f"Silent boot. Waiting for wake word: {WAKE_WORDS}")
    print(f"Wake engine: {WAKE_ENGINE} | Barge-in (interrupt her): {'ON' if BARGE_IN else 'OFF'}")
    print("=" * 50 + "\n")

    while True:
        try:
            
            print("[Mode] Sleeping — say 'Hey Friday' to wake me up...")
            wake_detected = listen_for_wake_word()

            if not wake_detected:
                continue  

            
            print("\n[Friday] Wake word detected! Entering active mode.")
            speak(startup_message())


            print("[Mode] Active — talk freely. Say 'bye' to put me to sleep.\n")

            last_activity = time.monotonic()
            pending = None  # what the user said while interrupting Friday: the next turn, no listening needed

            pending = maybe_brief()  # first wake of the day
            if pending:
                print(f"[You]     {pending}")

            while True:

                text = pending or listen_for_command()
                pending = None

                if not text:
                    if time.monotonic() - last_activity > IDLE_TIMEOUT:
                        speak("Going quiet. Say Hey Friday when you need me.")
                        print("[Mode] Idle timeout, going back to sleep...\n")
                        break
                    continue

                print(f"[You]     {text}")

                
                if is_sleep_command(text):
                    speak("Going to sleep. Say Hey Friday whenever you need me.")
                    print("[Mode] Going back to sleep...\n")
                    break  

                
                print("[Friday]  Thinking...")
                # Sentences are spoken as they stream in, so Friday starts talking before the answer is complete.
                pending = respond(text)
                if pending:
                    print(f"[You]     {pending}")
                last_activity = time.monotonic()

            

        except KeyboardInterrupt:
            print("\n[Friday] Shutting down. Goodbye.")
            speak("Shutting down. Goodbye.")
            break

        except Exception as e:
            print(f"[Error] {e}")
            time.sleep(1)
            continue


if __name__ == "__main__":
    run()