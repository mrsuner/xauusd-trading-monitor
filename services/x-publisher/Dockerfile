FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY services/x-publisher/pyproject.toml ./pyproject.toml
COPY services/x-publisher/src ./src

RUN pip install --no-cache-dir .

CMD ["x-publisher", "run"]
