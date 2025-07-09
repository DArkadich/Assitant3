import os
from peewee import SqliteDatabase
from dotenv import load_dotenv

load_dotenv()

def get_db():
    db_path = os.getenv("DATABASE_PATH", "database/db.sqlite3")
    return SqliteDatabase(db_path) 