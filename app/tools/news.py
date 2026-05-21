import os
import requests
from dotenv import load_dotenv

load_dotenv()

NEWS_API_KEY = os.getenv("NEWS_API_KEY")

def get_financial_news(company: str, max_articles: int = 5) -> list:
    url = "https://newsapi.org/v2/everything"
    params = {
        "q": f"{company} earnings financial results",
        "apiKey": NEWS_API_KEY,
        "language": "en",
        "sortBy": "publishedAt",
        "pageSize": max_articles
    }
    response = requests.get(url, params=params)
    data = response.json()

    if data.get("status") != "ok":
        raise ValueError(f"NewsAPI error: {data.get('message')}")

    articles = []
    for article in data.get("articles", []):
        articles.append({
            "title": article["title"],
            "source": article["source"]["name"],
            "published": article["publishedAt"],
            "content": article.get("content") or article.get("description") or "",
            "url": article["url"]
        })

    return articles