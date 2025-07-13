import os
from aiogram import Bot, Dispatcher, types
from aiogram.types import Message
from aiogram.filters import CommandStart
from aiogram import F
import asyncio
from dotenv import load_dotenv
from bot.handlers import save_document, process_document, save_to_database, format_response

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

@dp.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer("Привет! Пришли мне документ (PDF, DOCX, XLSX)")

@dp.message(F.document)
async def handle_document(message: Message):
    print("Document received:", message.document.file_name)
    try:
        # Сохраняем документ
        local_path = await save_document(message)
        print("Document saved to:", local_path)
        await message.answer("📄 Обрабатываю документ...")
        
        # Полная обработка документа
        print("Starting document processing...")
        result = await process_document(local_path)
        print("Document processing completed, result:", result)
        
        # Сохраняем в базу данных
        await save_to_database(result)
        
        # Формируем и отправляем ответ
        response = format_response(result)
        await message.answer(response)
        
    except Exception as e:
        print(f"Error in handle_document: {e}")
        await message.answer(f"❌ Ошибка при обработке документа: {str(e)}")

if __name__ == "__main__":
    asyncio.run(dp.start_polling(bot)) 