import os
import requests
from dotenv import load_dotenv

load_dotenv()

CLIENT_KEY = os.getenv("TIKTOK_CLIENT_KEY")
ACCESS_TOKEN = os.getenv("TIKTOK_ACCESS_TOKEN")
BASE_URL = "https://open.tiktokapis.com/v2"

NICHE_HASHTAGS = [
    "construcaocivil", "pedreiro", "obra", "maodeobra",
    "construção", "reformas", "engenharia", "arquitetura",
    "construindo", "acabamento", "labuu"
]


def init_video_upload(video_size: int, chunk_size: int, total_chunk_count: int) -> dict:
    url = f"{BASE_URL}/post/publish/video/init/"
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "post_info": {
            "title": "",
            "privacy_level": "PUBLIC_TO_EVERYONE",
            "disable_duet": False,
            "disable_comment": False,
            "disable_stitch": False
        },
        "source_info": {
            "source": "FILE_UPLOAD",
            "video_size": video_size,
            "chunk_size": chunk_size,
            "total_chunk_count": total_chunk_count
        }
    }
    res = requests.post(url, json=payload, headers=headers)
    return res.json()


def upload_video_chunk(upload_url: str, chunk_data: bytes, start: int, end: int, total: int) -> int:
    headers = {
        "Content-Range": f"bytes {start}-{end}/{total}",
        "Content-Type": "video/mp4"
    }
    res = requests.put(upload_url, data=chunk_data, headers=headers)
    return res.status_code


def publish_video(publish_id: str, caption: str) -> dict:
    url = f"{BASE_URL}/post/publish/video/init/"
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "post_id": publish_id,
        "post_info": {
            "title": caption[:150],
            "privacy_level": "PUBLIC_TO_EVERYONE"
        }
    }
    res = requests.post(url, json=payload, headers=headers)
    return res.json()


def upload_video(video_path: str, caption: str) -> dict:
    import os
    video_size = os.path.getsize(video_path)
    # TikTok recomenda chunks de 5MB a 64MB. Usaremos 10MB.
    chunk_size = 10 * 1024 * 1024
    total_chunks = (video_size + chunk_size - 1) // chunk_size

    # 1. Inicializar
    init_res = init_video_upload(video_size, chunk_size, total_chunks)
    if "data" not in init_res:
        return {"error": init_res}
    
    upload_url = init_res["data"]["upload_url"]
    publish_id = init_res["data"]["publish_id"]

    # 2. Upload Chunks
    with open(video_path, "rb") as f:
        for i in range(total_chunks):
            start = i * chunk_size
            chunk_data = f.read(chunk_size)
            end = start + len(chunk_data) - 1
            status = upload_video_chunk(upload_url, chunk_data, start, end, video_size)
            if status not in [200, 201]:
                return {"error": f"Chunk {i} failed with status {status}"}

    # 3. Publicar (Na verdade a API do TikTok as vezes publica automático após o último chunk, 
    # mas o fluxo oficial pede confirmação ou processamento)
    # No V2, o publish_id é usado para acompanhar ou disparar.
    return {"publish_id": publish_id, "status": "processing"}


def get_trending_hashtags() -> list:
    return [{"tag": h, "url": f"https://www.tiktok.com/tag/{h}"} for h in NICHE_HASHTAGS]


def get_video_metrics(video_id: str) -> dict:
    url = f"{BASE_URL}/video/query/"
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "filters": {"video_ids": [video_id]},
        "fields": ["view_count", "like_count", "comment_count", "share_count"]
    }
    res = requests.post(url, json=payload, headers=headers)
    data = res.json()
    videos = data.get("data", {}).get("videos", [])
    return videos[0] if videos else {}
