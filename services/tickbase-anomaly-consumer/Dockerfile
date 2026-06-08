FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY services/tickbase-anomaly-consumer/pyproject.toml ./pyproject.toml
COPY services/tickbase-anomaly-consumer/src ./src

RUN pip install --no-cache-dir .

CMD ["tickbase-anomaly-consumer", "run"]
