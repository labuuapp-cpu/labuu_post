# Deploy no VPS Hostinger

## 1. Copiar o projeto para o VPS
```bash
scp -r labuu_project/ user@seu-vps:/home/user/labuu
```

## 2. No VPS, configurar o .env
```bash
cd /home/user/labuu
cp .env.example .env
nano .env   # preencha todas as chaves, incluindo PUBLIC_BASE_URL
```

### Importante: PUBLIC_BASE_URL
Para o Instagram funcionar, ele precisa baixar o vídeo de uma URL pública.
Se estiver no VPS: `PUBLIC_BASE_URL=http://seu-ip-ou-dominio:8000`
Se estiver local: use [Ngrok](https://ngrok.com/) e coloque a URL gerada por ele.

## 3. Validar Configuração
Antes de rodar tudo, execute o script de diagnóstico:
```bash
python diagnose_setup.py
```
Se tudo estiver com "✅", você está pronto para subir.

## 4. Subir com Docker
```bash
docker-compose up -d --build
```

## 4. Verificar se está rodando
```bash
docker logs labuu-marketing-bot
```
Acesse: http://seu-ip:8000

## 5. (Opcional) Configurar domínio com Nginx
Aponte o domínio para o VPS e configure proxy para porta 8000.

---

## Chaves necessárias

### Claude API
1. Acesse: console.anthropic.com
2. Crie uma API Key
3. Coloque em ANTHROPIC_API_KEY

### Meta (Facebook + Instagram)
1. Acesse: developers.facebook.com
2. Crie um App > Business
3. Adicione o produto "Instagram Graph API"
4. Gere um Access Token de longa duração
5. Anote: APP_ID, APP_SECRET, ACCESS_TOKEN, INSTAGRAM_ACCOUNT_ID, FACEBOOK_PAGE_ID

### TikTok
1. Acesse: developers.tiktok.com
2. Crie um App
3. Adicione "Content Posting API"
4. Aguarde aprovação (pode levar alguns dias)
5. Anote: CLIENT_KEY, CLIENT_SECRET, ACCESS_TOKEN
