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
RUN pip install --upgrade pip
RUN pip install torch==2.2.2+cpu -f https://download.pytorch.org/whl/torch_stable.html
RUN pip install -r requirements.txt

COPY . .

CMD ["python", "bot/main.py"] 