from .ollama_client import query_ollama, EXTRACTION_PROMPT_TEMPLATE, CLASSIFY_PROMPT_TEMPLATE, ROLE_PROMPT_TEMPLATE, OUR_COMPANY
import json
import logging
import re
from io import BytesIO
from typing import Optional

MAX_CHARS = 2000  # Максимальная длина текста для LLM (уменьшено для ускорения)
OVERLAP = 500     # Перекрытие между окнами (уменьшено)

# --- Классификация типа документа через LLM ---
# CLASSIFY_PROMPT_TEMPLATE теперь импортируется из ollama_client.py

def classify_document_llm(text: str) -> str:
    prompt = CLASSIFY_PROMPT_TEMPLATE.format(text=text[:2000])
    logging.info(f"Prompt to LLM for classification: {prompt}")
    try:
        response = query_ollama(prompt)
        # Берём только первое слово из ответа
        doc_type = response.strip().split()[0].lower()
        return doc_type
    except Exception as e:
        logging.error(f"Error classifying document: {e}")
        return "иной"

# --- Извлечение текста для разных типов документов ---
def extract_full_text_from_pdf(file_path):
    try:
        import pdfplumber
        with pdfplumber.open(file_path) as pdf:
            text = "\n".join(page.extract_text() or "" for page in pdf.pages)
            logging.info(f"[PDF] Извлечённый текст (первые 200 символов): {text[:200]}")
            if text.strip():
                return text
            # Если текст пустой — пробуем OCR
            logging.info("[PDF] Текст не найден, пробую OCR для сканированного PDF...")
            from PIL import Image
            import pytesseract
            import cv2
            import numpy as np
            import traceback
            import subprocess
            import os
            ocr_text = ""
            for i, page in enumerate(pdf.pages):
                img = page.to_image(resolution=400).original
                buf = BytesIO()
                img.save(buf, format='PNG')
                buf.seek(0)
                pil_img = Image.open(buf)
                img_array = np.array(pil_img)
                if len(img_array.shape) == 3:
                    gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
                else:
                    gray = img_array
                clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
                gray = clahe.apply(gray)
                gray = cv2.medianBlur(gray, 3)
                enhanced_img = Image.fromarray(gray)
                # Сохраняем PNG для диагностики
                png_path = f"/tmp/ocr_page_{i+1}.png"
                enhanced_img.save(png_path)
                logging.info(f"[PDF][OCR] Saved {png_path} for manual OCR test")
                custom_config = r'--oem 3 --psm 6'
                logging.info(f"[PDF][OCR] config: {custom_config}")
                try:
                    # Сначала пробуем pytesseract
                    page_text = pytesseract.image_to_string(enhanced_img, lang='rus', config=custom_config)
                except Exception as ocr_e:
                    logging.error(f"[PDF][OCR] Ошибка pytesseract: {ocr_e}")
                    logging.error(traceback.format_exc())
                    # Пробуем через subprocess
                    try:
                        result = subprocess.run([
                            'tesseract', png_path, 'stdout', '-l', 'rus', '--oem', '3', '--psm', '6'
                        ], capture_output=True, text=True)
                        logging.error(f"[PDF][OCR][subprocess] stderr: {result.stderr}")
                        page_text = result.stdout
                    except Exception as sub_e:
                        logging.error(f"[PDF][OCR][subprocess] Ошибка: {sub_e}")
                        logging.error(traceback.format_exc())
                        page_text = ''
                ocr_text += page_text + "\n"
            logging.info(f"[PDF][OCR] Извлечённый текст (первые 200 символов): {ocr_text[:200]}")
            return ocr_text.strip()
    except Exception as e:
        import traceback
        logging.error(f"[PDF] Ошибка при извлечении текста: {e}")
        logging.error(traceback.format_exc())
        return ""

def extract_text_from_pdf_contract(file_path):
    try:
        with pdfplumber.open(file_path) as pdf:
            first_page_text = pdf.pages[0].extract_text() or ""
            requisites_text = ""
            for page in pdf.pages:
                text = page.extract_text() or ""
                if "реквизит" in text.lower():
                    requisites_text += text + "\n"
            return (first_page_text + "\n" + requisites_text).strip()
    except Exception:
        return ""

def extract_full_text_from_docx(file_path):
    try:
        from docx import Document
        doc = Document(file_path)
        return "\n".join([p.text for p in doc.paragraphs if p.text.strip()])
    except Exception:
        return ""

def extract_text_from_docx_contract(file_path):
    try:
        from docx import Document
        doc = Document(file_path)
        first_paragraphs = [p.text for p in doc.paragraphs[:20] if p.text.strip()]
        requisites = [p.text for p in doc.paragraphs if "реквизит" in p.text.lower()]
        return ("\n".join(first_paragraphs) + "\n" + "\n".join(requisites)).strip()
    except Exception:
        return ""

