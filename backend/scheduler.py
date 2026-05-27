from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import date, datetime
import logging

logger = logging.getLogger(__name__)
scheduler = BackgroundScheduler(timezone="America/Sao_Paulo")


def run_morning_update():
    logger.info(f"[{datetime.now()}] Rodando atualização das 08h")
    _generate_and_save_content("morning")


def run_afternoon_update():
    logger.info(f"[{datetime.now()}] Rodando atualização das 15h")
    _generate_and_save_content("afternoon")


def _generate_and_save_content(slot: str):
    try:
        from database import SessionLocal
        from models import DailyContent
        from ai_generator import generate_daily_content
        from engagement.instagram_finder import find_hot_posts as ig_posts
        from engagement.facebook_finder import find_hot_posts as fb_posts, get_suggested_groups
        from social.tiktok import get_trending_hashtags
        from ai_generator import generate_engagement_suggestions

        db = SessionLocal()
        today_str = date.today().isoformat()

        existing = db.query(DailyContent).filter(
            DailyContent.date == today_str,
            DailyContent.slot == slot
        ).first()
        if existing:
            db.close()
            return

        content = generate_daily_content(slot=slot, db=db)

        ig_hot = ig_posts(max_posts=5)
        fb_hot = fb_posts(max_posts=4)
        tt_tags = get_trending_hashtags()

        ig_suggestions = generate_engagement_suggestions("Instagram", ig_hot, db)
        fb_suggestions = generate_engagement_suggestions("Facebook", fb_hot, db)

        engagement_data = {
            "instagram": ig_suggestions,
            "facebook": fb_suggestions,
            "facebook_groups": get_suggested_groups(),
            "tiktok_hashtags": tt_tags
        }

        record = DailyContent(
            date=today_str,
            slot=slot,
            video_idea=content.get("video_idea"),
            hook=content.get("hook"),
            script=content.get("script"),
            image_prompt=content.get("image_prompt"),
            image_recommendation=content.get("image_recommendation"),
            video_prompt=content.get("video_prompt"),
            organic_tasks=content.get("organic_tasks", []),
            engagement_posts=engagement_data
        )
        db.add(record)
        db.commit()
        db.close()
        logger.info(f"Conteúdo {slot} gerado e salvo com sucesso")

    except Exception as e:
        logger.error(f"Erro ao gerar conteúdo {slot}: {e}")


def process_scheduled_posts():
    try:
        from database import SessionLocal
        from models import ScheduledPost
        from datetime import datetime, timezone
        import os

        db = SessionLocal()
        # Usar naive UTC para comparar com scheduled_at que é armazenado como naive UTC.
        # Evita problemas com PostgreSQL (TIMESTAMP vs TIMESTAMPTZ) e SQLite.
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        pending = db.query(ScheduledPost).filter(
            ScheduledPost.status == "pending",
            ScheduledPost.scheduled_at <= now
        ).all()

        for post in pending:
            _publish_post(post, db)

        db.close()
    except Exception as e:
        logger.error(f"Erro ao processar posts agendados: {e}")


