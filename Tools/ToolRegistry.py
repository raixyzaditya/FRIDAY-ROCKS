"""
Single place where every FRIDAY tool is declared.

TOOLS      -> JSON-schema descriptions you pass to the LLM (name, description, parameters).
run_tool() -> executes whatever tool the LLM picked, with validation and error handling.
"""

import re

from . import Contacts
from .News import handle_news_command
from .WebSearch import web_search
from .PCControl import (open_app, search_files, take_screenshot, create_folder, create_file, move_file,
                        system_control)
from .Weather import get_weather
from .Memory import remember, forget
from .Reminders import set_reminder, list_reminders, cancel_reminder
from .Desktop import system_status, read_clipboard, copy_to_clipboard, open_website
from .Vision import look_at_screen
from .Google import get_calendar_events, add_calendar_event
from .Email import check_email, send_email  # whichever mailbox is set up (app password, or Google sign-in)
from .Control import type_text, press_keys, scroll
from .Briefing import daily_briefing
from .Contacts import save_contact, add_contact, forget_contact, list_contacts


def get_news(topic: str = "") -> str:
    # Wrapper so the LLM passes a plain topic instead of a raw spoken sentence.
    return handle_news_command(f"news about {topic}" if topic else "world news")


FUNCTIONS = {
    "web_search": web_search,
    "get_news": get_news,
    "get_weather": get_weather,
    "open_app": open_app,
    "search_files": search_files,
    "take_screenshot": take_screenshot,
    "create_folder": create_folder,
    "create_file": create_file,
    "move_file": move_file,
    "system_control": system_control,
    "remember": remember,
    "forget": forget,
    "set_reminder": set_reminder,
    "list_reminders": list_reminders,
    "cancel_reminder": cancel_reminder,
    "system_status": system_status,
    "read_clipboard": read_clipboard,
    "copy_to_clipboard": copy_to_clipboard,
    "open_website": open_website,
    "look_at_screen": look_at_screen,
    "get_calendar_events": get_calendar_events,
    "add_calendar_event": add_calendar_event,
    "check_email": check_email,
    "send_email": send_email,
    "save_contact": save_contact,
    "add_contact": add_contact,
    "forget_contact": forget_contact,
    "list_contacts": list_contacts,
    "type_text": type_text,
    "press_keys": press_keys,
    "scroll": scroll,
    "daily_briefing": daily_briefing,
}


def _tool(name, description, properties=None, required=None):
    return {
        "name": name,
        "description": description,
        "parameters": {
            "type": "object",
            "properties": properties or {},
            "required": required or [],
        },
    }


