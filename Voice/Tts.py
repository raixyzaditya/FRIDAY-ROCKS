"""
F.R.I.D.A.Y. — Tts.py
Confirmed working voices on this machine:
  [0] Microsoft Hazel  — English UK   ← using this (best sounding)
  [1] Microsoft David  — English US
  [2] Microsoft Zira   — English US
"""

import pyttsx3
import threading
from Config import TTS_ENGINE, ELEVENLABS_API_KEY, ELEVENLABS_VOICE_ID

is_speaking = False
_lock = threading.Lock()

VOICE_INDEX = 0  # Hazel — change to 1 (David) or 2 (Zira) if you prefer


def _speak_pyttsx3(text: str):
    global is_speaking
    with _lock:
        try:
            is_speaking = True
            engine = pyttsx3.init()
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


def speak(text: str, blocking: bool = True):
    """
    blocking=True  → waits until speech finishes (default, use this always)
    blocking=False → fires in background, returns immediately
    """
    if not text or not text.strip():
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


def stop_speaking():
    global is_speaking
    is_speaking = False
    print("[TTS] Stopped.")