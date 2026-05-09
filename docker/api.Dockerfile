FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app/api

COPY api/ /app/api/

RUN pip install --no-cache-dir -U pip && \
    pip install --no-cache-dir -e .[dev]

CMD ["uvicorn", "llmh.main:app", "--host", "0.0.0.0", "--port", "8000"]

