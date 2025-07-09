import re
from typing import Dict, List

# Ключевые слова для классификации документов
DOCUMENT_KEYWORDS = {
    'счёт': [
        'счёт', 'счет', 'invoice', 'bill', 'платёжное поручение',
        'платежное поручение', 'счёт-фактура', 'счет-фактура'
    ],
    'акт': [
        'акт', 'act', 'акт выполненных работ', 'акт оказанных услуг',
        'акт приёмки', 'акт приемки', 'отчёт', 'отчет'
    ],
    'договор': [
        'договор', 'contract', 'соглашение', 'agreement',
        'контракт', 'contract'
    ],
    'накладная': [
        'накладная', 'waybill', 'товарная накладная', 'ттн',
        'товарно-транспортная накладная'
    ],
    'квитанция': [
        'квитанция', 'receipt', 'чек', 'check', 'платёж',
        'платеж', 'оплата'
    ]
}

def classify_document(text: str) -> str:
    """Классифицирует документ по типу на основе ключевых слов"""
    if not text:
        return "неизвестно"
    
    text_lower = text.lower()
    
    # Подсчитываем совпадения для каждого типа документа
    scores = {}
    for doc_type, keywords in DOCUMENT_KEYWORDS.items():
        score = 0
        for keyword in keywords:
            if keyword in text_lower:
                score += 1
        if score > 0:
            scores[doc_type] = score
    
    # Возвращаем тип с наибольшим количеством совпадений
    if scores:
        best_type = max(scores, key=scores.get)
        return best_type
    
    return "прочее"

def extract_document_number(text: str) -> str:
    """Извлекает номер документа"""
    # Паттерны для поиска номеров документов
    patterns = [
        r'№\s*([A-Z0-9\-_]+)',  # № A7БП_022102
        r'номер[:\s]*([A-Z0-9\-_]+)',  # номер: A7БП_022102
        r'№\s*(\d+)',  # № 123
        r'номер[:\s]*(\d+)',  # номер: 123
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1)
    
    return ""

def extract_date(text: str) -> str:
    """Извлекает дату документа"""
    # Паттерны для поиска дат
    patterns = [
        r'(\d{1,2}[\.\/]\d{1,2}[\.\/]\d{4})',  # 23.06.2025
        r'(\d{4}[\.\/]\d{1,2}[\.\/]\d{1,2})',  # 2025.06.23
        r'(\d{1,2}\s+[а-яё]+\s+\d{4})',  # 23 июня 2025
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1)
    
    return "" 