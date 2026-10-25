FROM python:3.11-slim

WORKDIR /app

# Instalar dependencias
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Modelo ONNX del RAG (multilingual-e5-small): revisión fijada + sha256 verificado.
# Capa propia para que no se vuelva a bajar en cada cambio de código.
COPY scripts/descargar_modelo_onnx.py scripts/
RUN python scripts/descargar_modelo_onnx.py /app/models/multilingual-e5-small
ENV IKKI_EMBED_MODEL_DIR=/app/models/multilingual-e5-small

# Copiar el código y el Cerebro Local
COPY . .

# Verificación crítica: Asegurarnos de que el cerebro está dentro del contenedor
RUN ls -lh data/contexto_maestro.txt

# Configurar PYTHONPATH
ENV PYTHONPATH=/app

EXPOSE 8000
CMD uvicorn src.agencia.api:app --host 0.0.0.0 --port ${PORT:-8000}
