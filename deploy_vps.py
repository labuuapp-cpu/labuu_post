import paramiko
import os
import tarfile
from dotenv import load_dotenv

load_dotenv()

# Configurações do VPS
HOST = os.getenv("VPS_HOST", "168.231.64.155")
USER = os.getenv("VPS_USER", "root")
PASSWORD = os.getenv("VPS_PASSWORD")

if not PASSWORD:
    print("ERRO: VPS_PASSWORD não definido no .env")
    exit(1)
REMOTE_PATH = "/opt/labuu"

def create_archive():
    print("Criando pacote para upload...")
    archive_name = "labuu_deploy.tar.gz"
    with tarfile.open(archive_name, "w:gz") as tar:
        for root, dirs, files in os.walk("."):
            # Ignorar pastas desnecessárias
            if any(x in root for x in [".git", "__pycache__", ".claude", "uploads", ".playwright-mcp"]):
                continue
            for file in files:
                if file.endswith(".tar.gz") or file == ".env":
                    continue
                file_path = os.path.join(root, file)
                tar.add(file_path)
    return archive_name

def deploy():
    archive = create_archive()
    
    print(f"Conectando ao VPS {HOST}...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASSWORD)
    
    print("Enviando arquivos...")
    sftp = ssh.open_sftp()
    sftp.put(archive, f"/tmp/{archive}")
    sftp.close()
    
    print("Extraindo e subindo container...")
    commands = [
        f"mkdir -p {REMOTE_PATH}",
        f"tar -xzf /tmp/{archive} -C {REMOTE_PATH}",
        f"cd {REMOTE_PATH} && docker compose up -d --build",
        f"rm /tmp/{archive}"
    ]
    
    for cmd in commands:
        print(f"Executando: {cmd}")
        stdin, stdout, stderr = ssh.exec_command(cmd)
        exit_status = stdout.channel.recv_exit_status()
        if exit_status != 0:
            print(f"ERRO: {stderr.read().decode()}")
        else:
            print(stdout.read().decode())
            
    ssh.close()
    os.remove(archive)
    print("Deploy finalizado com sucesso!")

if __name__ == "__main__":
    deploy()