def extract_text_from_jpg(file_path):
    try:
        from PIL import Image
        import pytesseract
        import cv2
        import numpy as np
        import traceback
        pil_img = Image.open(file_path)
        img_array = np.array(pil_img)
        if len(img_array.shape) == 3:
            gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
        else:
            gray = img_array
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
        gray = clahe.apply(gray)
        gray = cv2.medianBlur(gray, 3)
        enhanced_img = Image.fromarray(gray)
        custom_config = r'--oem 3 --psm 6'
        logging.info(f"[JPG][OCR] config: {custom_config}")
        try:
            return pytesseract.image_to_string(enhanced_img, lang='rus', config=custom_config)
        except Exception as ocr_e:
            logging.error(f"[JPG][OCR] Ошибка pytesseract: {ocr_e}")
            logging.error(traceback.format_exc())
            return ""
    except Exception as e:
        import traceback
        logging.error(f"[JPG] Ошибка при извлечении текста: {e}")
        logging.error(traceback.format_exc())
        return ""

# --- Универсальная эвристика + LLM для классификации ---
def classify_document_universal(text: str) -> str:
    # Расширенная эвристика: ищем по всему тексту, а не только по первым строкам
    text_lower = text.lower()
    # Ключевые слова и регулярки для разных типов документов
    if "упд" in text_lower or "универсальный передаточный" in text_lower:
        return "упд"
    if "акт" in text_lower:
        return "акт"
    if "накладная" in text_lower:
        return "накладная"
    if "счёт-фактура" in text_lower or "счет-фактура" in text_lower:
        return "счёт-фактура"
    if "передаточный" in text_lower:
        return "передаточный"
    if "счет" in text_lower or "счёт" in text_lower:
        return "счёт"
    if "договор" in text_lower:
        return "договор"
    if "invoice" in text_lower:
        return "счёт"
    if "contract" in text_lower:
        return "договор"
    if re.search(r"\bакт[а-я]*\b", text_lower):
        return "акт"
    if re.search(r"\bдоговор[а-я]*\b", text_lower):
        return "договор"
    if re.search(r"\bнакладн[а-я]*\b", text_lower):
        return "накладная"
    if re.search(r"\bупд\b", text_lower):
        return "упд"
    # Если ничего не найдено — fallback на LLM
    return classify_document_llm(text)

# --- Универсальная функция для bot/main.py ---
def process_file_with_classification(file_path):
    ext = file_path.rsplit(".", 1)[-1].lower()
    if ext == "pdf":
        full_text = extract_full_text_from_pdf(file_path)
        doc_type = classify_document_universal(full_text[:MAX_CHARS])
        logging.info(f"Document type (universal): {doc_type}")
        if doc_type == "договор":
            return extract_text_from_pdf_contract(file_path)
        else:
            return full_text[:MAX_CHARS]
    elif ext == "docx":
        full_text = extract_full_text_from_docx(file_path)
        doc_type = classify_document_universal(full_text[:MAX_CHARS])
        logging.info(f"Document type (universal): {doc_type}")
        if doc_type == "договор":
            return extract_text_from_docx_contract(file_path)
        else:
            return full_text[:MAX_CHARS]
    elif ext in ("jpg", "jpeg"):
        return extract_text_from_jpg(file_path)
    else:
        return None


def clean_text(text: str) -> str:
    # Удаляем лишние пробелы, пустые строки, оставляем только буквы, цифры, знаки препинания
    text = re.sub(r'[^\w\d\s.,:;!?@#№\-_/\\()\[\]{}"\'\n]', '', text, flags=re.UNICODE)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return ' '.join(lines)


def merge_fields(base: dict, new: dict) -> dict:
    # Объединяет два результата, не перезаписывая найденные значения
    result = base.copy()
    for k, v in new.items():
        if (not result.get(k)) or result[k] == "-" or result[k].lower() in ("not specified", "none", "-"):
            if v and v != "-" and v.lower() not in ("not specified", "none", "-"):
                result[k] = v
    return result


def determine_company_role(text: str) -> str:
    """
    Определяет роль нашей компании в документе.
    Возвращает: 'поставщик', 'покупатель' или 'не указана'.
    """
    try:
        prompt = ROLE_PROMPT_TEMPLATE.format(text=text[:MAX_CHARS], our_company=OUR_COMPANY)
        logging.info(f"Prompt to LLM for role determination: {prompt[:200]}...")
        response = query_ollama(prompt)
        role = response.strip().split()[0].lower()
        logging.info(f"Company role determined: {role}")
        return role
    except Exception as e:
        logging.error(f"Error determining company role: {e}")
        return "не указана"

