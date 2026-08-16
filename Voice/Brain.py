
import sys
import os

from Config import HF_TOKEN
from huggingface_hub import InferenceClient
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
client = InferenceClient(api_key=HF_TOKEN,provider='auto')

SYSTEM_PROMPT = """
You are F.R.I.D.A.Y. — a highly intelligent personal AI assistant.
You are very expert in physics, maths, chemistry, Laws, Computer science and general knowledge, automabiles like Mercedes, bmw, toyota and very much more. You are ultimate.
You were built by your user for their own personal use.
 
Your personality:
- Smart, direct, and concise. No fluff.
- You speak like a sharp, confident assistant — not a corporate chatbot.
- You address the user casually. No "Certainly!" or "Of course!".
- Keep responses short when spoken aloud (2-4 sentences max unless asked for more).
- You can be witty but you always prioritise being useful.
 
Your capabilities right now (Phase 1):
- Answer questions using your knowledge
- Have a real conversation and remember context within this session
- Access live information when it is provided by tools
- Help with coding, reasoning, planning, writing and general problem solving

Future capabilities:
- PC control
- Advanced computer automation
- Shopping assistance
- Physical/home automation through Raspberry Pi and connected devices
- You have access to live news, weather and search results when provided by the tools. When you have live data, you can use it to answer questions about current events, weather, or anything else. Always use the live data when it's available — it's more accurate and up-to-date than your training data.                       

When given live data (news/weather/search results):
- Summarise it naturally for speaking aloud — conversational, not robotic
- Don't read out bullet numbers like "1, 2, 3" — weave it into sentences
- Always keep the user in mind - what would be most useful and interesting for them to hear?
 
Current limitations:

- You cannot control the PC yet (coming in Phase 2)
 
If asked something you don't know, say so directly — don't make things up.
"""
MAX_HISTORY = 10
conversation_history = []

def detect_intent(user_input: str)->str:
    t = user_input.lower()
    news_keywords = [
        "news",
        "headlines",
        "current events",
        "latest news",
        "news about",
        "news on",
        "what happened in the news"
    ]

    search_keywords = [
        "search",
        "search for",
        "look up",
        "find",
        "google",
        "who is",
        "what is",
        "how much",
        "price",
        "how to",
        "best",
        "review",
        "compare",
        "vs",
        "difference",
        "meaning",
        "tell me about",
        "score",
        "match",
        "cricket",
        "football",
        "sports",
        "weather"
    ]

    if any(k in t for k in news_keywords):
        return "news"
    if any(k in t for k in search_keywords):
        return "search"

    return None

def ask_friday(question: str)-> str:
    global conversation_history
    print(f"[Brain] User: {question}")
    intent = detect_intent(question)
    print(f"[Brain] Detected intent: {intent}")
    live_data = None
    if intent == "news":
        try:
            from Tools.News import handle_news_command
            print("[Brain] Detected news intent. Fetching news...")
            live_data = handle_news_command(question)
        except Exception as e:
            print(f"[Brain] News tool error: {str(e)}")
    elif intent == "search":
        try:
            from Tools.WebSearch import handle_search_command
            print("[Brain] Detected search intent. Performing web search...")
            live_data = handle_search_command(question)
        except Exception as e:
            print(f"[Brain] Web search tool error: {str(e)}")

    if live_data:
        message_content = (
            f"User asked: {question}\n\n"
            f"Live data fetched: {live_data}\n\n"
            f"Summarise this information in a natural, conversational way for speaking aloud. Be concise and engaging.  Don't just read out bullet points - weave it into sentences. Focus on what's most interesting and useful for the user to hear."
        )
    else:
        message_content = question
    conversation_history.append({"role":"user","content":message_content})
    if len(conversation_history)>MAX_HISTORY:
        conversation_history = conversation_history[-MAX_HISTORY:]

    try:
        response = client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[
                {"role":"system","content": SYSTEM_PROMPT},
                *conversation_history
            ],
            max_tokens = 300
        )
        reply = response.choices[0].message.content.strip()
        conversation_history.append({"role":"assistant","content":reply})
        return reply
    
 
    except Exception as e:
        print(f"[Brain] LLM error: {e}")
        return "I'm having trouble connecting to my brain right now."
def clear_memory():
    
    global conversation_history
    conversation_history = []
    print("[Brain] Memory cleared.")