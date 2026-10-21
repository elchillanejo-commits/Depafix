FROM python:3.11-slim

WORKDIR /app

# Instalar dependencias
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el código y el Cerebro Local
COPY . .

# Verificación crítica: Asegurarnos de que el cerebro está dentro del contenedor
RUN ls -lh data/contexto_maestro.txt

# Configurar PYTHONPATH
ENV PYTHONPATH=/app

EXPOSE 8000
CMD uvicorn src.agencia.api:app --host 0.0.0.0 --port ${PORT:-8000}
