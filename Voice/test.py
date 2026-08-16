from ddgs import DDGS

results = DDGS().text(
    "latest score of India vs sri lanka 2026",
    region="in-en",
    safesearch="moderate",
    max_results=5
)

print(results)