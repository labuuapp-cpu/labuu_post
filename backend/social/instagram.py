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
    """Busca métricas de engajamento de uma mídia do Instagram.

    Estratégia:
    1. Campos diretos (like_count, comments_count) — mais confiável, sem permissão especial
    2. Insights API — impressões, alcance, shares, saves (requer permissão de insights)
    Se o media_id for inválido/inacessível, retorna {}
    """
    metrics = {}

    # 1. Curtidas e comentários via campos diretos do objeto de mídia
    try:
        res = requests.get(f"{BASE_URL}/{media_id}", params={
            "fields": "like_count,comments_count",
            "access_token": ACCESS_TOKEN
        })
        data = res.json()
        if "error" not in data:
            metrics["likes"]    = data.get("like_count", 0)
            metrics["comments"] = data.get("comments_count", 0)
        else:
            logger.warning(f"IG media {media_id} inacessível: {data['error'].get('message')}")
            return {}  # ID inválido — retorna vazio para que o caller possa reagir
    except Exception as e:
        logger.error(f"Erro ao buscar fields da mídia IG {media_id}: {e}")
        return {}

    # 2. Impressões, alcance, shares e saves via Insights (opcional, requer permissão)
    try:
        res = requests.get(f"{BASE_URL}/{media_id}/insights", params={
            "metric": "impressions,reach,shares,saved",
            "access_token": ACCESS_TOKEN
        })
        data = res.json()
        if "error" not in data:
            for item in data.get("data", []):
                metrics[item["name"]] = item.get("values", [{}])[0].get("value", 0)
    except Exception:
        pass  # insights é opcional

    return metrics


def find_media_by_timestamp(scheduled_at, window_minutes: int = 60) -> str:
    """Busca na lista de mídias da conta o ID da mídia publicada próxima ao horário agendado.
    Útil para corrigir IDs inválidos armazenados após publicação.
    Retorna o media_id correto ou '' se não encontrar.
    """
    from datetime import timezone, timedelta

    try:
        res = requests.get(f"{BASE_URL}/{IG_ACCOUNT_ID}/media", params={
            "fields": "id,timestamp",
            "limit": 20,
            "access_token": ACCESS_TOKEN
        })
        medias = res.json().get("data", [])

        # Garante que scheduled_at é timezone-aware UTC
        if hasattr(scheduled_at, 'tzinfo') and scheduled_at.tzinfo is None:
            scheduled_at = scheduled_at.replace(tzinfo=timezone.utc)

        window = timedelta(minutes=window_minutes)

        for m in medias:
            ts_str = m.get("timestamp", "")
            if not ts_str:
                continue
            from datetime import datetime
            ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            diff = abs((ts - scheduled_at).total_seconds())
            if diff <= window.total_seconds():
                logger.info(f"Mídia encontrada por timestamp: {m['id']} (diff={diff:.0f}s)")
                return m["id"]
    except Exception as e:
        logger.error(f"Erro ao buscar mídia por timestamp: {e}")
    return ""


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
