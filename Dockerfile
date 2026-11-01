# --- Stage 01 ---
FROM python:3.13-slim AS build
COPY --from=ghcr.io/astral-sh/uv:0.11.2 /uv /bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/srv/.venv

WORKDIR /srv
COPY pyproject.toml uv.lock ./

RUN uv sync --locked --no-dev

# --- Stage 02 ---
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/srv/.venv/bin:$PATH"

WORKDIR /srv
COPY --from=build /srv/.venv /srv/.venv
COPY app ./app
COPY data ./data

RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin appuser \
    && mkdir -p /srv/var && chown 10001:10001 /srv/var
USER 10001
VOLUME ["/srv/var"]

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
