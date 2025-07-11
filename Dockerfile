FROM python:3.11-slim

# Установка системных зависимостей
RUN apt-get update && \
    apt-get install -y tesseract-ocr tesseract-ocr-rus libpoppler-cpp-dev build-essential && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "-m", "bot.main"] 