def _resolve_post_file(post):
    """Retorna (local_path, public_url, cleanup_temp) para o arquivo do post.
    - local_path : caminho local temporário (usado por Facebook/TikTok)
    - public_url : URL acessível publicamente (usada pelo Instagram)
    - cleanup_temp : True se local_path é temp e deve ser deletado ao final
    """
    import os, tempfile
    from dotenv import load_dotenv
    load_dotenv()

    SUPABASE_URL     = os.getenv("SUPABASE_URL", "")
    SUPABASE_SVC_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")
    PUBLIC_BASE      = os.getenv("PUBLIC_BASE_URL", "").rstrip("/")
    UPLOAD_DIR       = os.getenv("UPLOAD_DIR", "../uploads")
    bucket           = "videos" if post.file_type == "video" else "images"
    filename         = os.path.basename(post.file_path)

    if SUPABASE_URL and SUPABASE_SVC_KEY:
        from supabase import create_client
        sb = create_client(SUPABASE_URL, SUPABASE_SVC_KEY)

        # Para imagens (bucket público): URL pública direta
        # Para vídeos (bucket privado): URL assinada com 1h de validade
        if bucket == "images":
            public_url = f"{SUPABASE_URL}/storage/v1/object/public/{bucket}/{filename}"
        else:
            try:
                signed = sb.storage.from_(bucket).create_signed_url(filename, 3600)
                public_url = signed.get("signedURL") or signed.get("signed_url", "")
            except Exception as e:
                logger.error(f"Erro ao gerar URL assinada para {filename}: {e}")
                public_url = f"{SUPABASE_URL}/storage/v1/object/public/{bucket}/{filename}"

        # Baixar para arquivo temp (Facebook/TikTok precisam de arquivo local)
        try:
            file_bytes = sb.storage.from_(bucket).download(filename)
            ext = filename.rsplit(".", 1)[-1]
            tmp = tempfile.NamedTemporaryFile(suffix=f".{ext}", delete=False)
            tmp.write(file_bytes)
            tmp.close()
            return tmp.name, public_url, True
        except Exception as e:
            logger.error(f"Erro ao baixar {filename} do Supabase: {e}")
            return None, public_url, False
    else:
        # Fallback local
        local_path = os.path.abspath(post.file_path)
        subdir     = bucket
        public_url = f"{PUBLIC_BASE}/uploads/{subdir}/{filename}"
        return local_path, public_url, False


def _publish_post(post, db):
    from sqlalchemy.orm.attributes import flag_modified

    platforms = post.platforms or []
    post_ids  = {}
    errors    = []

    local_path, public_url, cleanup_temp = _resolve_post_file(post)
    caption = f"{post.caption}\n\n{post.hashtags}" if post.hashtags else post.caption

    try:
        # ── Instagram (usa URL pública/assinada) ──────────────────────────
        if "instagram" in platforms:
            from social.instagram import post_video, post_image
            try:
                if post.file_type == "video":
                    res = post_video(public_url, caption)
                else:
                    res = post_image(public_url, caption)
                post_ids["instagram"] = res.get("id", res.get("error", ""))
                logger.info(f"Post {post.id} → Instagram OK: {post_ids['instagram']}")
            except Exception as e:
                logger.error(f"Erro Instagram post {post.id}: {e}")
                post_ids["instagram"] = f"error: {str(e)}"
                errors.append("instagram")

        # ── Facebook (precisa de arquivo local) ───────────────────────────
        if "facebook" in platforms:
            if local_path:
                from social.facebook import post_video, post_image
                try:
                    if post.file_type == "video":
                        res = post_video(local_path, caption, post.title or "")
                    else:
                        res = post_image(local_path, caption)
                    post_ids["facebook"] = res.get("id", res.get("error", ""))
                    logger.info(f"Post {post.id} → Facebook OK: {post_ids['facebook']}")
                except Exception as e:
                    logger.error(f"Erro Facebook post {post.id}: {e}")
                    post_ids["facebook"] = f"error: {str(e)}"
                    errors.append("facebook")
            else:
                logger.error(f"Post {post.id} → Facebook PULADO: arquivo local indisponível")
                post_ids["facebook"] = "error: arquivo nao disponivel localmente"
                errors.append("facebook")

        # ── TikTok (precisa de arquivo local, só vídeo) ───────────────────
        if "tiktok" in platforms:
            if local_path and post.file_type == "video":
                from social.tiktok import upload_video
                try:
                    res = upload_video(local_path, caption)
                    post_ids["tiktok"] = res.get("publish_id", res.get("error", "unknown_error"))
                    logger.info(f"Post {post.id} → TikTok OK: {post_ids['tiktok']}")
                except Exception as e:
                    logger.error(f"Erro TikTok post {post.id}: {e}")
                    post_ids["tiktok"] = f"error: {str(e)}"
                    errors.append("tiktok")
            elif post.file_type != "video":
                logger.warning(f"Post {post.id} → TikTok PULADO: apenas vídeos são suportados")
                post_ids["tiktok"] = "error: apenas videos sao aceitos pelo TikTok"
            else:
                logger.error(f"Post {post.id} → TikTok PULADO: arquivo local indisponível")
                post_ids["tiktok"] = "error: arquivo nao disponivel localmente"
                errors.append("tiktok")

        # ── Determinar status final ───────────────────────────────────────
        attempted = [p for p in platforms if p in post_ids]
        succeeded = [p for p in attempted if not str(post_ids[p]).startswith("error")]

        if not succeeded:
            post.status = "failed"
        elif len(errors) > 0:
            post.status = "partial"   # publicou em pelo menos uma plataforma
        else:
            post.status = "posted"

        # flag_modified garante que SQLAlchemy detecta a mudança no JSON
        post.post_ids = post_ids
        flag_modified(post, "post_ids")
        db.commit()
        logger.info(f"Post {post.id} status={post.status} ids={post_ids}")

    except Exception as e:
        post.status = "failed"
        db.commit()
        logger.error(f"Erro fatal ao publicar post {post.id}: {e}")
    finally:
        if cleanup_temp and local_path:
            import os as _os
            if _os.path.exists(local_path):
                _os.unlink(local_path)


