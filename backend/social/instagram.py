import os
import requests
from dotenv import load_dotenv

load_dotenv()

ACCESS_TOKEN = os.getenv("META_ACCESS_TOKEN")
IG_ACCOUNT_ID = os.getenv("INSTAGRAM_ACCOUNT_ID")
BASE_URL = "https://graph.facebook.com/v19.0"


def post_video(video_url: str, caption: str) -> dict:
    container_url = f"{BASE_URL}/{IG_ACCOUNT_ID}/media"
    res = requests.post(container_url, data={
        "media_type": "REELS",
        "video_url": video_url,
        "caption": caption,
        "access_token": ACCESS_TOKEN
    })
    container = res.json()
    if "id" not in container:
        return {"error": container}

    publish_url = f"{BASE_URL}/{IG_ACCOUNT_ID}/media_publish"
    pub = requests.post(publish_url, data={
        "creation_id": container["id"],
        "access_token": ACCESS_TOKEN
    })
    return pub.json()


def post_image(image_url: str, caption: str) -> dict:
    container_url = f"{BASE_URL}/{IG_ACCOUNT_ID}/media"
    res = requests.post(container_url, data={
        "image_url": image_url,
        "caption": caption,
        "access_token": ACCESS_TOKEN
    })
    container = res.json()
    if "id" not in container:
        return {"error": container}

    publish_url = f"{BASE_URL}/{IG_ACCOUNT_ID}/media_publish"
    pub = requests.post(publish_url, data={
        "creation_id": container["id"],
        "access_token": ACCESS_TOKEN
    })
    return pub.json()


def get_post_metrics(media_id: str) -> dict:
    url = f"{BASE_URL}/{media_id}/insights"
    res = requests.get(url, params={
        "metric": "impressions,reach,likes,comments,shares,saved,plays",
        "access_token": ACCESS_TOKEN
    })
    data = res.json()
    metrics = {}
    for item in data.get("data", []):
        metrics[item["name"]] = item.get("values", [{}])[0].get("value", 0)
    return metrics


def get_account_insights() -> dict:
    url = f"{BASE_URL}/{IG_ACCOUNT_ID}/insights"
    res = requests.get(url, params={
        "metric": "follower_count,reach,impressions,profile_views",
        "period": "day",
        "access_token": ACCESS_TOKEN
    })
    return res.json()


def get_comments_on_post(media_id: str) -> list:
    url = f"{BASE_URL}/{media_id}/comments"
    res = requests.get(url, params={
        "fields": "text,like_count,username,timestamp",
        "access_token": ACCESS_TOKEN
    })
    return res.json().get("data", [])
