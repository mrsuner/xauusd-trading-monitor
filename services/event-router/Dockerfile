FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy

COPY services/event-router/pyproject.toml ./pyproject.toml
COPY services/event-router/src ./src

RUN uv sync --no-dev

ENV PATH="/app/.venv/bin:$PATH"
CMD ["event-router", "run"]
