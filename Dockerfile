FROM python:3.12-slim

WORKDIR /app

# Instalar herramientas de compilación y librerías del sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    libffi-dev \
    libssl-dev \
    libjpeg-dev \
    zlib1g-dev \
    libfreetype6-dev \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

# Copiar requirements e instalar forzando wheels precompilados
COPY requirements.txt .
RUN pip install --upgrade pip setuptools wheel && \
    pip install --no-cache-dir --prefer-binary -r requirements.txt

COPY . /app

ENV PYTHONPATH=/app
ENV PORT=8080
EXPOSE 8080

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
