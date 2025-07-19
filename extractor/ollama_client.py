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

# Prompt для определения роли компании в документе
ROLE_PROMPT_TEMPLATE = (
    """
    Определи роль компании "{our_company}" в данном документе.
    Возможные роли: поставщик, покупатель, не указана.
    Верни только роль одним словом (например: поставщик).
    Текст документа:
    """
    "{text}"
)

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
    - Роль нашей компании в документе: {our_role}
    - Если наша компания поставщик → ищи ПОКУПАТЕЛЯ
    - Если наша компания покупатель → ищи ПОСТАВЩИКА
    - Если роль неясна → ищи любую другую организацию, кроме нашей
    
    Верни результат в формате JSON с ключами: inn, counterparty, doc_number, date, amount, subject, contract_number.
    Текст документа:
    """
    "{text}"
)

# Prompt для классификации типа документа
CLASSIFY_PROMPT_TEMPLATE = (
    """
    Определи тип документа по тексту. Возможные типы: договор, акт, счёт, счёт-фактура, накладная, упд, выписка банка, иной. 
    УПД (Универсальный передаточный документ) - это отдельный тип документа, который может заменять счёт-фактуру, накладную и акт.
    Верни только тип одним словом (например: договор, упд, счёт, счёт-фактура).
    Текст документа:
    """
    "{text}"
) 