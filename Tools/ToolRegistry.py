"""
Single place where every FRIDAY tool is declared.

TOOLS      -> JSON-schema descriptions you pass to the LLM (name, description, parameters).
run_tool() -> executes whatever tool the LLM picked, with validation and error handling.
"""

from .News import handle_news_command
from .WebSearch import web_search
from .PCControl import open_app, search_files, take_screenshot, create_folder, move_file
from .Weather import get_weather


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
    "move_file": move_file,
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
    _tool("move_file",
          "Move a file to another folder. Asks the user to confirm by voice first.",
          {"source": {"type": "string", "description": "File name or path"},
           "destination": {"type": "string", "description": "Destination folder or path"}},
          ["source", "destination"]),
]


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
