import os
from aiogram import types
from aiogram.types import Message
from datetime import datetime
from dotenv import load_dotenv
from typing import Dict

# Импортируем наши модули
from bot.utils.ocr import extract_text_with_ocr
from bot.utils.classifier import classify_document, extract_document_number, extract_date
from bot.utils.extractor import extract_all_receipts
from bot.utils.storage import get_target_folder, generate_filename, move_document_to_folder
from bot.utils.db import get_db
from models.document import Document

load_dotenv()

DOCUMENTS_PATH = os.getenv("DOCUMENTS_PATH", "data/Документы")
INBOX_PATH = os.path.join(DOCUMENTS_PATH, "Входящие")
os.makedirs(INBOX_PATH, exist_ok=True)

async def save_document(message: Message) -> str:
    """Сохраняет документ во входящую папку"""
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

async def process_document(file_path: str) -> Dict:
    """Полная обработка документа с использованием только regex-извлечения"""
    print("process_document: Starting with file:", file_path)
    
    # 1. Извлекаем текст (с OCR при необходимости)
    print("process_document: Extracting text...")
    text = extract_text_with_ocr(file_path)
    print("process_document: Text extracted, length:", len(text))
    print("=== EXTRACTED TEXT ===\n", text, "\n=== END TEXT ===")
    with open("/app/last_extracted_text.txt", "w", encoding="utf-8") as f:
        f.write(text)
    
    # 2. Классифицируем документ
    print("process_document: Classifying document...")
    doc_type = classify_document(text)
    print("process_document: Document type:", doc_type)
    
    # 3. Извлекаем реквизиты через regex
    print("process_document: Extracting with regex...")
    receipts = extract_all_receipts(text)
    print("process_document: Regex result:", receipts)
    
    # 4. Определяем целевую папку
    print("process_document: Determining target folder...")
    year = datetime.now().strftime("%Y")
    target_folder = get_target_folder(
        doc_type=doc_type,
        company=receipts.get('company', ''),
        base_path=DOCUMENTS_PATH,
        year=year,
        direction=receipts.get('direction', None)
    )
    print("process_document: Target folder:", target_folder)
    
    # 5. Генерируем новое имя файла
    print("process_document: Generating filename...")
    new_filename = generate_filename(
        original_name=os.path.basename(file_path),
        doc_type=doc_type,
        doc_number=receipts.get('document_number', ''),
        amount=receipts.get('amount'),
        date=receipts.get('date', '')
    )
    print("process_document: New filename:", new_filename)
    
    # 6. Перемещаем файл в целевую папку
    print("process_document: Moving file...")
    final_path = move_document_to_folder(file_path, target_folder, new_filename)
    print("process_document: Final path:", final_path)
    
    result = {
        'doc_type': doc_type,
        'receipts': receipts,
        'target_folder': target_folder,
        'final_path': final_path,
        'text': text
    }
    print("process_document: Final result:", result)
    return result

async def save_to_database(result: Dict) -> bool:
    """Сохраняет метаданные документа в базу данных"""
    try:
        db = get_db()
        db.connect()
        
        # Создаём таблицу, если её нет
        Document.create_table()
        
        # Создаём запись
        doc = Document.create(
            filename=os.path.basename(result['final_path']),
            doctype=result['doc_type'],
            date=result['receipts'].get('date', ''),
            amount=result['receipts'].get('amount'),
            inn=result['receipts'].get('inn', ''),
            company=result['receipts'].get('company', ''),
            path=result['final_path'],
            created_at=datetime.now()
        )
        
        db.close()
        return True
    except Exception as e:
        print(f"Ошибка при сохранении в БД: {e}")
        return False

def format_response(result: Dict) -> str:
    """Формирует ответ пользователю"""
    doc_type = result['doc_type']
    receipts = result['receipts']
    
    response_parts = []
    
    # Тип документа
    if doc_type and doc_type != "неизвестно":
        response_parts.append(f"✅ Документ сохранён как: {doc_type.capitalize()}")
    else:
        response_parts.append("✅ Документ сохранён")
    
    # Номер документа
    if receipts.get('document_number'):
        response_parts.append(f"Номер: {receipts['document_number']}")
    
    # Дата
    if receipts.get('date'):
        response_parts.append(f"Дата: {receipts['date']}")
    
    # Контрагент
    if receipts.get('company'):
        response_parts.append(f"Контрагент: {receipts['company']}")
    
    # Сумма
    if receipts.get('amount'):
        response_parts.append(f"Сумма: {int(receipts['amount']):,} ₽")
    
    # Путь сохранения
    relative_path = os.path.relpath(result['target_folder'], DOCUMENTS_PATH)
    response_parts.append(f"Сохранено в: {relative_path}/")
    
    return "\n".join(response_parts) 