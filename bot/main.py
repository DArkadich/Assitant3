import asyncio
import os
from aiogram import Bot, Dispatcher
from aiogram.types import Message
from aiogram.filters import Command

from storage import storage
from analytics import Analytics
from validator import validator
from document_processor import processor
from rag import rag_index

async def main():
    bot = Bot(token=os.getenv("TELEGRAM_TOKEN"))
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

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main()) 