def collect_metrics():
    """Coleta métricas de engajamento de todos os posts publicados.

    Inclui posts com status 'posted' e 'partial' (publicado em pelo menos uma plataforma).
    Sem cutoff mínimo de tempo — coleta a qualquer momento.
    """
    try:
        from database import SessionLocal
        from models import ScheduledPost, PostMetrics

        db = SessionLocal()
        posts = db.query(ScheduledPost).filter(
            ScheduledPost.status.in_(["posted", "partial"])
        ).all()

        logger.info(f"[collect_metrics] {len(posts)} posts para coletar métricas")
        for post in posts:
            _collect_post_metrics(post, db)

        db.close()
    except Exception as e:
        logger.error(f"Erro ao coletar métricas: {e}")


def _collect_post_metrics(post, db):
    """Coleta e salva (ou atualiza) métricas de um post em todas as plataformas publicadas."""
    from models import PostMetrics
    from social.instagram import get_post_metrics as ig_metrics
    from social.facebook import get_post_metrics as fb_metrics

    post_ids = post.post_ids or {}

    def _upsert(platform: str, **values):
        """Atualiza registro existente ou insere novo."""
        existing = db.query(PostMetrics).filter(
            PostMetrics.scheduled_post_id == post.id,
            PostMetrics.platform == platform
        ).first()
        if existing:
            for k, v in values.items():
                setattr(existing, k, v)
        else:
            db.add(PostMetrics(scheduled_post_id=post.id, platform=platform, **values))

    # ── Instagram ─────────────────────────────────────────────────────────────
    ig_id = post_ids.get("instagram", "")
    if ig_id and not str(ig_id).startswith("error"):
        try:
            m = ig_metrics(ig_id)
            _upsert(
                "instagram",
                views=m.get("plays", 0) or m.get("impressions", 0),
                likes=m.get("likes", 0),
                comments=m.get("comments", 0),
                shares=m.get("shares", 0),
                reach=m.get("reach", 0),
            )
            logger.info(f"Post {post.id} IG metrics: {m}")
        except Exception as e:
            logger.error(f"Erro ao coletar métricas IG do post {post.id}: {e}")

    # ── Facebook ──────────────────────────────────────────────────────────────
    fb_id = post_ids.get("facebook", "")
    if fb_id and not str(fb_id).startswith("error"):
        try:
            m = fb_metrics(fb_id)
            _upsert(
                "facebook",
                views=m.get("post_impressions", 0),
                likes=m.get("likes", 0),
                comments=m.get("comments", 0),
                shares=m.get("shares", 0),
                reach=m.get("post_reach", 0),
            )
            logger.info(f"Post {post.id} FB metrics: {m}")
        except Exception as e:
            logger.error(f"Erro ao coletar métricas FB do post {post.id}: {e}")

    db.commit()


