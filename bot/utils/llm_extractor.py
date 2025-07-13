import requests
import json

OLLAMA_HOST = 'http://localhost:11434'  # Ollama в том же контейнере
OLLAMA_MODEL = 'mistral'

PROMPT_TEMPLATE = '''Вот текст документа:
{doc_text}

Извлеки, если есть: тип документа, номер, дату, сумму (в рублях), ИНН, контрагента. Ответь строго в формате JSON:
{{
  "doctype": "",
  "number": "",
  "date": "",
  "amount": "",
  "inn": "",
  "company": ""
}}
'''

def extract_receipts_llm(doc_text: str, timeout: int = 60) -> dict:
    prompt = PROMPT_TEMPLATE.format(doc_text=doc_text[:4000])  # Ограничим длину для скорости
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False
    }
    try:
        response = requests.post(f"{OLLAMA_HOST}/api/generate", json=payload, timeout=timeout)
        response.raise_for_status()
        data = response.json()
        # Ollama возвращает ответ в поле 'response'
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