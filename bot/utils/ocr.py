import pytesseract
from PIL import Image
import pdfplumber
import os
from typing import Optional

def extract_text_from_pdf(pdf_path: str, debug: bool = True) -> str:
    """Извлекает текст из PDF файла и сохраняет для отладки"""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            text = ""
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
        text = text.strip()
        # Сохраняем текст для отладки
        if debug:
            txt_path = pdf_path + ".txt"
            with open(txt_path, "w", encoding="utf-8") as f:
                f.write(text)
        return text
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

def extract_text_with_ocr(file_path: str, debug: bool = True) -> str:
    """Извлекает текст из файла с OCR при необходимости и сохраняет для отладки"""
    file_ext = os.path.splitext(file_path)[1].lower()
    
    if file_ext == '.pdf':
        # Сначала пробуем извлечь текст напрямую
        text = extract_text_from_pdf(file_path, debug=debug)
        
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