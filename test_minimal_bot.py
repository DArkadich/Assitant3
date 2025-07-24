import asyncio
import os
from aiogram import Bot, Dispatcher
from aiogram.types import Message
from aiogram.filters import Command

async def main():
    token = os.getenv("TELEGRAM_TOKEN")
    print("TELEGRAM_TOKEN:", token)
    bot = Bot(token=token)
    dp = Dispatcher()

    @dp.message(Command("start"))
    async def start_handler(message: Message):
        await message.answer("Минимальный бот работает!")

    print("Starting polling...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main()) 