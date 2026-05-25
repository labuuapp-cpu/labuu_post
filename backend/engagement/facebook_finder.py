import os
import requests
from dotenv import load_dotenv

load_dotenv()

ACCESS_TOKEN = os.getenv("META_ACCESS_TOKEN")
BASE_URL = "https://graph.facebook.com/v19.0"

NICHE_GROUPS_KEYWORDS = [
    "construção civil",
    "pedreiro",
    "obra",
    "mão de obra construção"
]

# Grupos sugeridos manualmente para engajamento inicial
# (populados pelo usuário conforme for encontrando grupos relevantes)
SUGGESTED_GROUPS = [
    {
        "name": "Construção Civil Brasil",
        "url": "https://facebook.com/groups/construcaocivilbrasil",
        "description": "Maior grupo de construção civil do Facebook"
    },
    {
        "name": "Pedreiros e Ajudantes de Obra",
        "url": "https://facebook.com/groups/pedreirosajudantes",
        "description": "Grupo para pedreiros e ajudantes buscando trabalho"
    }
]


def search_public_posts(keyword: str, limit: int = 3) -> list:
    url = f"{BASE_URL}/search"
    res = requests.get(url, params={
        "q": keyword,
        "type": "post",
        "fields": "message,from,created_time,likes.summary(true),comments.summary(true),permalink_url",
        "limit": limit,
        "access_token": ACCESS_TOKEN
    })
    posts = res.json().get("data", [])
    return [
        {
            "caption": p.get("message", "")[:200],
            "username": p.get("from", {}).get("name", ""),
            "likes": p.get("likes", {}).get("summary", {}).get("total_count", 0),
            "comments": p.get("comments", {}).get("summary", {}).get("total_count", 0),
            "url": p.get("permalink_url", ""),
            "timestamp": p.get("created_time", ""),
            "platform": "facebook"
        }
        for p in posts
    ]


def find_hot_posts(max_posts: int = 6) -> list:
    all_posts = []
    for keyword in NICHE_GROUPS_KEYWORDS[:2]:
        posts = search_public_posts(keyword, limit=3)
        all_posts.extend(posts)

    all_posts.sort(key=lambda x: x.get("likes", 0) + x.get("comments", 0) * 3, reverse=True)
    return all_posts[:max_posts]


def get_suggested_groups() -> list:
    return SUGGESTED_GROUPS
