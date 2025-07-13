import requests
import json
import time

OLLAMA_HOST = 'http://localhost:11434'  # Ollama в том же контейнере
OLLAMA_MODEL = 'mistral'

PROMPT_TEMPLATE = '''Извлеки из текста документа следующие данные в формате JSON:
{{
  "doctype": "тип документа",
  "number": "номер документа", 
  "date": "дата документа",
  "amount": "сумма в рублях (только число)",
  "inn": "ИНН",
  "company": "название компании"
}}

Текст документа:
{doc_text}

Ответь только JSON без дополнительного текста.'''

def wait_for_ollama(timeout=120):
    """Ждем, пока Ollama будет готов"""
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            response = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=5)
            if response.status_code == 200:
                print("Ollama is ready")
                return True
        except:
            pass
        time.sleep(2)
    return False

def extract_receipts_llm(doc_text: str, timeout: int = 120) -> dict:
    # Ждем готовности Ollama
    if not wait_for_ollama():
        print("Ollama not ready, skipping LLM")
        return {}
    
    prompt = PROMPT_TEMPLATE.format(doc_text=doc_text[:3000])  # Уменьшил длину для скорости
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False
    }
    try:
        print("Sending request to LLM...")
        response = requests.post(f"{OLLAMA_HOST}/api/generate", json=payload, timeout=timeout)
        response.raise_for_status()
        data = response.json()
        llm_text = data.get('response', '').strip()
        print("LLM raw response:", llm_text)
        
        # Ищем JSON в ответе
        json_start = llm_text.find('{')
        json_end = llm_text.rfind('}') + 1
        if json_start != -1 and json_end != -1:
            json_str = llm_text[json_start:json_end]
            try:
                result = json.loads(json_str)
                return result
            except Exception as e:
                print(f"Ошибка парсинга JSON из LLM: {e}\nОтвет: {llm_text}")
        print(f"LLM ответ не содержит корректного JSON: {llm_text}")
    except Exception as e:
        print(f"Ошибка обращения к Ollama: {e}")
    return {} 