# syntax=docker/dockerfile:1

# Imágenes fijadas por digest: siempre se construye con exactamente los mismos bytes.
FROM ghcr.io/astral-sh/uv:0.12.13@sha256:b485bd65cc2cf1c9a93b3554012c9c3778cf7b1b5fd3d3096ce9e1226c97e1e6 AS uv

# Etapa 1: instala las dependencias en un entorno virtual.
FROM python:3.14-slim@sha256:cad9a2c871761c413caa6fdd6441c783451e740a48aaeba60ae62a8b53525ef6 AS builder
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never
COPY --from=uv /uv /bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-install-project
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-editable

# Etapa 2: imagen final, sin uv, sin pip y sin código fuente, con usuario sin privilegios.
# pip solo sirve para instalar (ya se hizo en la etapa 1) y trae dependencias propias con
# vulnerabilidades conocidas: quitarlo reduce la superficie de ataque.
FROM python:3.14-slim@sha256:cad9a2c871761c413caa6fdd6441c783451e740a48aaeba60ae62a8b53525ef6 AS runtime
RUN rm -rf /usr/local/lib/python3.14/site-packages/pip /usr/local/lib/python3.14/site-packages/pip-* /usr/local/bin/pip* \
    && groupadd --system --gid 10001 rinde \
    && useradd --system --uid 10001 --gid rinde --no-create-home --shell /usr/sbin/nologin rinde
WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
COPY alembic.ini ./
COPY migrations ./migrations
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
# Commit de origen: /api/health/live lo informa para verificar qué versión corre.
ARG RINDE_VERSION=dev
ENV RINDE_VERSION=$RINDE_VERSION
LABEL org.opencontainers.image.source="https://github.com/MerAtim/Rinde" \
      org.opencontainers.image.description="API de Rinde" \
      org.opencontainers.image.revision=$RINDE_VERSION
USER rinde
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import sys, urllib.request; sys.exit(urllib.request.urlopen('http://127.0.0.1:8000/api/health/live', timeout=2).status != 200)"]
CMD ["uvicorn", "--factory", "rinde.main:create_app", "--host", "0.0.0.0", "--port", "8000"]
