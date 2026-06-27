FROM python:3.12-slim AS base

# Tesseract for OCR + build tooling for psycopg/pillow wheels.
RUN apt-get update && apt-get install -y --no-install-recommends \
        tesseract-ocr \
        libpq5 \
        curl \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN chmod +x start.sh

EXPOSE 8000

# start.sh runs migrations then launches uvicorn on $PORT (defaults to 8000).
# The worker service overrides this command in docker-compose.
CMD ["sh", "start.sh"]
