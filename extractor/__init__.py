from .ollama_client import query_ollama, EXTRACTION_PROMPT_TEMPLATE
import json
import logging
import re

MAX_CHARS = 4000  # Максимальная длина текста для LLM (расширено для полноты)

# --- Классификация типа документа через LLM ---
CLASSIFY_PROMPT_TEMPLATE = (
    """
    Определи тип документа по тексту. Возможные типы: договор, акт, счёт, накладная, выписка банка, иной. Верни только тип одним словом (например: договор).
    Текст документа:
    """
    "{text}"
)

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
        with pdfplumber.open(file_path) as pdf:
            return "\n".join(page.extract_text() or "" for page in pdf.pages)
    except Exception:
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
        return pytesseract.image_to_string(Image.open(file_path), lang='rus+eng')
    except Exception:
        return ""

# --- Универсальная функция для bot/main.py ---
def process_file_with_classification(file_path):
    ext = file_path.rsplit(".", 1)[-1].lower()
    if ext == "pdf":
        full_text = extract_full_text_from_pdf(file_path)
        doc_type = classify_document_llm(full_text[:MAX_CHARS])
        logging.info(f"Document type (LLM): {doc_type}")
        if doc_type == "договор":
            return extract_text_from_pdf_contract(file_path)
        else:
            return full_text[:MAX_CHARS]
    elif ext == "docx":
        full_text = extract_full_text_from_docx(file_path)
        doc_type = classify_document_llm(full_text[:MAX_CHARS])
        logging.info(f"Document type (LLM): {doc_type}")
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


def extract_fields_from_text(doc_text: str) -> dict:
    """
    Извлекает ключевые поля из текста документа с помощью Ollama LLM.
    Возвращает dict с полями: inn, counterparty, doc_number, date, amount, subject, contract_number.
    Если LLM не вернул корректный JSON, возвращает None.
    """
    # Очищаем и ограничиваем длину текста
    safe_text = clean_text(doc_text)[:MAX_CHARS]
    prompt = EXTRACTION_PROMPT_TEMPLATE.format(text=safe_text)
    print(f"Prompt to LLM (len={len(safe_text)}): {prompt}")
    logging.info(f"Prompt to LLM (len={len(safe_text)}): {prompt}")
    try:
        response = query_ollama(prompt)
        try:
            # Ищем JSON в ответе LLM
            start = response.find('{')
            end = response.rfind('}') + 1
            if start == -1 or end == -1:
                logging.warning("LLM did not return JSON.")
                return None
            json_str = response[start:end]
            return json.loads(json_str)
        except Exception as e:
            logging.error(f"Error parsing LLM response as JSON: {e}")
            return None
    except Exception as e:
        logging.error(f"Error querying Ollama LLM: {e}")
        return None

# Пример использования:
# fields = extract_fields_from_text("Текст документа ...")
# print(fields) 