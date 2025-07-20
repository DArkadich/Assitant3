FROM python:3.11-slim

WORKDIR /app
ENV PYTHONPATH=/app

# Установим системные зависимости для OCR и работы с docx/xlsx
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-rus \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    poppler-utils \
    libopencv-dev \
    python3-opencv \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY bot/ ./bot/
COPY extractor/ ./extractor/
COPY storage/ ./storage/
COPY analytics/ ./analytics/
COPY classifier/ ./classifier/
COPY legality_check/ ./legality_check/
COPY rag_engine/ ./rag_engine/
COPY closure_check/ ./closure_check/

CMD ["python", "bot/main.py"] 