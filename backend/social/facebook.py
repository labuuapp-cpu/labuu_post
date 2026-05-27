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
    # Para vídeos, o 'id' retornado já é o ID do post da página
    return data


def post_image(image_path: str, caption: str) -> dict:
    """Publica imagem na página do Facebook.
    Retorna o resultado com 'id' normalizado para o ID do post (compound post_id quando disponível).
    """
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

    # A API retorna {"id": "<photo_id>", "post_id": "<page_id>_<post_num>"}
    # O post_id (compound) é necessário para métricas; normalizamos como 'id'
    if "post_id" in data:
        data["id"] = data["post_id"]
    return data


def find_post_by_timestamp(scheduled_at, window_minutes: int = 60) -> str:
    """Busca na lista de posts da página o compound post ID próximo ao horário agendado.
    Útil para corrigir IDs de foto (não-compound) armazenados anteriormente.
    Retorna compound post_id ou '' se não encontrar.
    """
    from datetime import timezone, timedelta, datetime

    try:
        res = requests.get(f"{BASE_URL}/{PAGE_ID}/posts", params={
            "fields": "id,created_time",
            "limit": 20,
            "access_token": ACCESS_TOKEN
        })
        posts = res.json().get("data", [])

        if hasattr(scheduled_at, 'tzinfo') and scheduled_at.tzinfo is None:
            scheduled_at = scheduled_at.replace(tzinfo=timezone.utc)

        window = timedelta(minutes=window_minutes)

        for p in posts:
            ts_str = p.get("created_time", "")
            if not ts_str:
                continue
            ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            diff = abs((ts - scheduled_at).total_seconds())
            if diff <= window.total_seconds():
                logger.info(f"Post FB encontrado por timestamp: {p['id']} (diff={diff:.0f}s)")
                return p["id"]
    except Exception as e:
        logger.error(f"Erro ao buscar post FB por timestamp: {e}")
    return ""


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

    Usa a API de fields para curtidas (reactions) e comentários — funciona com
    compound post IDs (format: {page_id}_{post_num}).

    Se receber um ID simples (photo object ID), tenta encontrar o compound post ID
    usando a lista de posts da página.
    """
    metrics = {}

    # Se o ID não é compound (não contém '_'), o post pode ser uma foto sem
    # compound ID — as reactions só funcionam com compound IDs
    effective_id = post_id

    # 1. Curtidas e comentários via fields (usa compound ID)
    try:
        res = requests.get(f"{BASE_URL}/{effective_id}", params={
            "fields": "reactions.summary(true),comments.summary(true)",
            "access_token": ACCESS_TOKEN
        })
        data = res.json()
        if "error" not in data:
            metrics["likes"]    = data.get("reactions", {}).get("summary", {}).get("total_count", 0)
            metrics["comments"] = data.get("comments",  {}).get("summary", {}).get("total_count", 0)
        else:
            err_msg = data["error"].get("message", "")
            logger.warning(f"Campos do post FB {effective_id} indisponíveis: {err_msg}")
    except Exception as e:
        logger.error(f"Erro ao buscar fields do post FB {effective_id}: {e}")

    return metrics


def get_comments_on_post(post_id: str) -> list:
    url = f"{BASE_URL}/{post_id}/comments"
    res = requests.get(url, params={
        "fields": "message,like_count,from,created_time",
        "access_token": ACCESS_TOKEN
    })
    return res.json().get("data", [])
