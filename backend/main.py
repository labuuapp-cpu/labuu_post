from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form, Request, Security
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.security import APIKeyHeader
from starlette.middleware.base import BaseHTTPMiddleware
from sqlalchemy.orm import Session
from datetime import date, datetime
from typing import Optional, List
import os, shutil, json, tempfile

from database import engine, get_db, Base
from models import BrandConfig, DailyContent, ScheduledPost, PostMetrics, BrandImage, LearnedPattern
from scheduler import start_scheduler
from dotenv import load_dotenv

load_dotenv()

Base.metadata.create_all(bind=engine)

# ─── Supabase Storage ─────────────────────────────────────────────────────────

SUPABASE_URL         = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")
UPLOAD_DIR           = os.getenv("UPLOAD_DIR", "../uploads")
ADMIN_TOKEN          = os.getenv("ADMIN_TOKEN", "")
ALLOWED_ORIGIN       = os.getenv("ALLOWED_ORIGIN", "*")

# ─── Auth ─────────────────────────────────────────────────────────────────────
_api_key_header = APIKeyHeader(name="X-Admin-Token", auto_error=False)

def require_auth(token: str = Security(_api_key_header)):
    """Protege as rotas da API com token de admin.
    Se ADMIN_TOKEN não estiver configurado, aceita tudo (dev mode)."""
    if not ADMIN_TOKEN:
        return   # sem token configurado = modo dev, sem bloqueio
    if token != ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Token inválido")

_sb_storage = None
if SUPABASE_URL and SUPABASE_SERVICE_KEY:
    try:
        from supabase import create_client
        _sb_storage = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY).storage
        print("[OK] Supabase Storage conectado")
    except Exception as e:
        print(f"[WARN] Supabase Storage indisponivel: {e}")


def _upload_file(bucket: str, filename: str, file_bytes: bytes,
                 content_type: str = "application/octet-stream") -> str:
    """Faz upload para Supabase Storage (ou pasta local como fallback)."""
    if _sb_storage:
        _sb_storage.from_(bucket).upload(
            filename, file_bytes,
            {"content-type": content_type, "x-upsert": "true"}
        )
        return filename          # armazena apenas o nome, URL é montada depois
    else:
        subdir = f"{UPLOAD_DIR}/{bucket}"
        os.makedirs(subdir, exist_ok=True)
        local_path = f"{subdir}/{filename}"
        with open(local_path, "wb") as f:
            f.write(file_bytes)
        return local_path


def _public_url(bucket: str, filename: str) -> str:
    """URL pública do arquivo (Supabase CDN ou estática local)."""
    if _sb_storage and SUPABASE_URL:
        return f"{SUPABASE_URL}/storage/v1/object/public/{bucket}/{filename}"
    # fallback local: filename pode ser caminho completo ou só nome
    if filename.startswith("/") or filename.startswith("../"):
        return f"/uploads/{bucket}/{os.path.basename(filename)}"
    return f"/uploads/{bucket}/{filename}"


def _download_to_temp(bucket: str, filename: str) -> str:
    """Baixa do Supabase Storage para arquivo temporário e retorna o caminho."""
    if _sb_storage:
        file_bytes = _sb_storage.from_(bucket).download(filename)
        ext = filename.rsplit(".", 1)[-1]
        tmp = tempfile.NamedTemporaryFile(suffix=f".{ext}", delete=False)
        tmp.write(file_bytes)
        tmp.close()
        return tmp.name
    else:
        # Fallback local — filename pode ser caminho absoluto já
        if os.path.exists(filename):
            return filename
        local = f"{UPLOAD_DIR}/{bucket}/{os.path.basename(filename)}"
        return local


def _delete_file(bucket: str, filename: str):
    """Remove do Supabase Storage ou do sistema de arquivos local."""
    if _sb_storage:
        try:
            _sb_storage.from_(bucket).remove([filename])
        except Exception as e:
            print(f"[WARN] Erro ao deletar {filename} do Storage: {e}")
    else:
        for candidate in [filename, f"{UPLOAD_DIR}/{bucket}/{os.path.basename(filename)}"]:
            if os.path.exists(candidate):
                os.remove(candidate)
                break


# ─── App ──────────────────────────────────────────────────────────────────────

app = FastAPI(title="Labuu Marketing Bot")

