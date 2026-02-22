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

# Umgebungsvariablen (Defaults, überschreibbar via docker run -e)
ENV CHURN_LOG_LEVEL=INFO
ENV CHURN_DATA_SOURCE=data/sample/customer_events_sample.csv
ENV CHURN_TOP_N_ACCOUNTS=20
ENV CHURN_OUTPUT_DIR=output

CMD ["python", "main.py"]
