FROM python:3.11-slim

WORKDIR /app

# System deps: gcc per compilar alguns paquets, tesseract per OCR fallback
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libmariadb-dev \
    tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# El codi es munta com a volum en dev; en prod: COPY . .
EXPOSE 8000