_origins = ["http://localhost:8000", "http://127.0.0.1:8000"]
if ALLOWED_ORIGIN and ALLOWED_ORIGIN != "*":
    _origins.append(ALLOWED_ORIGIN)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins if ALLOWED_ORIGIN != "*" else ["*"],
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type", "X-Admin-Token"],
)

# ─── Security Headers Middleware ──────────────────────────────────────────────
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        return response

app.add_middleware(SecurityHeadersMiddleware)

# Pasta local como fallback de uploads
os.makedirs(f"{UPLOAD_DIR}/images", exist_ok=True)
os.makedirs(f"{UPLOAD_DIR}/videos", exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")
app.mount("/static",  StaticFiles(directory="../frontend"),   name="static")


@app.get("/api/health")
def health_check():
    import requests
    status = {
        "google":      False,
        "meta":        False,
        "tiktok":      False,
        "supabase": _sb_storage is not None,
        "public_url":  bool(os.getenv("PUBLIC_BASE_URL")),
    }
    try:
        from ai_generator import client, MODEL_NAME
        client.models.generate_content(model=MODEL_NAME, contents="ping")
        status["google"] = True
    except: pass

    token = os.getenv("META_ACCESS_TOKEN")
    if token:
        res = requests.get(f"https://graph.facebook.com/v19.0/me?access_token={token}")
        status["meta"] = (res.status_code == 200)

    status["tiktok"] = bool(os.getenv("TIKTOK_ACCESS_TOKEN"))
    return status


@app.on_event("startup")
def startup():
    start_scheduler()
    db = next(get_db())
    if not db.query(BrandConfig).first():
        db.add(BrandConfig(
            audience="ambos",
            tone="informal natural",
            themes=["pedreiro", "obra", "contratação", "construção civil"],
            weekly_frequency=7
        ))
        db.commit()
    db.close()


@app.get("/")
def serve_frontend():
    return FileResponse("../frontend/index.html")


# ─── Brand Config ─────────────────────────────────────────────────────────────

@app.get("/api/brand")
def get_brand(db: Session = Depends(get_db), _=Depends(require_auth)):
    config = db.query(BrandConfig).first()
    if not config:
        raise HTTPException(404, "Configuração não encontrada")
    return {
        "audience":        config.audience,
        "tone":            config.tone,
        "themes":          config.themes,
        "weekly_frequency": config.weekly_frequency,
        "update_hour_1":   config.update_hour_1,
        "update_hour_2":   config.update_hour_2,
    }


@app.put("/api/brand")
def update_brand(
    audience: str         = Form(...),
    tone: str             = Form(...),
    themes: str           = Form("[]"),
    weekly_frequency: int = Form(7),
    db: Session           = Depends(get_db),
    _=Depends(require_auth),
):
    config = db.query(BrandConfig).first()
    if not config:
        config = BrandConfig()
        db.add(config)
    config.audience         = audience
    config.tone             = tone
    config.themes           = json.loads(themes)
    config.weekly_frequency = weekly_frequency
    db.commit()
    return {"ok": True}


# ─── Daily Content ─────────────────────────────────────────────────────────────

@app.get("/api/content/today")
def get_today_content(db: Session = Depends(get_db), _=Depends(require_auth)):
    today = date.today().isoformat()
    items = db.query(DailyContent).filter(DailyContent.date == today).all()
    return [
        {
            "id":                   c.id,
            "slot":                 c.slot,
            "video_idea":           c.video_idea,
            "hook":                 c.hook,
            "script":               c.script,
            "image_prompt":         c.image_prompt,
            "image_recommendation": c.image_recommendation,
            "video_prompt":         c.video_prompt,
            "organic_tasks":        c.organic_tasks,
            "engagement_posts":     c.engagement_posts,
            "created_at":           c.created_at.isoformat() if c.created_at else None,
        }
        for c in items
    ]


@app.post("/api/content/generate")
def generate_now(slot: str = "morning", db: Session = Depends(get_db), _=Depends(require_auth)):
    from scheduler import _generate_and_save_content
    _generate_and_save_content(slot)
    return {"ok": True, "message": f"Conteúdo '{slot}' gerado"}


# ─── Scheduled Posts ───────────────────────────────────────────────────────────

@app.get("/api/posts")
def list_posts(db: Session = Depends(get_db), _=Depends(require_auth)):
    posts = db.query(ScheduledPost).order_by(ScheduledPost.scheduled_at.desc()).limit(50).all()
    return [
        {
            "id":           p.id,
            "title":        p.title,
            "caption":      p.caption,
            "platforms":    p.platforms,
            "scheduled_at": p.scheduled_at.isoformat() if p.scheduled_at else None,
            "status":       p.status,
            "file_type":    p.file_type,
            "post_ids":     p.post_ids,
        }
        for p in posts
    ]


@app.post("/api/posts/upload")
async def upload_and_schedule(
    file: UploadFile       = File(...),
    title: str             = Form(""),
    caption: str           = Form(""),
    hashtags: str          = Form(""),
    platforms: str         = Form('["instagram","facebook","tiktok"]'),
    scheduled_at: str      = Form(...),
    db: Session            = Depends(get_db),
    _=Depends(require_auth),
):
    ext       = (file.filename or "upload").rsplit(".", 1)[-1].lower()
    file_type = "video" if ext in ["mp4", "mov", "avi", "mkv"] else "image"
    bucket    = "videos" if file_type == "video" else "images"
    filename  = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{file.filename}"

    file_bytes = await file.read()
    mime_map = {
        "jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
        "webp": "image/webp", "mp4": "video/mp4", "mov": "video/quicktime",
    }
    content_type = mime_map.get(ext, "application/octet-stream")

    stored_path = _upload_file(bucket, filename, file_bytes, content_type)

    post = ScheduledPost(
        title        = title,
        caption      = caption,
        hashtags     = hashtags,
        file_path    = stored_path,
        file_type    = file_type,
        platforms    = json.loads(platforms),
        # Normaliza para UTC (remove timezone info, armazena como UTC naive)
        scheduled_at = datetime.fromisoformat(scheduled_at.replace("Z", "+00:00")).replace(tzinfo=None),
        status       = "pending",
    )
    db.add(post)
    db.commit()
    db.refresh(post)
    return {"ok": True, "post_id": post.id}


@app.delete("/api/posts/{post_id}")
def delete_post(post_id: int, db: Session = Depends(get_db), _=Depends(require_auth)):
    post = db.query(ScheduledPost).filter(ScheduledPost.id == post_id).first()
    if not post:
        raise HTTPException(404, "Post não encontrado")
    db.delete(post)
    db.commit()
    return {"ok": True}


# ─── Metrics ───────────────────────────────────────────────────────────────────

@app.get("/api/metrics/summary")
def metrics_summary(db: Session = Depends(get_db), _=Depends(require_auth)):
    platforms = ["instagram", "facebook", "tiktok"]
    result = {}
    for platform in platforms:
        metrics = db.query(PostMetrics).filter(PostMetrics.platform == platform).all()
        if not metrics:
            result[platform] = {"views": 0, "likes": 0, "comments": 0, "shares": 0, "reach": 0, "posts": 0}
            continue
        result[platform] = {
            "views":          sum(m.views    for m in metrics),
            "likes":          sum(m.likes    for m in metrics),
            "comments":       sum(m.comments for m in metrics),
            "shares":         sum(m.shares   for m in metrics),
            "reach":          sum(m.reach    for m in metrics),
            "posts":          len(set(m.scheduled_post_id for m in metrics)),
            "avg_engagement": round(sum(m.engagement_rate for m in metrics) / len(metrics), 2),
        }
    return result


@app.get("/api/metrics/best-posts")
def best_posts(db: Session = Depends(get_db), _=Depends(require_auth)):
    metrics = db.query(PostMetrics).order_by(
        (PostMetrics.likes + PostMetrics.comments * 2 + PostMetrics.shares * 3).desc()
    ).limit(5).all()
    result = []
    for m in metrics:
        post = db.query(ScheduledPost).filter(ScheduledPost.id == m.scheduled_post_id).first()
        if post:
            result.append({
                "title":        post.title,
                "platform":     m.platform,
                "likes":        m.likes,
                "comments":     m.comments,
                "shares":       m.shares,
                "reach":        m.reach,
                "scheduled_at": post.scheduled_at.isoformat() if post.scheduled_at else None,
            })
    return result


# ─── Brand Images ──────────────────────────────────────────────────────────────

@app.get("/api/images")
def list_images(db: Session = Depends(get_db), _=Depends(require_auth)):
    images = db.query(BrandImage).all()
    return [
        {
            "id":          img.id,
            "filename":    img.filename,
            "file_path":   img.file_path,
            "description": img.description,
            "tags":        img.tags,
            "url":         _public_url("images", img.filename),
        }
        for img in images
    ]


@app.post("/api/images/upload")
async def upload_brand_image(
    file: UploadFile    = File(...),
    description: str    = Form(""),
    tags: str           = Form("[]"),
    db: Session         = Depends(get_db),
    _=Depends(require_auth),
):
    filename   = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{file.filename}"
    file_bytes = await file.read()
    ext        = filename.rsplit(".", 1)[-1].lower()
    mime_map   = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp"}
    ct         = mime_map.get(ext, "image/jpeg")

    stored_path = _upload_file("images", filename, file_bytes, ct)

    img = BrandImage(
        filename    = filename,
        file_path   = stored_path,
        description = description,
        tags        = json.loads(tags),
    )
    db.add(img)
    db.commit()
    db.refresh(img)
    return {"ok": True, "image_id": img.id}


@app.post("/api/images/{image_id}/suggest-caption")
def suggest_caption_for_image(image_id: int, db: Session = Depends(get_db), _=Depends(require_auth)):
    """Gera legenda analisando visualmente a imagem da biblioteca."""
    img = db.query(BrandImage).filter(BrandImage.id == image_id).first()
    if not img:
        raise HTTPException(404, "Imagem não encontrada")

    tmp_path = None
    try:
        tmp_path = _download_to_temp("images", img.filename)
        from ai_generator import generate_caption_from_file
        caption = generate_caption_from_file(tmp_path)
    finally:
        # Remove temp apenas se foi criado pelo download (não é caminho local original)
        if tmp_path and _sb_storage and os.path.exists(tmp_path):
            os.unlink(tmp_path)

    if not caption:
        raise HTTPException(500, "Erro ao gerar legenda")
    return {"caption": caption}


@app.delete("/api/images/{image_id}")
def delete_image(image_id: int, db: Session = Depends(get_db), _=Depends(require_auth)):
    img = db.query(BrandImage).filter(BrandImage.id == image_id).first()
    if not img:
        raise HTTPException(404, "Imagem não encontrada")
    _delete_file("images", img.filename)
    db.delete(img)
    db.commit()
    return {"ok": True}


# ─── Caption Suggestions ───────────────────────────────────────────────────────

@app.post("/api/content/suggest-caption")
async def suggest_caption(
    title: str      = Form(""),
    hashtags: str   = Form(""),
    hook: str       = Form(""),
    script: str     = Form(""),
    video_idea: str = Form(""),
    db: Session     = Depends(get_db),
    _=Depends(require_auth),
):
    from ai_generator import generate_caption
    caption = generate_caption(
        title=title, hashtags=hashtags,
        hook=hook, script=script, video_idea=video_idea,
    )
    if not caption:
        raise HTTPException(500, "Erro ao gerar legenda")
    return {"caption": caption}


@app.post("/api/content/suggest-caption-from-file")
async def suggest_caption_from_uploaded_file(file: UploadFile = File(...), _=Depends(require_auth)):
    """Recebe arquivo (imagem/vídeo) e gera legenda baseada no conteúdo visual."""
    ext = (file.filename or "upload").rsplit(".", 1)[-1].lower()
    with tempfile.NamedTemporaryFile(suffix=f".{ext}", delete=False) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name
    try:
        from ai_generator import generate_caption_from_file
        caption = generate_caption_from_file(tmp_path)
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
    if not caption:
        raise HTTPException(500, "Erro ao gerar legenda")
    return {"caption": caption}


# ─── Learned Patterns ──────────────────────────────────────────────────────────

@app.get("/api/patterns")
def get_patterns(db: Session = Depends(get_db), _=Depends(require_auth)):
    patterns = db.query(LearnedPattern).filter(
        LearnedPattern.sample_count >= 2
    ).order_by(LearnedPattern.avg_engagement.desc()).all()
    return [
        {
            "type":           p.pattern_type,
            "value":          p.pattern_value,
            "avg_engagement": round(p.avg_engagement, 2),
            "sample_count":   p.sample_count,
        }
        for p in patterns
    ]
