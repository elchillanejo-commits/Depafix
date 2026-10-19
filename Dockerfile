FROM python:3.11-slim

WORKDIR /app

# Instalar dependencias primero (para caché de Docker)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el código fuente
COPY . .

# Configurar PYTHONPATH
ENV PYTHONPATH=/app

# Railway inyecta la variable $PORT dinámicamente
EXPOSE 8000
CMD uvicorn src.agencia.api:app --host 0.0.0.0 --port ${PORT:-8000}
