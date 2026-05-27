import paramiko, urllib.request, json, time, os
from dotenv import load_dotenv

load_dotenv()

host = os.getenv("VPS_HOST", "168.231.64.155")
user = os.getenv("VPS_USER", "root")
passwd = os.getenv("VPS_PASSWORD")

if not passwd:
    print("ERRO: VPS_PASSWORD não definido no .env")
    exit(1)

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(host, port=22, username=user, password=passwd, timeout=20)

def run(cmd, timeout=30):
    _, stdout, _ = client.exec_command(cmd, timeout=timeout)
    return stdout.read().decode(errors="replace").strip()

# Aguardar alguns segundos para o container inicializar
time.sleep(5)

print("=== Logs do container (últimas 40 linhas) ===")
print(run("docker logs labuu-marketing-bot --tail 40 2>&1"))

print("\n=== Teste de saúde via curl ===")
print(run("curl -s http://localhost:8000/api/health 2>/dev/null || echo 'falhou'"))

print("\n=== Container status ===")
print(run('docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"'))

# Configurar restart policy
print("\n=== Configurando restart always ===")
print(run("docker update --restart=always labuu-marketing-bot"))

client.close()