TOOLS = [
    _tool("web_search",
          "Search the web for general information, facts, prices, how-tos or definitions.",
          {"query": {"type": "string", "description": "What to search for"}}, ["query"]),
    _tool("get_news",
          "Get the latest news headlines, optionally about a topic (e.g. 'AI', 'cricket').",
          {"topic": {"type": "string", "description": "Optional topic; leave empty for world news"}}),
    _tool("get_weather",
          "Get the current weather for a city.",
          {"city": {"type": "string", "description": "City name, e.g. 'Delhi'"}}, ["city"]),
    _tool("open_app",
          "Open a desktop application such as Notepad, Chrome, Calculator or VS Code.",
          {"name": {"type": "string", "description": "App name"}}, ["name"]),
    _tool("search_files",
          "Find files by name on this computer (Desktop, Documents, Downloads by default).",
          {"query": {"type": "string", "description": "Words in the file name"},
           "folder": {"type": "string", "description": "Optional folder to search in"}}, ["query"]),
    _tool("take_screenshot",
          "Capture the screen and save it as an image."),
    _tool("create_folder",
          "Create a new folder inside the user's home directory.",
          {"path": {"type": "string", "description": "Folder path, e.g. 'Documents/Project'"}}, ["path"]),
    _tool("create_file",
          "Create a new text file with the given content. A bare name goes in Documents; never overwrites.",
          {"path": {"type": "string", "description": "File name or path, e.g. 'notes.txt' or 'Documents/Project/todo.md'"},
           "content": {"type": "string", "description": "What to write in it (can be empty)"}}, ["path"]),
    _tool("move_file",
          "Move a file to another folder. Asks the user to confirm by voice first.",
          {"source": {"type": "string", "description": "File name or path"},
           "destination": {"type": "string", "description": "Destination folder or path"}},
          ["source", "destination"]),
    _tool("system_control",
          "Control the PC's volume and media playback, or lock the screen.",
          {"action": {"type": "string",
                      "enum": ["volume_up", "volume_down", "mute", "play_pause",
                               "next_track", "previous_track", "lock_screen"],
                      "description": "What to do"},
           "steps": {"type": "integer", "description": "Volume steps of about 10% each (default 1)"}},
          ["action"]),
    _tool("remember",
          "Save a lasting fact about the user (preferences, people, routines) when they ask you to remember something.",
          {"fact": {"type": "string", "description": "The fact, as a short sentence, e.g. 'User's gym session is at 6 am'"}},
          ["fact"]),
    _tool("forget",
          "Delete remembered facts about a topic when the user asks you to forget something.",
          {"topic": {"type": "string", "description": "Keywords of the fact to forget"}}, ["topic"]),
    _tool("set_reminder",
          "Set a reminder or a timer. Friday will speak up when it is due, even if nobody is talking to her. "
          "Give either minutes (relative, e.g. 20) or at (a clock time).",
          {"message": {"type": "string", "description": "What to remind about, e.g. 'call mom'. For a timer use 'your timer'."},
           "minutes": {"type": "number", "description": "Minutes from now, e.g. 20 for 'in 20 minutes', 90 for 'in an hour and a half'"},
           "at": {"type": "string", "description": "Clock time in 24-hour HH:MM (e.g. '18:30'), or 'YYYY-MM-DD HH:MM' for another day"}},
          ["message"]),
    _tool("list_reminders", "List the reminders and timers that are currently set."),
    _tool("cancel_reminder",
          "Cancel a reminder or timer.",
          {"keyword": {"type": "string", "description": "Words from the reminder to cancel"}}, ["keyword"]),
    _tool("system_status", "Report the PC's battery level, memory use and free disk space."),
    _tool("read_clipboard", "Read the text the user last copied to the clipboard (e.g. to summarise, translate or explain it)."),
    _tool("copy_to_clipboard",
          "Put text on the clipboard so the user can paste it.",
          {"text": {"type": "string", "description": "The text to copy"}}, ["text"]),
    _tool("open_website",
          "Open a website in the browser, or search the web in the browser when it isn't an address.",
          {"target": {"type": "string", "description": "A web address like 'youtube.com' or 'https://github.com', or search words"}},
          ["target"]),
    _tool("look_at_screen",
          "Look at the user's screen and answer a question about it (read an error, describe a page, explain what is open). "
          "Captures one screenshot and sends it to a vision model.",
          {"question": {"type": "string", "description": "What to find out, e.g. 'What does this error mean?'"}}),
    _tool("get_calendar_events",
          "Read the user's Google Calendar: what is coming up today or over the next few days.",
          {"days": {"type": "integer", "description": "1 for today (default), 7 for the coming week"}}),
    _tool("add_calendar_event",
          "Add an event to the user's Google Calendar. The user is asked to confirm by voice first.",
          {"title": {"type": "string", "description": "Event name"},
           "start": {"type": "string", "description": "24-hour HH:MM for today/tomorrow, or 'YYYY-MM-DD HH:MM'"},
           "duration_minutes": {"type": "integer", "description": "Length in minutes (default 60)"}},
          ["title", "start"]),
    _tool("check_email",
          "Read the user's email inbox (this only reads; sending is send_email). Defaults to unread mail, newest first.",
          {"query": {"type": "string", "description": "Optional search, e.g. 'from:amazon' or 'subject:invoice newer_than:7d'"},
           "max_results": {"type": "integer", "description": "How many emails (default 5, max 10). For 'top 2 emails' use 2."},
           "include_body": {"type": "boolean",
                            "description": "True when the user wants emails summarised or read out, so you get the message text. "
                                           "False just lists sender and subject."}}),
    _tool("send_email",
          "Send a short email from the user's own email account. Only when the user's own spoken words ask you to send it. "
          "The user hears the recipient, subject and full message read back and must say yes before anything is sent. "
          "Recipients must be saved contacts: pass the contact's NAME (e.g. 'Ravi'). If the person isn't saved, "
          "call add_contact with their name first (Friday then asks the user for the details by voice).",
          {"to": {"type": "string", "description": "Saved contact name(s), e.g. 'Ravi' or 'Ravi, Mom' (up to 3, comma separated)"},
           "subject": {"type": "string", "description": "Short subject line"},
           "body": {"type": "string", "description": "The message text, under 600 characters, written in the user's voice, plain text"}},
          ["to", "subject", "body"]),
    _tool("add_contact",
          "Add a person as an email contact. PREFERRED way: Friday herself asks the user which email service "
          "(gmail, yahoo...) and to spell the part before the @, then spells it all back and waits for a yes. "
          "Just pass the name; do not ask the user for the address yourself.",
          {"name": {"type": "string", "description": "The person's name, e.g. 'Dad' or 'Ravi'"}}, ["name"]),
    _tool("save_contact",
          "Save a contact from a COMPLETE email address the user has already said in full. Rarely needed: prefer add_contact. "
          "Friday spells the address back letter by letter and the user must say yes before it is saved.",
          {"name": {"type": "string", "description": "The person's name, e.g. 'Ravi' or 'Mom'"},
           "email": {"type": "string", "description": "Their email address, exactly as the user gave it"}},
          ["name", "email"]),
    _tool("forget_contact", "Remove a saved email contact.",
          {"name": {"type": "string", "description": "The contact's name"}}, ["name"]),
    _tool("list_contacts", "List the names of the saved email contacts."),
    _tool("type_text",
          "Type text into the currently active window. Only when the user explicitly asks you to type something. "
          "The user is asked to confirm by voice first.",
          {"text": {"type": "string", "description": "Exactly what to type"}}, ["text"]),
    _tool("press_keys",
          "Press a key or an allowed shortcut in the active window, e.g. 'enter', 'ctrl+c', 'ctrl+v', 'alt+tab'. "
          "The user is asked to confirm by voice first.",
          {"keys": {"type": "string", "description": "Key or combination, e.g. 'ctrl+s'"}}, ["keys"]),
    _tool("scroll",
          "Scroll the page or window under the mouse up or down.",
          {"direction": {"type": "string", "enum": ["up", "down"], "description": "Which way"},
           "amount": {"type": "integer", "description": "Scroll clicks, default 3"}}, ["direction"]),
    _tool("daily_briefing",
          "Gather the user's daily briefing: date, weather, reminders, calendar, email and news. "
          "Use when the user asks for their briefing, morning update, or 'what's my day look like'.",
          {"city": {"type": "string", "description": "The user's home city for the weather, if you know it from memory"}}),
]


