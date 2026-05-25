"""
Script para obter o Access Token do TikTok via OAuth 2.0.

Como usar:
1. Coloque CLIENT_KEY e CLIENT_SECRET abaixo (ou no .env)
2. Rode: python tiktok_auth.py
3. Abra o link no navegador, autorize sua conta TikTok
4. Cole aqui a URL de redirecionamento completa
5. O script imprime o access_token pronto para colocar no .env
"""

import os
import secrets
import urllib.parse
import requests
from dotenv import load_dotenv

load_dotenv()

CLIENT_KEY    = os.getenv("TIKTOK_CLIENT_KEY", "")
CLIENT_SECRET = os.getenv("TIKTOK_CLIENT_SECRET", "")

REDIRECT_URI  = "https://localhost/"   # deve estar cadastrado no app TikTok
SCOPES        = "user.info.basic,video.publish,video.upload"

AUTH_URL      = "https://www.tiktok.com/v2/auth/authorize/"
TOKEN_URL     = "https://open.tiktokapis.com/v2/oauth/token/"


def build_auth_url(state: str) -> str:
    params = {
        "client_key":     CLIENT_KEY,
        "response_type":  "code",
        "scope":          SCOPES,
        "redirect_uri":   REDIRECT_URI,
        "state":          state,
    }
    return AUTH_URL + "?" + urllib.parse.urlencode(params)


def exchange_code(code: str) -> dict:
    res = requests.post(TOKEN_URL, data={
        "client_key":     CLIENT_KEY,
        "client_secret":  CLIENT_SECRET,
        "code":           code,
        "grant_type":     "authorization_code",
        "redirect_uri":   REDIRECT_URI,
    }, headers={"Content-Type": "application/x-www-form-urlencoded"})
    return res.json()


def main():
    if not CLIENT_KEY or not CLIENT_SECRET:
        print("\nERRO: Coloque TIKTOK_CLIENT_KEY e TIKTOK_CLIENT_SECRET no .env primeiro.\n")
        return

    state = secrets.token_urlsafe(16)
    url   = build_auth_url(state)

    print("\n" + "="*60)
    print("PASSO 1 — Abra este link no navegador e autorize:")
    print("="*60)
    print(url)
    print("="*60)
    print("\nDepois de autorizar, o TikTok vai redirecionar para uma")
    print(f"URL começando com: {REDIRECT_URI}")
    print("(pode dar erro de conexão no navegador — isso é normal)")
    print("\nCopie a URL COMPLETA da barra de endereço e cole aqui:")

    callback = input("\nURL de redirecionamento: ").strip()

    parsed = urllib.parse.urlparse(callback)
    params = urllib.parse.parse_qs(parsed.query)

    if "error" in params:
        print(f"\nERRO retornado pelo TikTok: {params.get('error_description', params['error'])}")
        return

    if "code" not in params:
        print("\nNão encontrei o 'code' na URL. Verifique se colou a URL completa.")
        return

    code           = params["code"][0]
    returned_state = params.get("state", [""])[0]

    if returned_state != state:
        print("\nAVISO: state não confere. Pode ser um problema de segurança. Abortando.")
        return

    print("\nTrocando code pelo access_token...")
    data = exchange_code(code)

    if "access_token" not in data:
        print(f"\nERRO ao obter token: {data}")
        return

    access_token  = data["access_token"]
    refresh_token = data.get("refresh_token", "N/A")
    expires_in    = data.get("expires_in", "?")
    scope         = data.get("scope", "?")

    print("\n" + "="*60)
    print("SUCESSO! Coloque isso no seu .env:")
    print("="*60)
    print(f"TIKTOK_ACCESS_TOKEN={access_token}")
    print(f"TIKTOK_REFRESH_TOKEN={refresh_token}")
    print("="*60)
    print(f"\nExpira em: {expires_in} segundos (~{int(expires_in)//86400} dias)")
    print(f"Escopos:   {scope}")


if __name__ == "__main__":
    main()
