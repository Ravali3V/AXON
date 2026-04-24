# AXON audit worker — Playwright + Python + Node sidecar for Puppeteer PDF.
# Based on Microsoft's Playwright image which includes browsers + system deps.
FROM mcr.microsoft.com/playwright/python:v1.46.0-jammy

WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

# Node for the Puppeteer PDF sidecar (T-11)
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates gnupg \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

COPY worker/pyproject.toml ./
RUN pip install --no-cache-dir "." \
    && python -m playwright install chromium --with-deps

COPY worker/src ./src

# Puppeteer PDF sidecar
COPY worker/pdf_sidecar ./pdf_sidecar
RUN cd pdf_sidecar && npm install --omit=dev

ENV WORKER_PORT=8080
EXPOSE 8080
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8080"]
