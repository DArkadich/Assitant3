import os
from aiogram import Bot, Dispatcher, types
from aiogram.types import Message
from aiogram.filters import CommandStart
from aiogram import F
import asyncio
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

@dp.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer("Привет! Пришли мне документ (PDF, DOCX, XLSX)")

@dp.message(F.document)
async def handle_document(message: Message):
    await message.answer("Документ получен! (Обработка в разработке)")

if __name__ == "__main__":
    asyncio.run(dp.start_polling(bot)) 