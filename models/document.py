from peewee import *
import os
from dotenv import load_dotenv

load_dotenv()

db_path = os.getenv("DATABASE_PATH", "database/db.sqlite3")
db = SqliteDatabase(db_path)

class Document(Model):
    filename = CharField()
    doctype = CharField()
    date = CharField(null=True)
    amount = FloatField(null=True)
    inn = CharField(null=True)
    company = CharField(null=True)
    path = CharField()
    created_at = DateTimeField()

    class Meta:
        database = db
        table_name = "documents" 