# AXON AI Proxy — Cloud Run.
FROM python:3.11-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

RUN pip install --upgrade pip

COPY ai-proxy/pyproject.toml ./
RUN pip install --no-cache-dir "."

COPY ai-proxy/src ./src

ENV AI_PROXY_PORT=8080
EXPOSE 8080
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8080"]