# ---------------------------------------------------------------- tool routing
#
# Sending all ~30 tool definitions with every request costs ~3,000 tokens, which burns through Groq's
# free limits (200k tokens/day, 8k/minute). So each request gets only the tools that look relevant to what
# the user said. "core" is always sent. A side benefit: powerful tools (typing, email) are not even
# offered unless the user's words mention them.

TOOL_GROUPS = {
    "core": ["web_search", "get_news", "get_weather", "remember", "forget", "open_app", "open_website",
             "system_control", "set_reminder", "list_reminders", "cancel_reminder"],
    "files": ["search_files", "create_folder", "create_file", "move_file", "take_screenshot"],
    "screen": ["look_at_screen"],
    "clipboard": ["read_clipboard", "copy_to_clipboard"],
    "status": ["system_status"],
    "calendar": ["get_calendar_events", "add_calendar_event"],
    "email": ["check_email", "send_email", "add_contact", "save_contact", "forget_contact", "list_contacts"],
    "control": ["type_text", "press_keys", "scroll"],
    "briefing": ["daily_briefing"],
}
GROUP_OF = {tool: group for group, names in TOOL_GROUPS.items() for tool in names}

# Deliberately generous: a wasted group costs ~100-300 tokens, a missed one means Friday can't do the task.
_ROUTES = {
    "files": r"\b(files?|folders?|director(?:y|ies)|documents?|docs?|pdfs?|docx?|xlsx?|spreadsheets?|downloads?|"
             r"desktop|find|locate|move|rename|screenshots?|screen ?shots?|capture|notes?|txt|scripts?)\b",
    "screen": r"\b(screen|error|visible|showing|looking at|what'?s open|what is open|"
              r"read this|explain this|describe this)\b",
    "clipboard": r"\b(clipboard|copied|copy|paste|pasted)\b",
    "status": r"\b(battery|charg\w*|memory|ram|disk|storage|space|cpu|performance|laptop|status|"
              r"how'?s my (pc|computer|laptop))\b",
    "calendar": r"\b(calendar|meetings?|events?|schedule|appointments?|agenda|busy|free|book|today|tomorrow|"
                r"tonight|monday|tuesday|wednesday|thursday|friday|saturday|sunday|this week|next week)\b",
    "email": r"\b(e-?mails?|inbox|gmail|messages?|send|contacts?|reply|write to|tell|unread|forward|mail)\b",
    "control": r"\b(type|typing|press|keys?|keyboard|enter|scroll|shortcut|ctrl|control c|alt|tab|click|dictate)\b",
    "briefing": r"\b(brief\w*|morning|my day|update me|catch me up|what'?s up|good morning)\b",
}
_ROUTE_PATTERNS = {group: re.compile(rx, re.I) for group, rx in _ROUTES.items()}


