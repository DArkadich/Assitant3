from .ollama_client import query_ollama, EXTRACTION_PROMPT_TEMPLATE
import json


def extract_fields_from_text(doc_text: str) -> dict:
    """
    Извлекает ключевые поля из текста документа с помощью Ollama LLM.
    Возвращает dict с полями: inn, counterparty, doc_number, date, amount, subject, contract_number.
    Если LLM не вернул корректный JSON, возвращает None.
    """
    prompt = EXTRACTION_PROMPT_TEMPLATE.format(text=doc_text)
    response = query_ollama(prompt)
    try:
        # Ищем JSON в ответе LLM
        start = response.find('{')
        end = response.rfind('}') + 1
        if start == -1 or end == -1:
            return None
        json_str = response[start:end]
        return json.loads(json_str)
    except Exception:
        return None

# Пример использования:
# fields = extract_fields_from_text("Текст документа ...")
# print(fields) 