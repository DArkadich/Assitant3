from .ollama_client import query_ollama, EXTRACTION_PROMPT_TEMPLATE
import json
import logging

MAX_CHARS = 4000  # Максимальная длина текста для LLM


def extract_fields_from_text(doc_text: str) -> dict:
    """
    Извлекает ключевые поля из текста документа с помощью Ollama LLM.
    Возвращает dict с полями: inn, counterparty, doc_number, date, amount, subject, contract_number.
    Если LLM не вернул корректный JSON, возвращает None.
    """
    # Ограничиваем длину текста
    safe_text = doc_text[:MAX_CHARS]
    prompt = EXTRACTION_PROMPT_TEMPLATE.format(text=safe_text)
    logging.info(f"Prompt to LLM (len={len(safe_text)}): {prompt[:200]}...")
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