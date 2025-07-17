FROM python:3.11-slim

WORKDIR /app
ENV PYTHONPATH=/app

# Установим системные зависимости для OCR и работы с docx/xlsx
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY bot/ ./bot/
COPY extractor/ ./extractor/
COPY classifier/ ./classifier/
COPY legality_check/ ./legality_check/
COPY rag_engine/ ./rag_engine/
COPY analytics/ ./analytics/
COPY closure_check/ ./closure_check/

CMD ["python", "bot/main.py"] 