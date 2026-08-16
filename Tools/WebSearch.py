import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'Voice'))
from ddgs import DDGS

def web_search(query: str, max_results:int = 5)-> str:
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query,max_results = max_results,region="in-en",safesearch="moderate"))
            if not results:
                return f"Sorry, I couldn't find any results for {query}."
            lines = [f"Here are the top search for {query} :- "]
            for i, result in enumerate(results,1):
                title = result.get("title","")
                body = result.get("body","")[:180]
                if title:
                    lines.append(f"{i}. {title}-{body}")
            return "\n".join(lines)
    except Exception as e:
        return f"Sorry boss, something went wrong while searching the web. Please try again later."
    
def latest_search(query: str, max_results:int=5)-> str:
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query,max_results = max_results,region="in-en",safesearch="moderate"))
            if not results:
                return f"Sorry boss, I couldn't find any results for {query}."
            lines = [f"Latest news for {query} :- "]
            for i, result in enumerate(results,1):
                title = result.get("title","")
                source = result.get("source","")
                date = result.get("date","")[:10]
                if title:
                    lines.append(f"{i}. {title}" + (f" — {source} ({date})" if source else ""))
            return "\n".join(lines)
    except Exception as e:
        return f"Sorry boss, something went wrong while searching the web. Please try again later :- {str(e)}."
    
def handle_search_command(query: str)->str:
    text = query.lower()
    news_triggers = [
        "latest", "recent", "today", "yesterday", "this week",
        "just happened", "right now", "currently", "update",
        "news", "war", "attack", "election", "score"
    ]

    web_triggers = [
        "price", "cost", "how much", "what is", "who is",
        "how to", "best", "review", "compare", "vs",
        "difference between", "meaning of", "define"
    ]
    filler = [
        "hey friday", "friday", "search for", "search",
        "look up", "find", "google", "tell me about",
        "what is", "who is", "latest on", "news about"
    ]
    command = query
    for f in filler:
        command = command.lower().replace(f,"").strip()
    command = command.strip("?.,!")
    if not command:
        return "Sorry boss, what do you want me to search for"
    if any(t in text for t in news_triggers):
        return latest_search(command)
    else:
        return web_search(command)

 
    
