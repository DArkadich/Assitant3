import os
import requests
import logging
import hashlib
import pickle
import time
import psycopg2

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://ollama:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "mistral")
OUR_COMPANY = os.getenv("OUR_COMPANY", "ООО \"ТОРМЕДТЕХ\"")
LLM_CACHE_PATH = os.getenv("LLM_CACHE_PATH", "data/llm_cache.pkl")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://doc_user:doc_password@localhost:5432/doc_checker")

logging.info(f"Используется модель Ollama: {OLLAMA_MODEL}")
logging.info(f"Наша компания: {OUR_COMPANY}")

_llm_cache = None

def _load_llm_cache():
    global _llm_cache
    if _llm_cache is not None:
        return _llm_cache
    try:
        if os.path.exists(LLM_CACHE_PATH):
            with open(LLM_CACHE_PATH, "rb") as f:
                _llm_cache = pickle.load(f)
        else:
            _llm_cache = {}
    except Exception:
        _llm_cache = {}
    return _llm_cache

def _save_llm_cache():
    try:
        os.makedirs(os.path.dirname(LLM_CACHE_PATH), exist_ok=True)
        with open(LLM_CACHE_PATH, "wb") as f:
            pickle.dump(_llm_cache, f)
    except Exception:
        # Кэш не критичен; игнорируем ошибки записи
        pass

def _pg_fetch_cache(cache_key: str, prompt_hash: str):
    try:
        conn = psycopg2.connect(DATABASE_URL)
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT response FROM llm_cache WHERE key=%s OR prompt_hash=%s LIMIT 1", (cache_key, prompt_hash))
                row = cur.fetchone()
                if row:
                    return row[0]
        finally:
            conn.close()
    except Exception:
        return None
    return None

def _pg_store_cache(cache_key: str, prompt_hash: str, model: str, response_text: str):
    try:
        conn = psycopg2.connect(DATABASE_URL)
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO llm_cache(key, model, prompt_hash, response) VALUES(%s, %s, %s, %s) ON CONFLICT (key) DO NOTHING",
                    (cache_key, model, prompt_hash, response_text)
                )
                conn.commit()
        finally:
            conn.close()
    except Exception:
        pass

def query_ollama(prompt: str) -> str:
    """
    Отправляет prompt в Ollama (endpoint /api/generate) и возвращает ответ LLM.
    Добавляет простое кэширование и ретраи с экспоненциальной паузой.
    """
    cache = _load_llm_cache()
    cache_key = hashlib.sha256(f"{OLLAMA_MODEL}\n{prompt}".encode("utf-8")).hexdigest()
    prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    # Postgres cache first
    pg_cached = _pg_fetch_cache(cache_key, prompt_hash)
    if pg_cached:
        return pg_cached
    # File cache fallback
    if cache_key in cache:
        return cache[cache_key]

    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {
            # Детерминированные ответы и ограничение длины
            "temperature": 0,
            "num_predict": 512
        }
    }

    last_err = None
    for attempt in range(3):
        try:
            response = requests.post(
                f"{OLLAMA_HOST}/api/generate",
                json=payload,
                timeout=120
            )
            response.raise_for_status()
            result = response.json().get("response", "")
            cache[cache_key] = result
            _save_llm_cache()
            _pg_store_cache(cache_key, prompt_hash, OLLAMA_MODEL, result)
            return result
        except Exception as e:
            last_err = e
            # backoff: 0.5s, 1s, 2s
            time.sleep(0.5 * (2 ** attempt))
    # Если все попытки провалились — поднимаем исключение
    raise last_err

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