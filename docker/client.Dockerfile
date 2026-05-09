FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app/client

COPY client/ /app/client/

RUN pip install --no-cache-dir -U pip && \
    pip install --no-cache-dir -e .[dev]

CMD ["python", "-m", "llmh_client"]
