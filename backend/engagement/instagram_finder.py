import os
import requests
from dotenv import load_dotenv

load_dotenv()

ACCESS_TOKEN = os.getenv("META_ACCESS_TOKEN")
BASE_URL = "https://graph.facebook.com/v19.0"

NICHE_HASHTAGS = [
    "construcaocivil", "pedreiro", "obra", "maodeobra",
    "construção", "reformas", "pedreirodeconfiança", "obraresidencial"
]


def get_hashtag_id(hashtag: str) -> str | None:
    url = f"{BASE_URL}/ig_hashtag_search"
    res = requests.get(url, params={
        "user_id": os.getenv("INSTAGRAM_ACCOUNT_ID"),
        "q": hashtag,
        "access_token": ACCESS_TOKEN
    })
    data = res.json()
    ids = data.get("data", [])
    return ids[0]["id"] if ids else None


def get_top_posts_for_hashtag(hashtag_id: str, limit: int = 5) -> list:
    url = f"{BASE_URL}/{hashtag_id}/top_media"
    res = requests.get(url, params={
        "user_id": os.getenv("INSTAGRAM_ACCOUNT_ID"),
        "fields": "id,caption,like_count,comments_count,permalink,timestamp,media_type",
        "access_token": ACCESS_TOKEN
    })
    posts = res.json().get("data", [])[:limit]
    return [
        {
            "id": p.get("id"),
            "caption": p.get("caption", "")[:200],
            "likes": p.get("like_count", 0),
            "comments": p.get("comments_count", 0),
            "url": p.get("permalink", ""),
            "type": p.get("media_type", ""),
            "timestamp": p.get("timestamp", ""),
            "platform": "instagram"
        }
        for p in posts
    ]


def find_hot_posts(max_posts: int = 8) -> list:
    all_posts = []
    seen_ids = set()

    for hashtag in NICHE_HASHTAGS[:4]:
        hashtag_id = get_hashtag_id(hashtag)
        if not hashtag_id:
            continue
        posts = get_top_posts_for_hashtag(hashtag_id, limit=3)
        for post in posts:
            if post["id"] not in seen_ids:
                post["hashtag"] = hashtag
                all_posts.append(post)
                seen_ids.add(post["id"])

    all_posts.sort(key=lambda x: x.get("likes", 0) + x.get("comments", 0) * 3, reverse=True)
    return all_posts[:max_posts]
