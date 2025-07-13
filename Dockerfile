FROM python:3.11-slim

# Установка системных зависимостей
RUN apt-get update && \
    apt-get install -y tesseract-ocr tesseract-ocr-rus libpoppler-cpp-dev build-essential ca-certificates curl && \
    update-ca-certificates && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Установка Ollama
RUN curl -fsSL https://ollama.com/install.sh | sh

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Скачиваем модель Mistral при сборке
RUN ollama pull mistral

# Запускаем Ollama в фоне и затем бота
CMD ollama serve & sleep 5 && python -m bot.main 