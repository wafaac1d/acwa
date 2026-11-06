FROM node:22-alpine AS frontend
WORKDIR /src
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim-bookworm

COPY --from=ghcr.io/astral-sh/uv:0.13.1 /uv /uvx /bin/
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH" \
    ACWA_STATIC_DIR=/app/static

COPY backend/pyproject.toml backend/uv.lock backend/README.md ./
COPY backend/src ./src
COPY backend/alembic.ini ./
COPY backend/alembic ./alembic
COPY backend/docker-entrypoint.sh /entrypoint.sh
COPY docker/start.sh /start.sh
COPY --from=frontend /src/dist /app/static
RUN uv sync --frozen --no-dev && chmod +x /entrypoint.sh /start.sh

EXPOSE 8000
ENTRYPOINT ["/entrypoint.sh"]
CMD ["/start.sh"]
