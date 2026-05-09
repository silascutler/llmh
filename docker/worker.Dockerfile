FROM python:3.12-slim

WORKDIR /app

COPY api/ /app/api/
COPY worker/ /app/worker/

RUN pip install --no-cache-dir -U pip && \
    pip install --no-cache-dir -e /app/api -e /app/worker[dev]

CMD ["python", "-m", "llmh_worker"]
