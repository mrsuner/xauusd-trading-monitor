FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY services/public-api/pyproject.toml ./pyproject.toml
COPY services/public-api/alembic.ini ./alembic.ini
COPY services/public-api/migrations ./migrations
COPY services/public-api/src ./src

RUN pip install --no-cache-dir .

CMD ["public-api", "run"]
