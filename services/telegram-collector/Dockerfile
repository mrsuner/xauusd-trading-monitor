FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY services/telegram-collector/pyproject.toml ./pyproject.toml
COPY services/telegram-collector/src ./src

RUN pip install --no-cache-dir .

CMD ["telegram-collector", "run"]
