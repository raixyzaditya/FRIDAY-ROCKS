"""
Text-mode test harness for FRIDAY (no microphone needed).
Run from the same folder as Main.py:   python run_tests.py

For every command it records: which tools the LLM chose, whether that matches
the expectation, latency, and the reply. Results go to friday_results.csv.
Fill the 'task_success' column by hand after checking the actual outcome.
"""
import csv
import time

import Brain

# (category, command, expected tools). A tuple means "any one of these".
PAUSE_BETWEEN_TESTS = 30  # seconds; keeps us under Groq's free 8K tokens/minute limit

TESTS = [
    ("live info",  "What's the weather in Delhi?",                       ["get_weather"]),
    ("live info",  "Latest news about AI",                               ["get_news"]),
    ("live info",  "Who is the CEO of Nvidia?",                          ["web_search"]),
    ("app launch", "Open Notepad",                                       ["open_app"]),
    ("app launch", "Open Calculator",                                    ["open_app"]),
    ("file",       "Find a file named resume",                           ["search_files"]),
    ("file",       "Create a folder called FridayTest in Documents",     ["create_folder"]),
    ("system",     "Take a screenshot",                                  ["take_screenshot"]),
    ("no tool",    "What is the capital of France?",                     []),
    ("no tool",    "Tell me a joke",                                     []),
    ("multi-step", "Search for AI news and then open Notepad",           [("get_news", "web_search"), "open_app"]),
    ("multi-step", "Take a screenshot and then open Chrome",             ["take_screenshot", "open_app"]),
]
# move_file needs a spoken yes, so test it manually by voice.

called = []
_original_run_tool = Brain.run_tool


def _logging_run_tool(name, args=None):
    called.append(name)
    return _original_run_tool(name, args)


Brain.run_tool = _logging_run_tool


def tools_match(expected, actual):
    if not expected:
        return len(actual) == 0
    for e in expected:
        options = e if isinstance(e, tuple) else (e,)
        if not any(o in actual for o in options):
            return False
    return True


def main():
    rows = []
    for i, (category, command, expected) in enumerate(TESTS, 1):
        Brain.clear_memory()  # keep tests independent
        called.clear()
        print(f"\n--- Test {i}: {command}")
        start = time.time()
        reply = Brain.ask_friday(command)
        latency = round(time.time() - start, 2)
        llm_failed = reply.startswith("I'm having trouble connecting")
        ok = (not llm_failed) and tools_match(expected, called)
        print(f"Tools: {called} | match: {ok} | {latency}s" + (" | LLM ERROR" if llm_failed else "") + f"\nReply: {reply}")
        if i < len(TESTS):
            time.sleep(PAUSE_BETWEEN_TESTS)
        rows.append({
            "id": i, "category": category, "command": command,
            "tools_called": ", ".join(called), "tool_selection_ok": ok,
            "latency_s": latency, "task_success": "", "reply": reply,
        })

    with open("friday_results.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    n_ok = sum(r["tool_selection_ok"] for r in rows)
    avg = sum(r["latency_s"] for r in rows) / len(rows)
    print(f"\nTool-selection accuracy: {n_ok}/{len(rows)} = {100 * n_ok / len(rows):.0f}%")
    print(f"Mean latency (text mode, no STT/TTS): {avg:.2f}s")
    print("Saved friday_results.csv. Fill in task_success manually.")


if __name__ == "__main__":
    main()