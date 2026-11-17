import requests
import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'Voice'))
from Config import NEWS_API_KEY, GAURDIAN_API_KEY
from datetime import datetime

BASE_URL = "https://newsapi.org/v2/top-headlines"
EVERYTHING_URL = "https://newsapi.org/v2/everything"
GAURDIAN_URL = "https://content.guardianapis.com/search"

SECTION_MAP = {
    "world": "world", "war": "world", "iran": "world",
    "israel": "world", "ukraine": "world", "russia": "world",
    "politics": "politics", "tech": "technology",
    "technology": "technology", "ai": "technology",
    "science": "science", "sport": "sport", "sports": "sport",
    "cricket": "sport", "football": "sport",
    "business": "business", "finance": "business", "economy": "business",
    "health": "society", "entertainment": "culture",
    "bollywood": "culture", "hollywood": "culture",
    "environment": "environment", "climate": "environment",
}
 
SEARCH_TRIGGERS = [
    "about", "on", "regarding", "related to", "related with",
    "news on", "news about", "update on", "updates on",
    "latest on", "situation in", "what happened to",
    "what's happening with"
]

NEWS_NOT_SET_UP = ("Sorry boss, news isn't set up yet. Add your Guardian or NewsAPI key "
                   "to Config.py and I'll be able to read you the headlines.")


def guardian_search(query: str=None, section: str=None)->str:
    if not GAURDIAN_API_KEY:
        return None  # no key: let the caller fall back to NewsAPI
    params = {
        "api-key":GAURDIAN_API_KEY,
        "page-size":6,
        "order-by":"newest",
        "show-fields":"trailText"
    }
    if query:
        params["q"] = query
    if section:
        params["section"] = section
    
    try:
        response = requests.get(GAURDIAN_URL,params=params,timeout=5)
        data = response.json()
        result = data.get("response",{}).get("results",[])
        if not result:
            return None
        lines = [f"Here are the latest news from my updates {datetime.now().strftime('%B %d')} :"]
        for i,article in enumerate(result,1):
            title = article.get("webTitle","").split(" | ")[0].strip()
            if title:
                lines.append(f"{i}. {title}")
        return "\n".join(lines)
    except Exception:
        return None




def get_top_headlines_from_NewsAPI(category:str=None,country:str='us')->str:
    if not NEWS_API_KEY:
        return "Sorry boss, I couldn't fetch the news right now"
    params = {
        "apiKey": NEWS_API_KEY,
        "country":country,
        "pageSize":6
    }

    params["category"] = category if category else "general"
    try:
        response = requests.get(BASE_URL,params = params,timeout = 5)
        data = response.json()
        if data["status"] != "ok":
            return "Sorry boss, I couldn't fetch the news right now"
        articles = data.get("articles",[])
        if not articles:
            return "Sorry boss, I wasn't able to find the headlines right now"
        lines = [f"Here are the top headlines for {datetime.now().strftime('%B %d')} : "]
        for i, article in enumerate(articles,1):
            title = article.get("title","").split(" - ")[0]
            if title and title != "[Removed]":
                lines.append(f"{i}. {title}")
        return "\n".join(lines)
    except Exception:
        return "Sorry boss, something went wrong while fetching the news. Please try again later."

def search_news(query:str)-> str:
    if not NEWS_API_KEY:
        return "Sorry boss, I couldn't fetch the news right now"
    params = {
        "apiKey": NEWS_API_KEY,
        "q":query,
        "pageSize":6,
        "sortBy":"publishedAt",
        "language":"en"
    }

    try:
        response = requests.get(EVERYTHING_URL,params = params,timeout = 5)
        data = response.json()
        if data["status"] != "ok":
            return "Sorry boss, I couldn't fetch the news right now"
        articles = data.get("articles",[])
        if not articles:
            return f"Sorry boss, I couldn't find any news related to '{query}' right now"
        lines = [f"Here are the top news articles related to {query} :"]
        for i, article in enumerate(articles,1):
            title = article.get("title","").split(" - ")[0]
            source = article.get("source",{}).get("name","")
            if title and title != "[Removed]":
                lines.append(f"{i}. {title}" + (f" ({source} )" if source else ""))
        return "\n".join(lines)
    except Exception:
        return "Sorry boss, something went wrong while fetching the news. Please try again later."
    
def handle_news_command(command:str)->str:
    if not GAURDIAN_API_KEY and not NEWS_API_KEY:
        return NEWS_NOT_SET_UP
    text = command.lower()
    for trigger in SEARCH_TRIGGERS:
        if trigger in text:
            parts = text.split(trigger,1)
            if len(parts)>1:
                topic = parts[1].strip().replace("news","").strip()
                if topic:
                    print(f"[News] Guardian search for topic: {topic}")
                    result = guardian_search(query=topic)
                    if result:
                        return result
                    print(f"[Gaurdian] failed to fetch. Now trying Newsapi for topic: {topic}")
                    return search_news(topic)
    for k,s in SECTION_MAP.items():
        if k in text:
            print(f"[News] Gaurdian search : {s}")
            result = guardian_search(section=s)
            if result:
                return result
            print(f"[Gaurdian] failed to fetch. Now trying Newsapi for category: {s}")
            return get_top_headlines_from_NewsAPI(category=s if s!="world" else None)
    print(f"[News] Fetching guardian world news :- ")
    result = guardian_search(section="world")
    if result:
        return result
    print("[News] Falling back to NewsAPI...")
    return get_top_headlines_from_NewsAPI()