# --- Быстрый путь для извлечения ключевых полей ---
def extract_fields_from_text(doc_text: str, rag_context: Optional[list] = None) -> dict:
    """
    Сначала пытаемся извлечь ключевые поля регулярками/паттернами (быстрый путь).
    Если не удалось — используем LLM (медленный путь).
    """
    import re
    clean = clean_text(doc_text)
    total_len = len(clean)
    result = {k: "-" for k in ["inn", "counterparty", "doc_number", "date", "amount", "subject", "contract_number"]}

    # Быстрый путь: регулярки для ИНН, даты, суммы, номера документа
    # ИНН (10 или 12 цифр)
    inn_match = re.search(r"\b\d{10}\b|\b\d{12}\b", clean)
    if inn_match:
        result["inn"] = inn_match.group(0)
    # Дата (форматы: 23.06.2025, 23/06/2025, 23 июня 2025)
    date_match = re.search(r"\b\d{2}[./]\d{2}[./]\d{4}\b|\b\d{2} [а-я]+ \d{4}\b", clean)
    if date_match:
        result["date"] = date_match.group(0)
    # Сумма (форматы: 1 234 567,89 руб., 1234567.89)
    amount_match = re.search(r"\b\d{1,3}(?:[\s.,]\d{3})*(?:[.,]\d{2})?\b", clean)
    if amount_match:
        result["amount"] = amount_match.group(0)
    # Номер документа (№123, № 123, N123)
    docnum_match = re.search(r"№\s?\d+|N\s?\d+", clean)
    if docnum_match:
        result["doc_number"] = docnum_match.group(0)
    # --- Новый быстрый путь: поиск counterparty ---
    # Ищем строки с ключевыми словами и паттернами организаций
    counterparty_patterns = [
        r"(Общество с ограниченной ответственностью [\"'«][^\"'»]+[\"'»])",
        r"(Акционерное общество [\"'«][^\"'»]+[\"'»])",
        r"(Публичное акционерное общество [\"'«][^\"'»]+[\"'»])",
        r"(Индивидуальный предприниматель [А-ЯЁ][а-яё]+ [А-ЯЁ][а-яё]+)",
        r"(ООО\s+[\"'«][^\"'»]+[\"'»])",
        r"(АО\s+[\"'«][^\"'»]+[\"'»])",
        r"(ПАО\s+[\"'«][^\"'»]+[\"'»])",
        r"(ИП\s+[А-ЯЁ][а-яё]+\s[А-ЯЁ][а-яё]+)",
        r"(Заказчик:?\s*.+)",
        r"(Исполнитель:?\s*.+)",
        r"(Поставщик:?\s*.+)",
        r"(Получатель:?\s*.+)",
        r"(Продавец:?\s*.+)",
        r"(Покупатель:?\s*.+)",
        r"(Контрагент:?\s*.+)"
    ]
    for pat in counterparty_patterns:
        m = re.search(pat, clean)
        if m:
            val = m.group(1).strip()
            # Обрезаем лишнее после запятой/скобки/конца строки
            val = re.split(r'[\n\r,\(\)]', val)[0].strip()
            if 3 < len(val) < 100:
                result["counterparty"] = val
                break
    # --- Новый быстрый путь: поиск contract_number ---
    contract_patterns = [
        r"Договор\s*№\s*([A-Za-zА-Яа-я0-9\-_/]+)",
        r"Contract\s*No\.?\s*([A-Za-zА-Яа-я0-9\-_/]+)",
        r"Соглашение\s*№\s*([A-Za-zА-Яа-я0-9\-_/]+)",
        r"№\s*([A-Za-zА-Яа-я0-9\-_/]+)",
        r"N\s*([A-Za-zА-Яа-я0-9\-_/]+)"
    ]
    for pat in contract_patterns:
        m = re.search(pat, clean)
        if m:
            val = m.group(1).strip()
            if 2 < len(val) < 50:
                result["contract_number"] = val
                break
    # Если хотя бы 3 поля найдены — считаем быстрый путь успешным
    found_fields = sum(1 for v in [result["inn"], result["date"], result["amount"], result["doc_number"], result["counterparty"], result["contract_number"]] if v != "-")
    if found_fields >= 3:
        return result

    # --- Медленный путь: LLM ---
    # (остальной код как раньше)
    # Сначала определяем роль нашей компании
    our_role = determine_company_role(clean[:MAX_CHARS])
    # Формируем RAG-контекст
    rag_block = ""
    if rag_context:
        rag_block += "Вот примеры похожих документов:\n"
        for i, frag in enumerate(rag_context, 1):
            rag_block += f"Пример {i}:\n{frag}\n\n"
        rag_block += "----\n"
    windows = 0
    i = 0
    while i < total_len and windows < 10:
        window_text = clean[i:i+MAX_CHARS]
        prompt = rag_block + EXTRACTION_PROMPT_TEMPLATE.format(text=window_text, our_company=OUR_COMPANY, our_role=our_role)
        logging.info(f"Prompt to LLM (window {windows+1}, chars {i}-{i+MAX_CHARS}): {prompt[:200]}...")
        try:
            response = query_ollama(prompt)
            start = response.find('{')
            end = response.rfind('}') + 1
            if start == -1 or end == -1:
                logging.warning("LLM did not return JSON.")
                continue
            json_str = response[start:end]
            fields = json.loads(json_str)
            result = merge_fields(result, fields)
            if all(result[k] and result[k] != "-" and result[k].lower() not in ("not specified", "none", "-") for k in result):
                break
        except Exception as e:
            logging.error(f"Error querying Ollama LLM or parsing JSON: {e}")
            continue
        windows += 1
        i += OVERLAP
    logging.info(f"LLM windows used: {windows}, result: {result}")
    return result

# Пример использования:
# fields = extract_fields_from_text("Текст документа ...")
# print(fields) 