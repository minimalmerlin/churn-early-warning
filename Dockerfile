# Churn Early Warning Pipeline – Dockerfile
# Multi-Stage Build für minimales Produktions-Image

FROM python:3.12-slim AS base

# Security: Kein Root-User im Container
RUN useradd --create-home --shell /bin/bash appuser

WORKDIR /app

# Dependency-Installation als separater Layer (Cache-Effizienz)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip==25.0 \
    && pip install --no-cache-dir -r requirements.txt

# Quellcode kopieren
COPY . .

# Ownership auf Non-Root-User übertragen
RUN chown -R appuser:appuser /app
USER appuser

# Output-Verzeichnis anlegen
RUN mkdir -p output

# Umgebungsvariablen (Defaults, überschreibbar via docker run -e / Railway / Render)
ENV CHURN_LOG_LEVEL=INFO
ENV CHURN_TOP_N_ACCOUNTS=20
ENV CHURN_OUTPUT_DIR=output
# HOST=0.0.0.0 notwendig für Docker: Container muss auf allen Interfaces lauschen
ENV HOST=0.0.0.0
ENV PORT=8000

# Web-Server starten (nicht CLI). PORT wird von run_server.py via $PORT gelesen.
CMD ["python", "run_server.py"]
