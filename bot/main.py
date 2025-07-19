import logging
logging.basicConfig(level=logging.INFO)

import os
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.types import Message
from aiogram.utils import executor
from aiogram.dispatcher.filters import ContentTypeFilter
from dotenv import load_dotenv

from extractor import extract_fields_from_text, process_file_with_classification, classify_document_universal

# Очередь задач
task_queue = asyncio.Queue()

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

# Воркер для обработки очереди документов
async def document_worker():
    while True:
        user_id, filename, file_path, ext = await task_queue.get()
        try:
            # Сначала извлекаем текст
            text = process_file_with_classification(file_path)
            print(f"Text to LLM: {text[:200]}")
            logging.info(f"Text to LLM: {text[:200]}")
            if not text:
                await bot.send_message(user_id, f"❌ Не удалось извлечь текст из документа {filename}.")
            else:
                # Определяем тип документа
                doc_type = classify_document_universal(text)
                logging.info(f"Document type determined: {doc_type}")
                
                # Извлекаем поля
                fields = extract_fields_from_text(text)
                if fields:
                    # Добавляем тип документа в результат и переупорядочиваем поля
                    fields['doc_type'] = doc_type
                    # Создаём новый словарь с нужным порядком полей
                    ordered_fields = {
                        'doc_type': fields['doc_type'],
                        'counterparty': fields['counterparty'],
                        'inn': fields['inn'],
                        'doc_number': fields['doc_number'],
                        'date': fields['date'],
                        'amount': fields['amount'],
                        'subject': fields['subject'],
                        'contract_number': fields['contract_number']
                    }
                    await bot.send_message(user_id, f"Извлечённые данные для '{filename}':\n<pre>{ordered_fields}</pre>", parse_mode="HTML")
                else:
                    await bot.send_message(user_id, f"❌ Не удалось извлечь ключевые поля из документа {filename}.")
        except Exception as e:
            await bot.send_message(user_id, f"❌ Ошибка при обработке документа {filename}: {e}")
        finally:
            task_queue.task_done()

@dp.message_handler(content_types=types.ContentType.DOCUMENT)
async def handle_document(message: Message):
    document = message.document
    filename = document.file_name
    if not allowed_file(filename):
        await message.reply("❌ Недопустимый тип файла. Разрешены: PDF, JPG, DOCX, XLSX, ZIP.")
        return
    file_path = os.path.join(TEMP_DIR, filename)
    await document.download(destination_file=file_path)
    ext = filename.rsplit(".", 1)[-1].lower()
    await message.reply(f"✅ Документ '{filename}' получен и поставлен в очередь на обработку.")
    await task_queue.put((message.from_user.id, filename, file_path, ext))

@dp.message_handler(content_types=types.ContentType.PHOTO)
async def handle_photo(message: Message):
    # Сохраняем самое большое фото
    photo = message.photo[-1]
    file_id = photo.file_id
    filename = f"photo_{file_id}.jpg"
    file_path = os.path.join(TEMP_DIR, filename)
    await photo.download(destination_file=file_path)
    await message.reply(f"✅ Фото получено и поставлено в очередь на обработку.")
    await task_queue.put((message.from_user.id, filename, file_path, "jpg"))

@dp.message_handler(commands=["start", "help"])
async def send_welcome(message: Message):
    await message.reply("Привет! Отправьте мне документ (PDF, JPG, DOCX, XLSX, ZIP), и я его обработаю.\nДокументы обрабатываются по очереди, вы получите результат после завершения обработки каждого файла.")

def main():
    loop = asyncio.get_event_loop()
    loop.create_task(document_worker())
    executor.start_polling(dp, skip_updates=True, loop=loop)

if __name__ == "__main__":
    main() 