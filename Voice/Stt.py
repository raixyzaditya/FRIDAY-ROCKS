import os
import queue
import tempfile

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

print("Done")



def record_audio(
    sample_rate=SAMPLE_RATE,
    silence_threshold=1000,
    silence_duration=1.2
):

    print("[STT] Waiting for speech...")

    q = queue.Queue()

    audio_chunks = []

    silence_chunks = 0

    chunk_duration = 0.2
    chunk_samples = int(sample_rate * chunk_duration)

    def callback(indata, frames, time, status):
        q.put(indata.copy())

    with sd.InputStream(
        samplerate=sample_rate,
        channels=1,
        dtype='int16',
        blocksize=chunk_samples,
        callback=callback
    ):

        started = False

        while True:

            chunk = q.get()

            volume = np.abs(chunk).mean()

            # WAIT UNTIL USER SPEAKS
            if not started:

                if volume > silence_threshold:

                    print("[STT] Speech detected")

                    started = True
                    audio_chunks.append(chunk)

                continue

            # RECORDING PHASE
            audio_chunks.append(chunk)

            if volume > silence_threshold:
                silence_chunks = 0
            else:
                silence_chunks += 1

            # USER STOPPED SPEAKING
            if silence_chunks > silence_duration / chunk_duration:
                break

    print("[STT] Recording complete")

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



def transcribe(wav_path):

    result = MODEL.transcribe(wav_path,language="en")

    return result["text"].strip()

def is_garbage(text: str) -> bool:
    """Returns True if Whisper returned hallucinated garbage instead of real speech."""
    if not text or len(text.strip()) < 2:
        return True
    # Count non-latin characters
    non_latin = sum(1 for c in text if ord(c) > 591)
    if non_latin > len(text) * 0.3:   # More than 30% non-latin = garbage
        return True
    return False

def record_and_transcribe():

    audio = record_audio()

    if len(audio) == 0:
        return ""

    wav_path = save_wave(audio)

    try:
        text = transcribe(wav_path)


    finally:
        os.remove(wav_path)
    if is_garbage(text):
        print("[STT] Garbage detected, ignoring.")
        return ""

    return text