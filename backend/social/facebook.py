import os
import requests
import logging
from dotenv import load_dotenv

logger = logging.getLogger(__name__)
load_dotenv()

# Tenta usar o token específico da página, senão usa o token geral da Meta
ACCESS_TOKEN = os.getenv("META_PAGE_ACCESS_TOKEN") or os.getenv("META_ACCESS_TOKEN")
PAGE_ID = os.getenv("FACEBOOK_PAGE_ID")
BASE_URL = "https://graph.facebook.com/v19.0"


def post_video(video_path: str, caption: str, title: str = "") -> dict:
    url = f"{BASE_URL}/{PAGE_ID}/videos"
    with open(video_path, "rb") as f:
        res = requests.post(url, data={
            "description": caption,
            "title": title,
            "access_token": ACCESS_TOKEN
        }, files={"source": f})
    data = res.json()
    if "error" in data:
        logger.error(f"Erro Facebook Video API: {data}")
    return data


def post_image(image_path: str, caption: str) -> dict:
    url = f"{BASE_URL}/{PAGE_ID}/photos"
    with open(image_path, "rb") as f:
        res = requests.post(url, data={
            "caption": caption,
            "access_token": ACCESS_TOKEN
        }, files={"source": f})
    data = res.json()
    if "error" in data:
        logger.error(f"Erro Facebook Image API: {data}")
    return data


def get_page_insights() -> dict:
    url = f"{BASE_URL}/{PAGE_ID}/insights"
    res = requests.get(url, params={
        "metric": "page_impressions,page_reach,page_fan_adds,page_post_engagements",
        "period": "week",
        "access_token": ACCESS_TOKEN
    })
    return res.json()


def get_post_metrics(post_id: str) -> dict:
    url = f"{BASE_URL}/{post_id}/insights"
    res = requests.get(url, params={
        "metric": "post_impressions,post_reach,post_reactions_by_type_total,post_clicks",
        "access_token": ACCESS_TOKEN
    })
    data = res.json()
    metrics = {}
    for item in data.get("data", []):
        metrics[item["name"]] = item.get("values", [{}])[0].get("value", 0)
    return metrics


def get_comments_on_post(post_id: str) -> list:
    url = f"{BASE_URL}/{post_id}/comments"
    res = requests.get(url, params={
        "fields": "message,like_count,from,created_time",
        "access_token": ACCESS_TOKEN
    })
    return res.json().get("data", [])
