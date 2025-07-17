from .ollama_client import query_ollama, EXTRACTION_PROMPT_TEMPLATE
import json
import logging
import re

MAX_CHARS = 4000  # Максимальная длина текста для LLM (расширено для полноты)


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