from google import genai
import json
import os
from datetime import date
from dotenv import load_dotenv

load_dotenv()

# Configuração do cliente usando a biblioteca nova google-genai
client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
MODEL_NAME = "gemini-2.5-flash"

BRAND_CONTEXT = """
Marca: Labuu
Segmento: Construção civil
Propósito: Conectar pedreiros/ajudantes que buscam trabalho com donos de obra que precisam contratar
Público: Tanto pedreiros/ajudantes buscando trampo quanto donos de obra contratando
Tom: Informal e natural — como se fosse uma conversa do dia a dia. Sem forçar gíria, sem ser formal demais
Nicho de hashtags: #construcaocivil #pedreiro #obra #maodeobra #construção #reformas #labuu
"""


def get_learned_patterns_context(db=None) -> str:
    if not db:
        return ""
    try:
        from models import LearnedPattern
        patterns = db.query(LearnedPattern).filter(
            LearnedPattern.sample_count >= 3
        ).order_by(LearnedPattern.avg_engagement.desc()).limit(10).all()
        if not patterns:
            return ""
        context = "\n\nPadrões que funcionam bem (baseado em posts anteriores):\n"
        for p in patterns:
            context += f"- {p.pattern_type}: '{p.pattern_value}' (engajamento médio: {p.avg_engagement:.1f}%)\n"
        return context
    except Exception:
        return ""


def get_brand_images_context(db=None) -> str:
    if not db:
        return ""
    try:
        from models import BrandImage
        images = db.query(BrandImage).all()
        if not images:
            return ""
        context = "\n\nImagens disponíveis na biblioteca da marca:\n"
        for img in images:
            context += f"- ID {img.id}: {img.filename} — {img.description}\n"
        return context
    except Exception:
        return ""


def _parse_json_response(text: str):
    text = text.strip()
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0]
    elif "```" in text:
        text = text.split("```")[1].split("```")[0]
    return json.loads(text.strip())


def generate_daily_content(slot: str = "morning", db=None) -> dict:
    slot_label = "manhã" if slot == "morning" else "tarde"
    today = date.today().strftime("%d/%m/%Y")
    patterns_ctx = get_learned_patterns_context(db)
    images_ctx = get_brand_images_context(db)

    prompt = f"""Você é um especialista em marketing de conteúdo para construção civil.
{BRAND_CONTEXT}{patterns_ctx}{images_ctx}

Hoje é {today} ({slot_label}). Gere o pacote de conteúdo diário para a Labuu.

Responda APENAS com um JSON válido neste formato exato:
{{
  "video_idea": "título curto da ideia de vídeo",
  "hook": "os primeiros 3 segundos do vídeo — frase de impacto que prende atenção",
  "script": "roteiro em 3-4 linhas, tom informal e natural",
  "cta": "chamada para ação no final",
  "image_recommendation": "ID X da biblioteca" ou null,
  "image_prompt": "prompt detalhado em português para gerar imagem com IA (caso não use imagem da biblioteca)",
  "video_prompt": "prompt detalhado para gerar ou editar vídeo no CapCut/Runway",
  "organic_tasks": [
    {{"platform": "instagram", "priority": "alta", "action": "descrição da tarefa"}},
    {{"platform": "facebook", "priority": "media", "action": "descrição da tarefa"}},
    {{"platform": "tiktok", "priority": "media", "action": "descrição da tarefa"}}
  ],
  "hashtags": "#hashtag1 #hashtag2 #hashtag3 #hashtag4 #hashtag5"
}}"""

    try:
        response = client.models.generate_content(model=MODEL_NAME, contents=prompt)
        return _parse_json_response(response.text)
    except Exception as e:
        print(f"Erro na geração de conteúdo: {e}")
        return {}


def generate_engagement_suggestions(platform: str, posts: list, db=None) -> list:
    if not posts:
        return []

    posts_text = "\n".join([
        f"- @{p.get('username', 'user')}: \"{p.get('caption', '')[:100]}\" ({p.get('likes', 0)} curtidas, {p.get('comments', 0)} comentários) — URL: {p.get('url', '')}"
        for p in posts[:5]
    ])

    prompt = f"""Você é especialista em marketing para construção civil.
{BRAND_CONTEXT}

Posts em alta no {platform} do nicho de construção civil:
{posts_text}

Para cada post, sugira um comentário natural e estratégico que:
1. Agrega valor à conversa
2. Apresenta ou reforça a Labuu de forma não invasiva
3. Soa como uma pessoa real, não como propaganda

Responda APENAS com JSON válido:
[
  {{
    "post_url": "url do post",
    "username": "@usuario",
    "priority": "alta" ou "media",
    "reason": "por que comentar aqui vale a pena (1 frase)",
    "suggested_comment": "o comentário sugerido"
  }}
]"""

    try:
        response = client.models.generate_content(model=MODEL_NAME, contents=prompt)
        return _parse_json_response(response.text)
    except Exception as e:
        print(f"Erro na sugestão de engajamento: {e}")
        return []


