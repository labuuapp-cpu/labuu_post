import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

engine = create_engine(os.getenv('DATABASE_URL'))
with engine.connect() as conn:
    res = conn.execute(text('SELECT id, status, post_ids FROM scheduled_posts WHERE id=7'))
    row = res.fetchone()
    if row:
        print(f"ID: {row[0]}")
        print(f"Status: {row[1]}")
        print(f"Post IDs: {row[2]}")
    else:
        print("Post 7 não encontrado")
