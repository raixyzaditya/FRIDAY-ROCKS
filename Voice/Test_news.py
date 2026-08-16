import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from Tools.News import get_top_headlines, search_news, handle_news_command
 
print("=== Test 1: Top headlines India ===")
print(get_top_headlines())
print()
 
print("=== Test 2: Tech news ===")
print(get_top_headlines(category="technology"))
print()
 
print("=== Test 3: Search cricket ===")
print(search_news("IPL 2026"))
print()
 
print("=== Test 4: Voice command simulation ===")
print(handle_news_command("what's the latest news about AI"))