def generate_caption(title: str = "", hashtags: str = "", hook: str = "", script: str = "", video_idea: str = "") -> str:
    context_parts = []
    if video_idea: context_parts.append(f"Ideia do vídeo: {video_idea}")
    if title:      context_parts.append(f"Título: {title}")
    if hook:       context_parts.append(f"Hook (abertura): {hook}")
    if script:     context_parts.append(f"Roteiro: {script}")
    if hashtags:   context_parts.append(f"Hashtags: {hashtags}")
    context = "\n".join(context_parts) if context_parts else "Conteúdo sobre construção civil, pedreiros e contratação de mão de obra."

    prompt = f"""Você é especialista em marketing digital para construção civil.
{BRAND_CONTEXT}

Com base nas informações abaixo, escreva UMA legenda completa e pronta para postar no Instagram e Facebook.

{context}

Regras:
- Tom informal e natural, como conversa do dia a dia
- Entre 3 e 6 linhas
- Inclua uma chamada para ação no final (ex: "Baixa o app Labuu!", "Comenta aqui!", "Salva esse vídeo!")
- Deixe espaço para as hashtags (não inclua as hashtags no texto)
- Não use linguagem corporativa nem exagere nos emojis (máximo 3)

Responda APENAS com o texto da legenda, pronto para copiar e colar."""

    try:
        response = client.models.generate_content(model=MODEL_NAME, contents=prompt)
        return response.text.strip()
    except Exception as e:
        print(f"Erro na geração de legenda: {e}")
        return ""


def generate_caption_from_file(file_path: str) -> str:
    """Gera legenda analisando o conteúdo visual real da imagem ou vídeo via Gemini."""
    if not os.path.exists(file_path):
        return ""

    ext = file_path.lower().split(".")[-1]
    mime_map = {
        "jpg": "image/jpeg", "jpeg": "image/jpeg",
        "png": "image/png", "webp": "image/webp", "gif": "image/gif",
        "mp4": "video/mp4", "mov": "video/quicktime",
        "avi": "video/x-msvideo", "mkv": "video/x-matroska",
    }
    mime_type = mime_map.get(ext, "image/jpeg")
    is_video = mime_type.startswith("video/")
    media_label = "vídeo" if is_video else "imagem"

    prompt = f"""Você é especialista em marketing digital para construção civil.
{BRAND_CONTEXT}

Analise {'este vídeo' if is_video else 'esta imagem'} com atenção e escreva UMA legenda completa e pronta para postar no Instagram e Facebook.

Regras:
- Base a legenda no que você vê {'no vídeo' if is_video else 'na imagem'} — descreva o contexto de forma natural
- Tom informal e natural, como conversa do dia a dia
- Entre 3 e 6 linhas
- Inclua uma chamada para ação no final (ex: "Baixa o app Labuu!", "Comenta aqui!", "Salva esse vídeo!")
- Não inclua hashtags no texto (elas serão adicionadas depois)
- No máximo 3 emojis, nada corporativo

Responda APENAS com o texto da legenda, pronto para copiar e colar."""

    try:
        from google.genai import types as genai_types

        with open(file_path, "rb") as f:
            file_bytes = f.read()

        file_size_mb = len(file_bytes) / (1024 * 1024)

        if file_size_mb > 15:
            # Arquivo grande: usa File API do Gemini
            import tempfile
            suffix = f".{ext}"
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                tmp.write(file_bytes)
                tmp_path = tmp.name
            try:
                uploaded = client.files.upload(
                    path=tmp_path,
                    config=genai_types.UploadFileConfig(mime_type=mime_type, display_name=f"labuu_{media_label}")
                )
                response = client.models.generate_content(
                    model=MODEL_NAME,
                    contents=[uploaded, prompt]
                )
            finally:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
        else:
            # Arquivo pequeno: envia direto como bytes
            media_part = genai_types.Part.from_bytes(data=file_bytes, mime_type=mime_type)
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=[media_part, prompt]
            )

        return response.text.strip()
    except Exception as e:
        print(f"Erro na geração de legenda por arquivo: {e}")
        return ""


def generate_reply_suggestion(comment_text: str, likes: int) -> str:
    prompt = f"""Você é o responsável pelo marketing da Labuu (app de construção civil).
{BRAND_CONTEXT}

Um comentário no seu post recebeu {likes} curtidas:
"{comment_text}"

Escreva UMA resposta curta, natural e informal. Máximo 2 frases. Não use emojis em excesso.
Responda APENAS com o texto da resposta, sem aspas."""

    try:
        response = client.models.generate_content(model=MODEL_NAME, contents=prompt)
        return response.text.strip()
    except Exception as e:
        print(f"Erro na sugestão de resposta: {e}")
        return "Obrigado pelo comentário!"
