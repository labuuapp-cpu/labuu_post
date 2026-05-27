import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

engine = create_engine(os.getenv('DATABASE_URL'))
with engine.connect() as conn:
    res = conn.execute(text('SELECT id, file_path, caption, file_type FROM scheduled_posts ORDER BY id DESC LIMIT 1'))
    row = res.fetchone()
    if row:
        print(f"ID: {row[0]}")
        print(f"Path: {row[1]}")
        print(f"Caption: {row[2]}")
        print(f"Type: {row[3]}")
    else:
        print("Nenhum post encontrado")
