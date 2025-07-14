import re
from typing import Dict, Optional

MY_COMPANIES = [
    'ООО "Тормедтех"',
    '7716958566',
]

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

def extract_payment_parties(text: str):
    lines = text.splitlines()
    payer, payer_inn, receiver, receiver_inn = '', '', '', ''
    my_inns = [c for c in MY_COMPANIES if c.isdigit()]
    found_payer = found_receiver = False
    for i, line in enumerate(lines):
        m = re.search(r'инн\s*(\d{10,12})', line, re.IGNORECASE)
        if m:
            inn = m.group(1)
            if not found_payer and inn in my_inns and i+1 < len(lines):
                payer_inn = inn
                payer = lines[i+1].strip()
                found_payer = True
            elif not found_receiver and inn not in my_inns and i+1 < len(lines):
                receiver_inn = inn
                receiver = lines[i+1].strip()
                found_receiver = True
        if found_payer and found_receiver:
            break
    return payer, payer_inn, receiver, receiver_inn

def extract_payment_counterparty(text: str) -> str:
    payer, payer_inn, receiver, receiver_inn = extract_payment_parties(text)
    # Если плательщик — своя компания, контрагент — получатель
    if any(my in payer or my in payer_inn for my in MY_COMPANIES):
        return receiver or receiver_inn
    # Если получатель — своя компания, контрагент — плательщик
    if any(my in receiver or my in receiver_inn for my in MY_COMPANIES):
        return payer or payer_inn
    return ''

def extract_payment_amount(text: str) -> Optional[float]:
    # Ищем сумму в формате 11000-00 или 11000–00
    match = re.search(r'Сумма\s*([0-9]+[-–][0-9]+)', text)
    if match:
        amount_str = match.group(1).replace('-', '.').replace('–', '.')
        try:
            return float(amount_str)
        except ValueError:
            pass
    return None

def extract_payment_direction(text: str) -> str:
    payer, payer_inn, receiver, receiver_inn = extract_payment_parties(text)
    if any(my in payer or my in payer_inn for my in MY_COMPANIES):
        return "Исходящие"
    if any(my in receiver or my in receiver_inn for my in MY_COMPANIES):
        return "Входящие"
    return ""

def extract_party_direction_and_counterparty(text: str):
    lines = text.splitlines()
    my_inns = [c for c in MY_COMPANIES if c.isdigit()]
    my_names = [c.lower() for c in MY_COMPANIES if not c.isdigit()]
    parties = {}
    for i, line in enumerate(lines):
        for role in ['исполнитель', 'заказчик', 'поставщик', 'покупатель']:
            if role in line.lower() and i+1 < len(lines):
                parties[role] = lines[i+1].strip()
    # ИНН ищем рядом
    for i, line in enumerate(lines):
        m = re.search(r'инн\s*(\d{10,12})', line, re.IGNORECASE)
        if m:
            inn = m.group(1)
            for role in parties:
                if parties[role] in line:
                    parties[role+'_inn'] = inn
    # Определяем направление и контрагента
    for role, opp_role in [('исполнитель', 'заказчик'), ('поставщик', 'покупатель')]:
        if role in parties and (parties.get(role+'_inn') in my_inns or any(name in parties[role].lower() for name in my_names)):
            return "Исходящие", parties.get(opp_role, "")
        if opp_role in parties and (parties.get(opp_role+'_inn') in my_inns or any(name in parties[opp_role].lower() for name in my_names)):
            return "Входящие", parties.get(role, "")
    return "", ""

def extract_invoice_number_and_date(text: str):
    m = re.search(r'Счет[^\d]*(\d+)[^\d]+от\s*([0-9]{1,2}\s*[а-яА-Я]+\.?\s*\d{4})', text, re.IGNORECASE)
    if m:
        return m.group(1), m.group(2)
    return "", ""

def extract_invoice_parties(text: str):
    my_inns = [c for c in MY_COMPANIES if c.isdigit()]
    my_names = [c.lower() for c in MY_COMPANIES if not c.isdigit()]
    m1 = re.search(r'Продавец:\s*([^\n,]+)', text)
    m2 = re.search(r'Покупатель:\s*([^\n,]+)', text)
    seller = m1.group(1).strip() if m1 else ""
    buyer = m2.group(1).strip() if m2 else ""
    # Определяем направление
    if any(my in seller or my in seller.lower() for my in my_names) or any(my in seller for my in my_inns):
        return "Исходящие", buyer
    if any(my in buyer or my in buyer.lower() for my in my_names) or any(my in buyer for my in my_inns):
        return "Входящие", seller
    return "", ""

def extract_all_receipts(text: str, doc_type: str = None) -> Dict[str, any]:
    if doc_type is None:
        from .classifier import classify_document
        doc_type = classify_document(text)
    # Для актов, договоров — универсальная логика
    if doc_type in ['акт', 'договор']:
        direction, counterparty = extract_party_direction_and_counterparty(text)
        return {
            'amount': extract_amount(text),
            'inn': extract_inn(text),
            'company': counterparty,
            'date': extract_date(text),
            'document_number': extract_document_number(text),
            'direction': direction,
        }
    # Для счетов — спец. логика
    if doc_type in ['счёт', 'счет']:
        number, date = extract_invoice_number_and_date(text)
        direction, counterparty = extract_invoice_parties(text)
        return {
            'amount': extract_amount(text),
            'inn': extract_inn(text),
            'company': counterparty,
            'date': date,
            'document_number': number,
            'direction': direction,
        }
    # Если это платёжное поручение
    if doc_type == 'платёжное поручение':
        direction = extract_payment_direction(text)
        return {
            'amount': extract_payment_amount(text),
            'inn': extract_inn(text),
            'company': extract_payment_counterparty(text),
            'date': extract_date(text),
            'document_number': extract_document_number(text),
            'direction': direction,
        }
    # иначе — стандартные
    return {
        'amount': extract_amount(text),
        'inn': extract_inn(text),
        'company': extract_company_name(text),
        'date': extract_date(text),
        'document_number': extract_document_number(text),
    }

# Импортируем функции из classifier.py
from .classifier import extract_date, extract_document_number 