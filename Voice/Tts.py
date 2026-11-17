"""
F.R.I.D.A.Y. — Tts.py
Confirmed working voices on this machine:
  [0] Microsoft Hazel  — English UK   ← using this (best sounding)
  [1] Microsoft David  — English US
  [2] Microsoft Zira   — English US
"""

import pyttsx3
import queue
import re
import threading
from Config import TTS_ENGINE, ELEVENLABS_API_KEY, ELEVENLABS_VOICE_ID

is_speaking = False
_lock = threading.Lock()
_current = {"engine": None}       # the pyttsx3 engine that is talking right now
_interrupted = threading.Event()  # set by stop_speaking(); queued speech is dropped while set

VOICE_INDEX = 0  # Hazel — change to 1 (David) or 2 (Zira) if you prefer


def _speak_pyttsx3(text: str):
    global is_speaking
    with _lock:
        try:
            is_speaking = True
            engine = pyttsx3.init()
            _current["engine"] = engine  # so stop_speaking() can cut it off
            voices = engine.getProperty('voices')
            engine.setProperty('voice', voices[VOICE_INDEX].id)
            engine.setProperty('rate', 165)
            engine.setProperty('volume', 1.0)
            print(f"[Friday Speaking] {text}")
            engine.say(text)
            engine.runAndWait()
            engine.stop()
        except Exception as e:
            print(f"[TTS] Error: {e}")
        finally:
            _current["engine"] = None
            is_speaking = False


def _speak_elevenlabs(text: str):
    global is_speaking
    try:
        import tempfile, os
        from elevenlabs.client import ElevenLabs
        import pygame

        client = ElevenLabs(api_key=ELEVENLABS_API_KEY)
        audio_bytes = b"".join(client.text_to_speech.convert(
            voice_id=ELEVENLABS_VOICE_ID,
            model_id="eleven_multilingual_v2",
            text=text
        ))

        tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
        tmp.write(audio_bytes)
        tmp.close()

        is_speaking = True
        print(f"[Friday Speaking] {text}")
        pygame.mixer.init()
        pygame.mixer.music.load(tmp.name)
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            pygame.time.Clock().tick(10)
        pygame.mixer.quit()
        os.unlink(tmp.name)

    except Exception as e:
        print(f"[TTS] ElevenLabs error: {e} — falling back to pyttsx3")
        _speak_pyttsx3(text)
    finally:
        is_speaking = False


def _clean(text: str) -> str:
    """Strip markdown symbols and URLs so they aren't read out loud."""
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"[*_`#>~|]+", "", text)
    return " ".join(text.split())


_queue = queue.Queue()
_worker = None
_worker_lock = threading.Lock()


def _drain():
    while True:
        sentence = _queue.get()
        try:
            if not _interrupted.is_set():
                _queue_active.set()
                speak(sentence)
        except Exception as e:
            print(f"[TTS] Queue error: {e}")
        finally:
            _queue_active.clear()
            _queue.task_done()


_queue_active = threading.Event()  # set while a queued answer sentence is being spoken


def queue_speaking() -> bool:
    """True only while Friday is speaking a queued answer (not a confirmation prompt)."""
    return _queue_active.is_set()


def speak_queued(text: str):
    """Returns immediately; sentences are spoken in order by a background worker.
    Lets Friday start talking while the LLM is still generating the rest of the answer."""
    global _worker
    if _interrupted.is_set():
        return  # the user cut Friday off; drop the rest of this answer
    with _worker_lock:
        if _worker is None:
            _worker = threading.Thread(target=_drain, daemon=True)
            _worker.start()
    _queue.put(text)


def wait_idle():
    """Block until everything passed to speak_queued() has been spoken."""
    _queue.join()


def speak(text: str, blocking: bool = True):
    """
    blocking=True  → waits until speech finishes (default, use this always)
    blocking=False → fires in background, returns immediately
    """
    text = _clean(text or "")
    if not text:
        return

    def _run():
        if TTS_ENGINE == "elevenlabs":
            _speak_elevenlabs(text)
        else:
            _speak_pyttsx3(text)

    if blocking:
        _run()
    else:
        threading.Thread(target=_run, daemon=False).start()


def is_interrupted() -> bool:
    return _interrupted.is_set()


def reset_interrupt():
    """Call at the start of each new turn so Friday can speak again after being interrupted."""
    _interrupted.clear()


def stop_speaking():
    """Cut Friday off mid-sentence and drop everything still queued."""
    global is_speaking
    _interrupted.set()
    while True:  # drop queued sentences, keeping the join() counter balanced
        try:
            _queue.get_nowait()
            _queue.task_done()
        except queue.Empty:
            break
    engine = _current["engine"]
    if engine is not None:
        try:
            engine.stop()
        except Exception as e:
            print(f"[TTS] Could not stop engine: {e}")
    try:  # ElevenLabs playback
        import pygame
        if pygame.mixer.get_init():
            pygame.mixer.music.stop()
    except Exception:
        pass
    is_speaking = False
    print("[TTS] Stopped.")