import os
import queue
import tempfile
import time

import numpy as np
import sounddevice as sd
import scipy.io.wavfile as wav
import whisper

from Config import WHISPER_MODEL, SAMPLE_RATE

print(
    f"For Speech to text conversion, we are loading whisper {WHISPER_MODEL} model...",
    end="",
    flush=True
)

MODEL = whisper.load_model(WHISPER_MODEL)

try:  # half precision only helps (and only works) on a GPU; this also silences the CPU warning
    import torch
    FP16 = torch.cuda.is_available()
except ImportError:
    FP16 = False

print("Done")

# Speech threshold measured from the room's own noise on the first recording,
# so it adapts to any mic instead of a hardcoded value.
MIN_THRESHOLD = 800
MAX_THRESHOLD = 2500
CALIBRATION_CHUNKS = 3  # 0.6 s of ambient noise
_threshold = None


def record_audio(
    sample_rate=SAMPLE_RATE,
    silence_threshold=None,
    silence_duration=1.2,
    max_wait=None,      # give up if nobody speaks within this many seconds
    max_seconds=30,     # hard cap on one utterance
    verbose=True,
):
    """Returns the recorded int16 audio, or an empty array if nobody spoke in time."""
    global _threshold

    log = print if verbose else (lambda *a, **k: None)
    log("[STT] Waiting for speech...")

    q = queue.Queue()
    audio_chunks = []
    silence_chunks = 0

    chunk_duration = 0.2
    chunk_samples = int(sample_rate * chunk_duration)

    def callback(indata, frames, _time_info, status):
        q.put(indata.copy())

    calibrating = silence_threshold is None and _threshold is None
    ambient = []
    wait_deadline = time.monotonic() + max_wait if max_wait else None
    record_deadline = None

    with sd.InputStream(
        samplerate=sample_rate,
        channels=1,
        dtype='int16',
        blocksize=chunk_samples,
        callback=callback
    ):

        started = False

        while True:

            try:
                chunk = q.get(timeout=0.5)
            except queue.Empty:
                chunk = None

            if chunk is None:
                if not started and wait_deadline and time.monotonic() > wait_deadline:
                    return np.array([], dtype=np.int16)
                continue

            volume = np.abs(chunk).mean()

            if calibrating:
                ambient.append(volume)
                if len(ambient) >= CALIBRATION_CHUNKS:
                    _threshold = float(min(MAX_THRESHOLD, max(MIN_THRESHOLD, np.mean(ambient) * 3)))
                    calibrating = False
                    log(f"[STT] Calibrated speech threshold: {_threshold:.0f}")
                continue

            threshold = silence_threshold or _threshold

            # WAIT UNTIL USER SPEAKS
            if not started:

                if volume > threshold:

                    log("[STT] Speech detected")

                    started = True
                    record_deadline = time.monotonic() + max_seconds
                    audio_chunks.append(chunk)

                elif wait_deadline and time.monotonic() > wait_deadline:
                    return np.array([], dtype=np.int16)

                continue

            # RECORDING PHASE
            audio_chunks.append(chunk)

            if volume > threshold:
                silence_chunks = 0
            else:
                silence_chunks += 1

            # USER STOPPED SPEAKING, OR HIT THE LENGTH CAP
            if silence_chunks > silence_duration / chunk_duration:
                break
            if time.monotonic() > record_deadline:
                break

    log("[STT] Recording complete")

    if len(audio_chunks) == 0:
        return np.array([], dtype=np.int16)

    audio = np.concatenate(audio_chunks, axis=0)

    return audio.flatten()



def save_wave(audio, sample_rate=SAMPLE_RATE):

    temp = tempfile.NamedTemporaryFile(
        suffix=".wav",
        delete=False
    )

    wav.write(temp.name, sample_rate, audio)

    return temp.name



def transcribe(wav_path, prompt=None):

    result = MODEL.transcribe(wav_path, language="en", initial_prompt=prompt, fp16=FP16)

    return result["text"].strip()


def transcribe_audio(audio, prompt=None, sample_rate=SAMPLE_RATE):
    """Transcribe int16 audio straight from memory. Whisper only needs ffmpeg to decode
    files, so passing a float32 array at 16 kHz means ffmpeg isn't required."""
    samples = audio.astype(np.float32) / 32768.0
    if sample_rate != 16000:  # Whisper expects 16 kHz
        target = int(len(samples) * 16000 / sample_rate)
        samples = np.interp(np.linspace(0, len(samples) - 1, target),
                            np.arange(len(samples)), samples).astype(np.float32)
    result = MODEL.transcribe(samples, language="en", initial_prompt=prompt, fp16=FP16)
    return result["text"].strip()


def get_threshold():
    """The calibrated speech-volume threshold (None until the first recording)."""
    return _threshold


def listen_for_wake_phrase(max_wait=3, max_seconds=4):
    """Offline wake-word listening: wait for a short burst of speech, transcribe it
    locally with Whisper, return the lowercase text ('' if nothing was said)."""
    audio = record_audio(max_wait=max_wait, max_seconds=max_seconds,
                         silence_duration=0.8, verbose=False)
    if len(audio) == 0:
        return ""
    # the prompt nudges Whisper toward the wake phrase
    text = transcribe_audio(audio, prompt="Hey Friday.")
    return "" if is_garbage(text) else text.lower()

def is_garbage(text: str) -> bool:
    """Returns True if Whisper returned hallucinated garbage instead of real speech."""
    if not text or len(text.strip()) < 2:
        return True
    # Count non-latin characters
    non_latin = sum(1 for c in text if ord(c) > 591)
    if non_latin > len(text) * 0.3:   # More than 30% non-latin = garbage
        return True
    return False

def record_and_transcribe(max_wait=None):

    audio = record_audio(max_wait=max_wait)

    if len(audio) == 0:
        return ""

    text = transcribe_audio(audio)
    if is_garbage(text):
        print("[STT] Garbage detected, ignoring.")
        return ""

    return text
