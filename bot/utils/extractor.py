import re
from typing import Dict, Optional

def extract_invoice_number(text: str) -> str:
    match = re.search(r'Счет на оплату №\s*([A-Za-zА-Яа-я0-9]+)', text, re.IGNORECASE)
    if match:
        return match.group(1)
    return ""

def extract_invoice_date(text: str) -> str:
    match = re.search(r'Счет на оплату №\s*[A-Za-zА-Яа-я0-9]+\s*от\s*([0-9]{2}\s[а-яА-Я]+\s[0-9]{4})', text, re.IGNORECASE)
    if match:
        return match.group(1)
    match = re.search(r'от\s*([0-9]{2}\s[а-яА-Я]+\s[0-9]{4})', text, re.IGNORECASE)
    if match:
        return match.group(1)
    return ""

def extract_invoice_supplier(text: str) -> str:
    match = re.search(r'Поставщик[:\s]+([^\n,]+)', text, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return ""

def extract_amount(text: str) -> Optional[float]:
    """Извлекает сумму из текста документа"""
    # Паттерны для поиска сумм (приоритет: сумма услуги, затем итого)
    patterns = [
        r'Сумма услуги \(руб\.\)[^\d\n]*\n\s*([\d\s.,]+)',
        r'Итого:[^\d\n]*\n\s*([\d\s.,]+)',
        r'Сумма услуги \(руб\.\)\s*\n\s*([\d\s.,]+)\s*\n\s*[\d\s.,]+\s*USD',
        r'Сумма услуги \(руб\.\)\s*\n\s*([\d\s.,]+)',
        r'сумма услуги[:\s]*([\d\s.,]+)[\s]*руб',
        r'итого[:\s]*([\d\s.,]+)[\s]*руб',
        r'к оплате[:\s]*([\d\s.,]+)[\s]*руб',
        r'сумма[:\s]*([\d\s.,]+)[\s]*руб',
        r'([\d\s.,]+)[\s]*рублей',
        r'([\d\s.,]+)[\s]*₽',
        r'([\d\s.,]+)[\s]*руб',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match and match.groups():
            amount_str = match.group(1).replace(' ', '').replace(',', '.').replace(' ', '')
            try:
                amount = float(amount_str)
                if amount > 100:
                    return amount
            except ValueError:
                continue
    # Если не нашли — ищем строку 'Итого:' и берём следующую строку
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if 'Итого:' in line and i+1 < len(lines):
            next_line = lines[i+1].strip()
            amount_str = next_line.replace(' ', '').replace(',', '.').replace(' ', '')
            try:
                amount = float(amount_str)
                if amount > 100:
                    return amount
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
        r'ООО\s+"([^"]+)"',  # ООО "Название" (с обычными кавычками)
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
    # Если это счёт, используем спец. функции
    if re.search(r'счет на оплату', text, re.IGNORECASE):
        return {
            'amount': extract_amount(text),
            'inn': extract_inn(text),
            'company': extract_invoice_supplier(text),
            'date': extract_invoice_date(text),
            'document_number': extract_invoice_number(text),
        }
    # иначе — стандартные
    return {
        'amount': extract_amount(text),
        'inn': extract_inn(text),
        'company': extract_company_name(text),
        'date': extract_date(text),  # импортируем из classifier.py
        'document_number': extract_document_number(text),  # импортируем из classifier.py
    }

# Импортируем функции из classifier.py
from .classifier import extract_date, extract_document_number 