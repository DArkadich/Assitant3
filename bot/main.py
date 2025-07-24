import asyncio
import os
from aiogram import Bot, Dispatcher, types
from aiogram.types import Message
from aiogram.filters import Command

from storage import storage
from analytics import Analytics
from validator import validator
from document_processor import processor
from rag import get_rag_index

TEMP_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "temp")
os.makedirs(TEMP_DIR, exist_ok=True)

async def notification_callback(user_id: int, message: str):
    try:
        # bot должен быть доступен через глобальную область
        await global_bot.send_message(user_id, message, parse_mode="HTML")
    except Exception as e:
        print(f"Ошибка отправки уведомления: {e}")

global_bot = None  # Глобальная переменная для доступа к боту из callback

async def main():
    global global_bot
    bot = Bot(token=os.getenv("TELEGRAM_TOKEN"))
    global_bot = bot
    dp = Dispatcher()

    @dp.message(Command("start", "help"))
    async def send_welcome(message: Message):
        await message.answer("Бот работает! Справка: /report, /unclosed, /monthly, /chain, /status, /validate, /tasks, /task, /find")

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

    # --- Этап: обработка документов и фото с постановкой в очередь ---
    @dp.message()
    async def handle_document(message: Message):
        if message.content_type == types.ContentType.DOCUMENT:
            document = message.document
            filename = document.file_name
            file_path = os.path.join(TEMP_DIR, filename)
            file = await bot.get_file(document.file_id)
            await bot.download(file, destination=file_path)
            task_id = await processor.add_task(message.from_user.id, filename, file_path)
            await message.answer(f"Документ '{filename}' получен и добавлен в очередь обработки (ID: {task_id[:8]})")
        elif message.content_type == types.ContentType.PHOTO:
            photo = message.photo[-1]
            file_id = photo.file_id
            filename = f"photo_{file_id}.jpg"
            file_path = os.path.join(TEMP_DIR, filename)
            file = await bot.get_file(photo.file_id)
            await bot.download(file, destination=file_path)
            task_id = await processor.add_task(message.from_user.id, filename, file_path)
            await message.answer(f"Фото получено и добавлено в очередь обработки (ID: {task_id[:8]})")

    # --- Запуск процессора документов ---
    processor.set_notification_callback(notification_callback)
    await processor.start()

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main()) 