def _mentions_contact(text: str) -> bool:
    """True if any word of the text is a saved contact's name ('tell Papa I'll be late')."""
    return any(len(word) >= 3 and Contacts.find(word) for word in re.findall(r"[a-z']+", text.lower()))


def select_groups(text: str, recent_tools=()) -> set:
    """Which tool groups to send for this request: core, plus any whose keywords appear in the user's words,
    plus the groups of tools used recently (so follow-ups like 'move it' or 'send it' keep working)."""
    groups = {"core"}
    for group, pattern in _ROUTE_PATTERNS.items():
        if pattern.search(text or ""):
            groups.add(group)
    for name in recent_tools:
        if name in GROUP_OF:
            groups.add(GROUP_OF[name])
    if _mentions_contact(text or ""):
        groups.add("email")
    return groups


def tools_for(groups=None) -> list:
    """Tool schemas for the given groups (None = every tool)."""
    if groups is None:
        return list(TOOLS)
    wanted = {name for g in groups for name in TOOL_GROUPS.get(g, [])}
    return [t for t in TOOLS if t["name"] in wanted]


def run_tool(name: str, args: dict = None) -> str:
    """Run a tool by name. Never raises: always returns a string FRIDAY can speak."""
    func = FUNCTIONS.get(name)
    if func is None:
        return f"Sorry boss, I don't have a tool called {name}."
    schema = next(t for t in TOOLS if t["name"] == name)
    allowed = schema["parameters"]["properties"]
    required = schema["parameters"]["required"]

    args = {k: v for k, v in (args or {}).items() if k in allowed}  # drop unknown args
    missing = [r for r in required if not args.get(r)]
    if missing:
        return f"Sorry boss, I need the {', '.join(missing)} for that."

    print(f"[Tool] {name}({args})")
    try:
        return str(func(**args))
    except Exception as e:
        print(f"[Tool] {name} failed: {e}")
        return "Sorry boss, that tool ran into a problem."
