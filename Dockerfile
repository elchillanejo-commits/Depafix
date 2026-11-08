FROM python:3.12-slim

WORKDIR /app

# Instalar dependencias del sistema para FAISS
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 && rm -rf /var/lib/apt/lists/*

# Copiar e instalar dependencias de Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el resto del código
COPY . .

# Comando por defecto (el chat interactivo)
CMD ["python", "mente_360.py"]
