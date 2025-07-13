import re
from typing import Dict, Optional

def extract_amount(text: str) -> Optional[float]:
    """Извлекает сумму из текста документа"""
    # Паттерны для поиска сумм (приоритет: сумма услуги, затем итого)
    patterns = [
        r'Сумма услуги \(руб\.\)\s*\n\s*([\d\s.,]+)',  # Сумма услуги (руб.) 1 570 134,00
        r'сумма услуги[:\s]*([\d\s.,]+)[\s]*руб',  # сумма услуги: 1 570 134,00 руб
        r'сумма[:\s]*([\d\s.,]+)[\s]*руб',  # сумма: 55 000 руб
        r'итого[:\s]*([\d\s.,]+)[\s]*руб',   # итого: 55 000 руб
        r'к оплате[:\s]*([\d\s.,]+)[\s]*руб', # к оплате: 55 000 руб
        r'([\d\s.,]+)[\s]*рублей',            # 55 000 рублей
        r'([\d\s.,]+)[\s]*₽',                 # 55 000 ₽
        r'([\d\s.,]+)[\s]*руб',               # 55 000 руб
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match and match.groups():
            amount_str = match.group(1).replace(' ', '').replace(',', '.').replace(' ', '')
            try:
                return float(amount_str)
            except ValueError:
                continue
    
    return None

def extract_inn(text: str) -> str:
    """Извлекает ИНН из текста"""
    # Паттерны для ИНН (10 или 12 цифр)
    patterns = [
        r'ИНН[:\s]*(\d{10,12})',  # ИНН: 1234567890
        r'инн[:\s]*(\d{10,12})',  # инн: 1234567890
        r'(\d{10,12})',            # просто 10-12 цифр подряд
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match and match.groups():
            inn = match.group(1)
            # Проверяем, что это действительно ИНН (10 или 12 цифр)
            if len(inn) in [10, 12]:
                return inn
    
    return ""

def extract_company_name(text: str) -> str:
    """Извлекает название компании/контрагента"""
    # Паттерны для поиска названий компаний (приоритет: ООО в начале документа)
    patterns = [
        r'Общество с ограниченной ответственностью "([^"]+)"',  # ООО "А7-АГЕНТ"
        r'ООО\s+[""]([^""]+)[""]',  # ООО "Название"
        r'поставщик[:\s]*([А-ЯЁ][А-ЯЁ\s\d\-\"\"\']+)',  # поставщик: ООО "Рога и Копыта"
        r'продавец[:\s]*([А-ЯЁ][А-ЯЁ\s\d\-\"\"\']+)',   # продавец: ООО "Рога и Копыта"
        r'заказчик[:\s]*([А-ЯЁ][А-ЯЁ\s\d\-\"\"\']+)',   # заказчик: ООО "Рога и Копыта"
        r'исполнитель[:\s]*([А-ЯЁ][А-ЯЁ\s\d\-\"\"\']+)', # исполнитель: ООО "Рога и Копыта"
        r'ИП\s+[А-ЯЁ\s]+',        # ИП Иванов Иван Иванович
        r'АО\s+[""][^""]+[""]',   # АО "Название"
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match and match.groups():
            company = match.group(1).strip()
            # Очищаем от лишних символов
            company = re.sub(r'\s+', ' ', company)
            return company
    
    return ""

def extract_all_receipts(text: str) -> Dict[str, any]:
    """Извлекает все реквизиты из текста документа"""
    return {
        'amount': extract_amount(text),
        'inn': extract_inn(text),
        'company': extract_company_name(text),
        'date': extract_date(text),  # импортируем из classifier.py
        'document_number': extract_document_number(text),  # импортируем из classifier.py
    }

# Импортируем функции из classifier.py
from .classifier import extract_date, extract_document_number 