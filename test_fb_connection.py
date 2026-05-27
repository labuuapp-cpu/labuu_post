import os
import requests
from dotenv import load_dotenv

load_dotenv()

token = os.getenv("META_ACCESS_TOKEN")
page_id = os.getenv("FACEBOOK_PAGE_ID")

print(f"Testando conexão com a página: {page_id}")

# 1. Testar se o token consegue ver a página
res = requests.get(f"https://graph.facebook.com/v19.0/{page_id}?fields=name,access_token&access_token={token}")
data = res.json()

if "error" in data:
    print(f"ERRO DE CONEXÃO: {data['error'].get('message')}")
    print(f"Detalhes: {data}")
else:
    print(f"SUCESSO: Conectado à página '{data.get('name')}'")
    if "access_token" not in data:
        print("AVISO: O token fornecido parece ser um User Token, não um Page Token. Isso pode causar erro ao postar como a página.")
