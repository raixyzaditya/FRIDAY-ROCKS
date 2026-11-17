import sys
import os
import json

from Config import GROQ_API_KEY
from openai import OpenAI
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from Tools.ToolRegistry import TOOLS, run_tool

client = OpenAI(api_key=GROQ_API_KEY, base_url="https://api.groq.com/openai/v1")
MODEL = "openai/gpt-oss-120b"

SYSTEM_PROMPT = """
You are F.R.I.D.A.Y. — a highly intelligent personal AI assistant.
You are very expert in physics, maths, chemistry, Laws, Computer science and general knowledge, automobiles like Mercedes, BMW, Toyota and very much more. You are ultimate.
You were built by your user for their own personal use.

Your personality:
- Smart, direct, and concise. No fluff.
- You speak like a sharp, confident assistant — not a corporate chatbot.
- You address the user casually. No "Certainly!" or "Of course!".
- Keep responses short when spoken aloud (2-4 sentences max unless asked for more).
- You can be witty but you always prioritise being useful.

Your capabilities:
- Answer questions using your knowledge and hold a conversation within this session
- Help with coding, reasoning, planning, writing and general problem solving
- Use tools: web search, news, weather, open apps, search files, take screenshots,
  create folders, and move files (the user is asked to confirm moves)

Tool rules:
- Use a tool whenever the user asks for live information or wants something done on the PC.
- For multi-step requests, call the tools one after another until everything is done.
- Do not call a tool for things you can answer from knowledge.
- Never claim you did something unless a tool result confirms it.
- If a tool reports an error, tell the user plainly what went wrong.

When you receive tool results (news/weather/search):
- Summarise naturally for speaking aloud — conversational, not robotic
- Don't read out bullet numbers like "1, 2, 3" — weave it into sentences
- Focus on what is most useful and interesting for the user to hear

Future capabilities: shopping assistance, home automation via Raspberry Pi.

If asked something you don't know, say so directly — don't make things up.
"""

MAX_HISTORY = 10
MAX_TOOL_STEPS = 4
conversation_history = []

LLM_TOOLS = [{"type": "function", "function": t} for t in TOOLS]


def _trim_history():
    """Keep the last MAX_HISTORY messages, always starting on a user message."""
    global conversation_history
    conversation_history = conversation_history[-MAX_HISTORY:]
    while conversation_history and conversation_history[0]["role"] != "user":
        conversation_history.pop(0)


def ask_friday(question: str) -> str:
    global conversation_history
    print(f"[Brain] User: {question}")

    conversation_history.append({"role": "user", "content": question})
    _trim_history()
    messages = [{"role": "system", "content": SYSTEM_PROMPT}, *conversation_history]

    try:
        for step in range(MAX_TOOL_STEPS):
            response = client.chat.completions.create(
                model=MODEL,
                messages=messages,
                tools=LLM_TOOLS,
                tool_choice="auto",
                max_tokens=400,
            )
            msg = response.choices[0].message

            if not msg.tool_calls:
                reply = (msg.content or "").strip()
                break

            messages.append({
                "role": "assistant",
                "content": msg.content or "",
                "tool_calls": [
                    {"id": tc.id, "type": "function",
                     "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                    for tc in msg.tool_calls
                ],
            })
            for tc in msg.tool_calls:
                try:
                    args = json.loads(tc.function.arguments or "{}")
                except json.JSONDecodeError:
                    args = {}
                print(f"[Brain] Step {step + 1}: LLM chose tool '{tc.function.name}'")
                result = run_tool(tc.function.name, args)
                print(f"[Brain] Tool result: {result[:120]}")
                messages.append({"role": "tool", "tool_call_id": tc.id, "content": result})
        else:
            reply = "Sorry boss, that took too many steps and I got stuck."

        if not reply:
            reply = "Sorry boss, I didn't get a proper answer. Try again."
        conversation_history.append({"role": "assistant", "content": reply})
        return reply

    except Exception as e:
        print(f"[Brain] LLM error: {e}")
        conversation_history.pop()  # drop the unanswered user message
        return "I'm having trouble connecting to my brain right now."


def clear_memory():
    global conversation_history
    conversation_history = []
    print("[Brain] Memory cleared.")