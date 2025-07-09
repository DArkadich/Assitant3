import os
from aiogram import types
from aiogram.types import Message
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

DOCUMENTS_PATH = os.getenv("DOCUMENTS_PATH", "data/Документы")
INBOX_PATH = os.path.join(DOCUMENTS_PATH, "Входящие")
os.makedirs(INBOX_PATH, exist_ok=True)

async def save_document(message: Message) -> str:
    document = message.document
    file_info = await message.bot.get_file(document.file_id)
    file_ext = os.path.splitext(document.file_name)[1]
    now = datetime.now().strftime("%Y%m%d_%H%M%S")
    local_filename = f"{now}_{document.file_name}"
    local_path = os.path.join(INBOX_PATH, local_filename)
    file = await message.bot.download_file(file_info.file_path)
    with open(local_path, "wb") as f:
        f.write(file.read())
    return local_path 