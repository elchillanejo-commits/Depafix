FROM python:3.12-slim
WORKDIR /app
RUN apt-get update && apt-get install -y \
    libpango-1.0-0 libpangoft2-1.0-0 libcairo2 libgdk-pixbuf-2.0-0 \
    shared-mime-info libglib2.0-0 libxml2 libxslt1.1 libjpeg-dev \
    libopenjp2-7-dev libffi-dev fonts-liberation fontconfig \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . /app
ENV PYTHONPATH=/app
ENV PORT=8080
EXPOSE 8080
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
