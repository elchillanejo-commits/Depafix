FROM python:3.12-slim
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential gcc libffi-dev libssl-dev libjpeg-dev zlib1g-dev libfreetype6-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip setuptools wheel
RUN pip install --no-cache-dir --prefer-binary -r requirements.txt

# Copiar TODO el proyecto, pero asegurando que src y app estén
COPY . /app

# Verificar que las carpetas críticas existan (esto lo verás en el log de build)
RUN ls -la /app && ls -la /app/src && ls -la /app/app

ENV PYTHONPATH=/app
ENV PORT=8080
EXPOSE 8080

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
