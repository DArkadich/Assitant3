import pytesseract
from PIL import Image
import fitz  # PyMuPDF
import os
from typing import Optional

def extract_text_from_pdf(pdf_path: str) -> str:
    """Извлекает текст из PDF файла"""
    try:
        doc = fitz.open(pdf_path)
        text = ""
        for page in doc:
            text += page.get_text()
        doc.close()
        return text.strip()
    except Exception as e:
        print(f"Ошибка при извлечении текста из PDF: {e}")
        return ""

def extract_text_from_image(image_path: str) -> str:
    """Извлекает текст из изображения с помощью OCR"""
    try:
        image = Image.open(image_path)
        text = pytesseract.image_to_string(image, lang='rus+eng')
        return text.strip()
    except Exception as e:
        print(f"Ошибка при OCR: {e}")
        return ""

def needs_ocr(text: str) -> bool:
    """Определяет, нужен ли OCR (если текст пустой или содержит мало символов)"""
    if not text or len(text.strip()) < 50:
        return True
    return False

def extract_text_with_ocr(file_path: str) -> str:
    """Извлекает текст из файла с OCR при необходимости"""
    file_ext = os.path.splitext(file_path)[1].lower()
    
    if file_ext == '.pdf':
        # Сначала пробуем извлечь текст напрямую
        text = extract_text_from_pdf(file_path)
        
        # Если текст пустой или мало символов - делаем OCR
        if needs_ocr(text):
            print("Текст не найден, применяем OCR...")
            # TODO: Добавить конвертацию PDF в изображения для OCR
            # Пока возвращаем исходный текст
            return text
        return text
    
    elif file_ext in ['.png', '.jpg', '.jpeg', '.tiff', '.bmp']:
        return extract_text_from_image(file_path)
    
    else:
        print(f"Неподдерживаемый формат файла: {file_ext}")
        return "" 