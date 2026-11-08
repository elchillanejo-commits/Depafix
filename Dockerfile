FROM python:3.12-slim

WORKDIR /app

# Instalar dependencias del sistema: WeasyPrint + Fuentes tipográficas
RUN apt-get update && apt-get install -y \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libjpeg-dev \
    libopenjp2-7-dev \
    libffi-dev \
    fonts-liberation \
    fontconfig \
    && rm -rf /var/lib/apt/lists/*

# Instalar librerías de Python
RUN pip install --no-cache-dir \
    fastapi \
    uvicorn \
    supabase \
    weasyprint \
    jinja2 \
    pandas \
    pydantic

COPY . /app

ENV PORT=8080
EXPOSE 8080

CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT}
