import logging
import os
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.types import Message
from dotenv import load_dotenv
from aiogram.filters import Command

from storage import storage
from analytics import Analytics
from validator import validator
from document_processor import processor
from rag import rag_index

load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

analytics = Analytics()
TEMP_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "temp")
os.makedirs(TEMP_DIR, exist_ok=True)

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

ALLOWED_EXTENSIONS = {"pdf", "jpg", "jpeg", "docx", "xlsx", "zip"}

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

async def notification_callback(user_id: int, message: str):
    try:
        await bot.send_message(user_id, message, parse_mode="Markdown")
    except Exception as e:
        logging.error(f"Ошибка отправки уведомления пользователю {user_id}: {e}")

@dp.message()
async def handle_document(message: Message):
    if message.content_type != types.ContentType.DOCUMENT:
        return
    document = message.document
    filename = document.file_name
    if not allowed_file(filename):
        await message.reply("❌ Недопустимый тип файла. Разрешены: PDF, JPG, DOCX, XLSX, ZIP.")
        return
    file_path = os.path.join(TEMP_DIR, filename)
    await document.download(destination_file=file_path)
    task_id = await processor.add_task(message.from_user.id, filename, file_path)
    await message.reply(f"✅ Документ '{filename}' получен и добавлен в очередь обработки (ID: {task_id[:8]})")

@dp.message()
async def handle_photo(message: Message):
    if message.content_type != types.ContentType.PHOTO:
        return
    photo = message.photo[-1]
    file_id = photo.file_id
    filename = f"photo_{file_id}.jpg"
    file_path = os.path.join(TEMP_DIR, filename)
    await photo.download(destination_file=file_path)
    task_id = await processor.add_task(message.from_user.id, filename, file_path)
    await message.reply(f"✅ Фото получено и добавлено в очередь обработки (ID: {task_id[:8]})")

@dp.message(Command("start", "help"))
async def send_welcome(message: Message):
    help_text = """
🤖 Документ-бот — автоматическая обработка документов

**Основные команды:**
/start, /help — справка
/report — отчёт по контрагентам
/unclosed — незакрытые цепочки
/monthly — месячный отчёт
/chain <номер> — детали цепочки
/status — статус системы
/validate <json> — проверить валидацию
/tasks — мои задачи
/task <id> — статус задачи
/find <текст> — семантический поиск

Просто отправьте документ или фото для обработки!
    """
    await message.answer(help_text, parse_mode="Markdown")

@dp.message(Command("report"))
async def handle_report(message: Message):
    await message.answer("Здесь будет отчёт по контрагентам.")

@dp.message(Command("unclosed"))
async def handle_unclosed(message: Message):
    await message.answer("Здесь будет отчёт по незакрытым цепочкам.")

@dp.message(Command("monthly"))
async def handle_monthly(message: Message):
    await message.answer("Здесь будет месячный отчёт.")

@dp.message(Command("chain"))
async def handle_chain(message: Message):
    await message.answer("Здесь будут детали цепочки.")

@dp.message(Command("status"))
async def handle_status(message: Message):
    await message.answer("Здесь будет статус системы.")

@dp.message(Command("validate"))
async def handle_validate(message: Message):
    await message.answer("Здесь будет валидация данных.")

@dp.message(Command("tasks"))
async def handle_tasks(message: Message):
    await message.answer("Здесь будет список ваших задач.")

@dp.message(Command("task"))
async def handle_task_status(message: Message):
    await message.answer("Здесь будет статус задачи.")

@dp.message(Command("find"))
async def handle_find(message: Message):
    await message.answer("Здесь будет семантический поиск.")

async def setup_processor():
    """Настройка и запуск процессора документов"""
    # Устанавливаем callback для уведомлений
    processor.set_notification_callback(notification_callback)
    
    # Запускаем процессор
    await processor.start()
    
    logging.info("DocumentProcessor настроен и запущен")

async def main():
    await setup_processor()
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main()) 