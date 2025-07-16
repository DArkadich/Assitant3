import os
import requests

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://ollama:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "mistral")


def query_ollama(prompt: str) -> str:
    """
    Отправляет prompt в Ollama и возвращает ответ LLM.
    """
    response = requests.post(
        f"{OLLAMA_HOST}/api/generate",
        json={
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False
        },
        timeout=120
    )
    response.raise_for_status()
    return response.json()["response"]


# Пример prompt для извлечения ключевых полей из текста документа
EXTRACTION_PROMPT_TEMPLATE = (
    """
    Извлеки из следующего текста ключевые поля документа:
    - ИНН
    - Наименование контрагента
    - Номер документа
    - Дата
    - Сумма
    - Предмет
    - Номер договора
    Верни результат в формате JSON с ключами: inn, counterparty, doc_number, date, amount, subject, contract_number.
    Текст документа:
    """
    "{text}"
) 