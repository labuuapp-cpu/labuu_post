import os
import requests
import time
import logging
from dotenv import load_dotenv

logger = logging.getLogger(__name__)
load_dotenv()

ACCESS_TOKEN = os.getenv("META_ACCESS_TOKEN")
IG_ACCOUNT_ID = os.getenv("INSTAGRAM_ACCOUNT_ID")
BASE_URL = "https://graph.facebook.com/v19.0"


def _wait_for_media(container_id: str, timeout: int = 60) -> bool:
    """Aguarda o processamento da mídia pela Meta."""
    start_time = time.time()
    while time.time() - start_time < timeout:
        res = requests.get(f"{BASE_URL}/{container_id}", params={
            "fields": "status_code",
            "access_token": ACCESS_TOKEN
        })
        status = res.json()
        if status.get("status_code") == "FINISHED":
            return True
        if status.get("status_code") == "ERROR":
            logger.error(f"Erro no processamento da mídia {container_id}: {status}")
            return False
        time.sleep(5)
    return False


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

    # Reels sempre precisam aguardar processamento
    if not _wait_for_media(container["id"]):
        return {"error": "Timeout ou erro no processamento do vídeo"}

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

    # Aguarda um pouco para garantir que a imagem foi baixada pela Meta
    time.sleep(10)

    publish_url = f"{BASE_URL}/{IG_ACCOUNT_ID}/media_publish"
    pub = requests.post(publish_url, data={
        "creation_id": container["id"],
        "access_token": ACCESS_TOKEN
    })
    
    # Se falhar porque a mídia ainda não está pronta, tenta mais uma vez
    data = pub.json()
    if "error" in data and data["error"].get("error_subcode") == 2207027:
        logger.info("Mídia não pronta, tentando novamente em 15 segundos...")
        time.sleep(15)
        pub = requests.post(publish_url, data={
            "creation_id": container["id"],
            "access_token": ACCESS_TOKEN
        })
        return pub.json()
        
    return data


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
