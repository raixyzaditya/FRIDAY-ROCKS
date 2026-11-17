"""
Finds out why Friday's brain can't connect. Run from this folder:   python check_brain.py
Each step tests one layer, so the first FAIL line is the cause.
"""
import sys

import Brain
from Brain import client, MODELS, LLM_TOOLS


def step(label, fn):
    try:
        out = fn()
        print(f"[ OK ] {label}" + (f": {out}" if out else ""))
        return True
    except Exception as e:
        status = getattr(e, "status_code", None)
        print(f"[FAIL] {label}\n       {type(e).__name__}" + (f" (HTTP {status})" if status else "") + f": {e}")
        return False


def main():
    import httpx, openai
    print(f"openai {openai.__version__}, httpx {httpx.__version__}, python {sys.version.split()[0]}\n")

    if not step("API key is set", lambda: (_ for _ in ()).throw(ValueError("GROQ_API_KEY is empty"))
                if not Brain.GROQ_API_KEY else f"length {len(Brain.GROQ_API_KEY)}"):
        return
    step("Groq reachable and key accepted (list models)", lambda: f"{len(client.models.list().data)} models")

    for model in MODELS:
        step(f"{model}: plain chat",
             lambda m=model: client.chat.completions.create(
                 model=m, messages=[{"role": "user", "content": "Say hi in 3 words."}], max_tokens=200
             ).choices[0].message.content)
        step(f"{model}: with Friday's tools",
             lambda m=model: client.chat.completions.create(
                 model=m, messages=[{"role": "user", "content": "What's the weather in Delhi?"}],
                 tools=LLM_TOOLS, tool_choice="auto", max_tokens=400
             ).choices[0].message.tool_calls[0].function.name)
        step(f"{model}: streaming with tools",
             lambda m=model: sum(1 for _ in client.chat.completions.create(
                 model=m, messages=[{"role": "user", "content": "Tell me a short joke."}],
                 tools=LLM_TOOLS, tool_choice="auto", max_tokens=200, stream=True)))


if __name__ == "__main__":
    main()
