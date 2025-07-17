import os
from aiogram import Bot, Dispatcher, types
from aiogram.types import Message
from aiogram.utils import executor
from aiogram.dispatcher.filters import ContentTypeFilter
from dotenv import load_dotenv

from extractor import extract_fields_from_text

# Реальные функции для извлечения текста
import pdfplumber
from docx import Document
from PIL import Image
import pytesseract


def extract_text_from_pdf(file_path):
    try:
        with pdfplumber.open(file_path) as pdf:
            return "\n".join(page.extract_text() or "" for page in pdf.pages)
    except Exception:
        return ""

def extract_text_from_docx(file_path):
    try:
        doc = Document(file_path)
        return "\n".join([p.text for p in doc.paragraphs])
    except Exception:
        return ""

def extract_text_from_jpg(file_path):
    try:
        return pytesseract.image_to_string(Image.open(file_path), lang='rus+eng')
    except Exception:
        return ""

# Загрузка токена из .env (создайте .env с TELEGRAM_TOKEN=...)
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

# Папка для временного хранения документов
TEMP_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "temp")
os.makedirs(TEMP_DIR, exist_ok=True)

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher(bot)

# Разрешённые расширения
ALLOWED_EXTENSIONS = {"pdf", "jpg", "jpeg", "docx", "xlsx", "zip"}


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def process_file(file_path):
    ext = file_path.rsplit(".", 1)[-1].lower()
    if ext == "pdf":
        text = extract_text_from_pdf(file_path)
    elif ext == "docx":
        text = extract_text_from_docx(file_path)
    elif ext in ("jpg", "jpeg"):
        text = extract_text_from_jpg(file_path)
    else:
        text = None
    return text

@dp.message_handler(content_types=types.ContentType.DOCUMENT)
async def handle_document(message: Message):
    document = message.document
    filename = document.file_name
    if not allowed_file(filename):
        await message.reply("❌ Недопустимый тип файла. Разрешены: PDF, JPG, DOCX, XLSX, ZIP.")
        return
    file_path = os.path.join(TEMP_DIR, filename)
    await document.download(destination_file=file_path)
    await message.reply(f"✅ Документ '{filename}' получен и сохранён. Извлекаю данные...")

    ext = filename.rsplit(".", 1)[-1].lower()
    if ext in ("pdf", "docx", "jpg", "jpeg"):
        text = process_file(file_path)
        if not text:
            await message.reply("❌ Не удалось извлечь текст из документа.")
            return
        fields = extract_fields_from_text(text)
        if fields:
            await message.reply(f"Извлечённые данные:\n<pre>{fields}</pre>", parse_mode="HTML")
        else:
            await message.reply("❌ Не удалось извлечь ключевые поля из документа.")
    else:
        await message.reply("Пока поддерживаются только PDF, DOCX, JPG. Поддержка XLSX и ZIP будет позже.")

@dp.message_handler(content_types=types.ContentType.PHOTO)
async def handle_photo(message: Message):
    # Сохраняем самое большое фото
    photo = message.photo[-1]
    file_id = photo.file_id
    filename = f"photo_{file_id}.jpg"
    file_path = os.path.join(TEMP_DIR, filename)
    await photo.download(destination_file=file_path)
    await message.reply(f"✅ Фото получено и сохранено как '{filename}'. Извлекаю данные...")
    text = extract_text_from_jpg(file_path)
    if not text:
        await message.reply("❌ Не удалось извлечь текст из фото.")
        return
    fields = extract_fields_from_text(text)
    if fields:
        await message.reply(f"Извлечённые данные:\n<pre>{fields}</pre>", parse_mode="HTML")
    else:
        await message.reply("❌ Не удалось извлечь ключевые поля из фото.")

@dp.message_handler(commands=["start", "help"])
async def send_welcome(message: Message):
    await message.reply("Привет! Отправьте мне документ (PDF, JPG, DOCX, XLSX, ZIP), и я его обработаю.")


def main():
    executor.start_polling(dp, skip_updates=True)

if __name__ == "__main__":
    main() 