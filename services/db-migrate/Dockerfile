FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN pip install --no-cache-dir "alembic>=1.13.3,<2.0" "psycopg[binary]>=3.2.3,<4.0"

COPY db ./db

WORKDIR /app/db

CMD ["alembic", "upgrade", "head"]
