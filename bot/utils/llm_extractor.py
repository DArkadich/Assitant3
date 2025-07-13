import requests
import json
import time

OLLAMA_HOST = 'http://localhost:11434'  # Ollama в том же контейнере
OLLAMA_MODEL = 'mistral'

PROMPT_TEMPLATE = '''JSON: {{
  "doctype": "акт",
  "number": "БП-22102", 
  "date": "23.06.2025",
  "amount": "1570134",
  "inn": "",
  "company": "ООО А7-АГЕНТ"
}}

Текст: {doc_text}

Извлеки данные в JSON формате.'''

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

def extract_receipts_llm(doc_text: str, timeout: int = 300) -> dict:
    # Ждем готовности Ollama
    if not wait_for_ollama():
        print("Ollama not ready, skipping LLM")
        return {}
    
    prompt = PROMPT_TEMPLATE.format(doc_text=doc_text[:2000])  # Еще меньше текста
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.1,  # Низкая температура для более предсказуемых ответов
            "top_p": 0.9
        }
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