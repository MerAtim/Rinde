# syntax=docker/dockerfile:1

# Imágenes fijadas por digest: la base es siempre la misma.
# La etapa final aplica encima los parches de seguridad de Debian, así que el
# resultado no es byte a byte reproducible. Es a propósito: la imagen oficial de
# Python se reconstruye más lento de lo que Debian publica parches, y preferimos
# una imagen parcheada antes que una reproducible con CVE conocidos.
FROM ghcr.io/astral-sh/uv:0.12.15@sha256:62f8c047d0a0e9ece6b53fc63df902585a67a47a7f318ddec4a37db586edc8e3 AS uv

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
RUN apt-get update \
    && apt-get upgrade --yes --no-install-recommends \
    && rm -rf /var/lib/apt/lists/* \
    && rm -rf /usr/local/lib/python3.14/site-packages/pip /usr/local/lib/python3.14/site-packages/pip-* /usr/local/bin/pip* \
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
