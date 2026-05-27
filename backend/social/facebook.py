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
    """Busca métricas de engajamento de um post do Facebook.

    Usa dois endpoints:
    1. Fields API (/{post_id}?fields=...) — curtidas, comentários, shares (mais confiável)
    2. Insights API (/{post_id}/insights) — impressões e alcance
    """
    metrics = {}

    # 1. Curtidas, comentários e compartilhamentos via fields (dados públicos do post)
    try:
        res = requests.get(f"{BASE_URL}/{post_id}", params={
            "fields": "reactions.summary(true),comments.summary(true),shares",
            "access_token": ACCESS_TOKEN
        })
        data = res.json()
        if "error" not in data:
            metrics["likes"]    = data.get("reactions", {}).get("summary", {}).get("total_count", 0)
            metrics["comments"] = data.get("comments",  {}).get("summary", {}).get("total_count", 0)
            metrics["shares"]   = data.get("shares",    {}).get("count", 0) if "shares" in data else 0
        else:
            logger.warning(f"Erro ao buscar fields do post FB {post_id}: {data['error'].get('message')}")
    except Exception as e:
        logger.error(f"Erro ao buscar fields do post FB {post_id}: {e}")

    # 2. Impressões e alcance via Insights API (requer permissão read_insights)
    try:
        res = requests.get(f"{BASE_URL}/{post_id}/insights", params={
            "metric": "post_impressions,post_reach",
            "access_token": ACCESS_TOKEN
        })
        data = res.json()
        if "error" not in data:
            for item in data.get("data", []):
                metrics[item["name"]] = item.get("values", [{}])[0].get("value", 0)
        else:
            logger.warning(f"Insights indisponível para post FB {post_id}: {data['error'].get('message')}")
    except Exception as e:
        logger.error(f"Erro ao buscar insights do post FB {post_id}: {e}")

    return metrics


def get_comments_on_post(post_id: str) -> list:
    url = f"{BASE_URL}/{post_id}/comments"
    res = requests.get(url, params={
        "fields": "message,like_count,from,created_time",
        "access_token": ACCESS_TOKEN
    })
    return res.json().get("data", [])