def update_learned_patterns():
    try:
        from database import SessionLocal
        from models import ScheduledPost, PostMetrics, LearnedPattern
        from sqlalchemy import func

        db = SessionLocal()
        posts = db.query(ScheduledPost).filter(
            ScheduledPost.status == "posted"
        ).all()

        pattern_data = {}
        for post in posts:
            metrics = db.query(PostMetrics).filter(
                PostMetrics.scheduled_post_id == post.id
            ).all()
            if not metrics:
                continue

            total_engagement = sum(
                m.likes + m.comments * 2 + m.shares * 3
                for m in metrics
            )
            avg_reach = sum(m.reach for m in metrics) / len(metrics) if metrics else 1
            eng_rate = (total_engagement / avg_reach * 100) if avg_reach > 0 else 0

            hour = post.scheduled_at.hour if post.scheduled_at else 0
            hour_key = ("posting_hour", str(hour))
            if hour_key not in pattern_data:
                pattern_data[hour_key] = []
            pattern_data[hour_key].append(eng_rate)

        for (ptype, pvalue), rates in pattern_data.items():
            avg = sum(rates) / len(rates)
            existing = db.query(LearnedPattern).filter(
                LearnedPattern.pattern_type == ptype,
                LearnedPattern.pattern_value == pvalue
            ).first()
            if existing:
                existing.avg_engagement = avg
                existing.sample_count = len(rates)
            else:
                db.add(LearnedPattern(
                    pattern_type=ptype,
                    pattern_value=pvalue,
                    avg_engagement=avg,
                    sample_count=len(rates)
                ))
        db.commit()
        db.close()
    except Exception as e:
        logger.error(f"Erro ao atualizar padrões: {e}")


def cleanup_old_content():
    """Remove daily_content com mais de 3 dias e posts already-posted/failed com mais de 7 dias."""
    try:
        from database import SessionLocal
        from models import DailyContent, ScheduledPost
        from datetime import datetime, timezone, timedelta

        db  = SessionLocal()
        now = datetime.now(timezone.utc).replace(tzinfo=None)   # naive UTC

        # Conteúdo diário: apaga tudo com mais de 3 dias
        cutoff_content = (now - timedelta(days=3)).date().isoformat()
        deleted_content = db.query(DailyContent).filter(
            DailyContent.date < cutoff_content
        ).delete(synchronize_session=False)

        # Posts publicados/falhos: apaga com mais de 7 dias
        cutoff_posts = now - timedelta(days=7)
        deleted_posts = db.query(ScheduledPost).filter(
            ScheduledPost.status.in_(["posted", "failed"]),
            ScheduledPost.scheduled_at < cutoff_posts
        ).delete(synchronize_session=False)

        db.commit()
        db.close()
        logger.info(f"[Cleanup] Removidos {deleted_content} conteúdos e {deleted_posts} posts antigos")
    except Exception as e:
        logger.error(f"Erro no cleanup: {e}")


def start_scheduler():
    scheduler.add_job(run_morning_update,      CronTrigger(hour=8,  minute=0), id="morning_content")
    scheduler.add_job(run_afternoon_update,    CronTrigger(hour=15, minute=0), id="afternoon_content")
    scheduler.add_job(process_scheduled_posts, "interval", minutes=5,          id="post_publisher")
    scheduler.add_job(collect_metrics,         CronTrigger(hour=10, minute=0), id="metrics_collector")
    scheduler.add_job(update_learned_patterns, CronTrigger(hour=23, minute=0), id="pattern_learner")
    # Limpeza a cada 3 dias às 03h
    scheduler.add_job(cleanup_old_content,     CronTrigger(hour=3,  minute=0, day="*/3"), id="content_cleanup")
    scheduler.start()
    logger.info("Scheduler iniciado — atualizações às 08h e 15h, limpeza a cada 3 dias")
