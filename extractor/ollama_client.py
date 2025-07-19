import os
import requests
import logging

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://ollama:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "mistral")
OUR_COMPANY = os.getenv("OUR_COMPANY", "ООО \"ТОРМЕДТЕХ\"")

logging.info(f"Используется модель Ollama: {OLLAMA_MODEL}")
logging.info(f"Наша компания: {OUR_COMPANY}")

def query_ollama(prompt: str) -> str:
    """
    Отправляет prompt в Ollama (endpoint /api/chat) и возвращает ответ LLM.
    """
    response = requests.post(
        f"{OLLAMA_HOST}/api/chat",
        json={
            "model": OLLAMA_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False
        },
        timeout=600  # 10 минут для обработки больших промптов
    )
    response.raise_for_status()
    return response.json()["message"]["content"]

# Пример prompt для извлечения ключевых полей из текста документа
EXTRACTION_PROMPT_TEMPLATE = (
    """
    Извлеки из следующего текста ключевые поля документа:
    - ИНН
    - Наименование контрагента (НЕ наша компания: {our_company})
    - Номер документа
    - Дата
    - Сумма
    - Предмет
    - Номер договора
    
    ВАЖНО: 
    - При поиске контрагента исключи нашу компанию "{our_company}"
    - Для счетов/актов ищи ПОКУПАТЕЛЯ/ЗАКАЗЧИКА (не поставщика)
    - Для договоров ищи вторую сторону сделки
    
    Верни результат в формате JSON с ключами: inn, counterparty, doc_number, date, amount, subject, contract_number.
    Текст документа:
    """
    "{text}"
) 