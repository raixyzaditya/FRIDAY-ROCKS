"""
Barge-in: lets you interrupt Friday mid-answer by talking over her, like in a real conversation.

While Friday speaks, a monitor watches the mic. When you talk loudly enough for ~0.4 s it
  1. cuts Friday off,
  2. keeps recording until you finish your sentence (including the first words you spoke
     before it triggered), and
  3. hands that audio back so it becomes your next question.

There is no echo cancellation. To avoid Friday interrupting herself through the speakers, the
monitor measures how loud her own voice sounds in the mic and only reacts to something clearly
louder. Headphones are still the most reliable setup. Turn it off with BARGE_IN = False in Config.py.
"""

import threading
from collections import deque

import numpy as np
import sounddevice as sd

import Stt
import Tts
import Config
from Config import SAMPLE_RATE

DEBUG = getattr(Config, "BARGE_IN_DEBUG", False)  # print live mic levels while Friday speaks

CHUNK_SECONDS = 0.1
LOUDNESS_FACTOR = 1.5   # a trigger must beat this multiple of the normal speech threshold...
ECHO_FACTOR = 2.0       # ...and this multiple of how loud Friday's own voice measures in the mic
HOLD_SECONDS = 0.4      # it must stay that loud this long, so a cough or a click is ignored
PRE_ROLL_CHUNKS = 6     # keep 0.6 s from before the trigger so your first words aren't lost
END_SILENCE = 1.0       # your interruption is over after this much quiet
MAX_CAPTURE = 15        # seconds, hard cap on one interruption
ECHO_WINDOW_CHUNKS = 40  # about 4 s of history used to measure Friday's own loudness
WARMUP_CHUNKS = 5        # audio samples of her own voice needed before interruptions are allowed (~0.9 s in)
IDLE_RESET_CHUNKS = 10   # forget her loudness after 1 s of silence (not just the gap between sentences)


class BargeInMonitor:
    """Use as a context manager around the code that speaks the answer.

    After the block: .triggered tells whether you interrupted, and .audio holds what you said
    (int16 samples) once wait_capture() has returned."""

    def __init__(self):
        self.triggered = False
        self.audio = None
        self.captured = threading.Event()
        self._stop = threading.Event()
        self._thread = None

    def __enter__(self):
        self.triggered = False
        self.audio = None
        self.captured.clear()
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *exc):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)
        return False

    def wait_capture(self, timeout=MAX_CAPTURE + 5):
        """If you interrupted, wait until you've finished speaking. Returns immediately otherwise."""
        if self.triggered:
            self.captured.wait(timeout)

    def _run(self):
        n = int(SAMPLE_RATE * CHUNK_SECONDS)
        hold_chunks = max(1, int(HOLD_SECONDS / CHUNK_SECONDS))
        floor = Stt.get_threshold() or 1000  # normal "someone is speaking" volume
        recent = deque(maxlen=ECHO_WINDOW_CHUNKS)  # volumes while Friday was speaking
        pre_roll = deque(maxlen=PRE_ROLL_CHUNKS)
        loud_chunks = idle_chunks = ticks = 0
        armed = False
        print(f"[BargeIn] Monitor running (speech floor {floor:.0f}).")
        try:
            with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="int16", blocksize=n) as stream:
                while not self._stop.is_set():
                    chunk, _overflow = stream.read(n)
                    volume = float(np.abs(chunk).mean())
                    pre_roll.append(chunk)

                    if not Tts.queue_speaking():
                        loud_chunks = 0
                        idle_chunks += 1
                        if idle_chunks >= IDLE_RESET_CHUNKS:  # a real pause, not just the gap between sentences
                            recent.clear()
                            armed = False
                        continue
                    idle_chunks = 0
                    if not armed:
                        armed = True
                        print("[BargeIn] Friday is speaking: learning her volume, then you can interrupt.")

                    # Friday's own voice level, from audio older than the trigger window. Until we have
                    # a second or so of it we can't tell her echo from you, so just listen and learn.
                    older = list(recent)[:-hold_chunks] if len(recent) > hold_chunks else []
                    recent.append(volume)
                    if len(older) < WARMUP_CHUNKS:
                        loud_chunks = 0
                        continue
                    echo = float(np.percentile(older, 90))
                    level = max(floor * LOUDNESS_FACTOR, echo * ECHO_FACTOR)
                    ticks += 1
                    if DEBUG and ticks % 5 == 0:  # twice a second
                        print(f"[BargeIn] mic={volume:.0f}  needed>{level:.0f}  (her echo~{echo:.0f}, floor {floor:.0f})")

                    loud_chunks = loud_chunks + 1 if volume > level else 0
                    if loud_chunks >= hold_chunks:
                        print("[BargeIn] Interrupted.")
                        self.triggered = True
                        Tts.stop_speaking()
                        self._capture(stream, n, floor, list(pre_roll))
                        return
        except Exception as e:
            print(f"[BargeIn] Monitor stopped: {e}")
        finally:
            self.captured.set()

    def _capture(self, stream, n, floor, frames):
        """Record the rest of the user's interruption until they stop talking."""
        end_chunks = int(round(END_SILENCE / CHUNK_SECONDS))
        max_chunks = int(round(MAX_CAPTURE / CHUNK_SECONDS))
        silent = taken = 0
        while not self._stop.is_set() and taken < max_chunks:
            chunk, _overflow = stream.read(n)
            frames.append(chunk)
            taken += 1
            silent = 0 if np.abs(chunk).mean() > floor else silent + 1
            if silent >= end_chunks:
                break
        self.audio = np.concatenate(frames).flatten()
