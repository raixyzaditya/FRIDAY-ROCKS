"""
Quick TTS test — run this standalone to check if pyttsx3 works at all.
python test_tts.py
"""
import pyttsx3
import time

print("Testing pyttsx3...")
engine = pyttsx3.init()
voices = engine.getProperty('voices')
print(f"Found {len(voices)} voices:")
for i, v in enumerate(voices):
    print(f"  [{i}] {v.name} — {v.id}")

engine.setProperty('rate', 165)
engine.setProperty('volume', 1.0)

# Use voice index 0 first
engine.say("Hello. I am Friday. This is a test.")
engine.runAndWait()
print("Done. Did you hear it?")