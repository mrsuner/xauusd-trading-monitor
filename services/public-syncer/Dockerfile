FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY services/public-syncer/pyproject.toml ./pyproject.toml
COPY services/public-syncer/src ./src

RUN pip install --no-cache-dir .

CMD ["public-syncer", "run"]
