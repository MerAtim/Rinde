#!/usr/bin/env bash
# Chequeos de calidad del backend: uno por nombre, o todos.
# Uso: scripts/check-backend.sh [format|lint|types|layers|migrations|tests|all]
#
# Lo ejecutan el hook pre-push (local) y el pipeline de CI, con los mismos
# nombres. Es a propósito: un chequeo que se agrega acá entra en los dos lados a
# la vez y no pueden separarse. La CI sigue siendo la autoridad; esto evita que
# lo local diga que está verde cuando la CI va a decir que no.
set -euo pipefail

raiz="$(git rev-parse --show-toplevel)"
cd "$raiz/backend"

# En Windows la consola no toma UTF-8 por defecto y la salida lleva tildes.
export PYTHONIOENCODING=utf-8

# Formato y estilo son distintos: `ruff format` acomoda, `ruff check` busca
# problemas. Pasar uno no implica pasar el otro.
format() { uv run ruff format --check .; }
lint() { uv run ruff check .; }
types() { uv run mypy; }
layers() { uv run lint-imports; }

# Varios chequeos necesitan un PostgreSQL de verdad. Se deniega por defecto y se
# permite por excepción explícita, en vez de devolver un verde que no significa
# nada. Devuelve 0 si hay base, 1 si se permitió seguir sin ella, y corta si no.
_needs_database() {
  if [[ -n "${RINDE_DATABASE_URL:-}" ]]; then
    return 0
  fi
  if [[ "${RINDE_SKIP_DB_CHECKS:-}" == "1" ]]; then
    return 1
  fi
  {
    echo "Falta RINDE_DATABASE_URL: este chequeo necesita una base de datos real."
    echo "  * Levantá la base de tests:"
    echo "      docker compose --profile test up --detach --wait test-db"
    echo "  * Y exportá (con 127.0.0.1, no localhost):"
    echo "      export RINDE_DATABASE_URL=postgresql+psycopg://rinde:solo_para_tests@127.0.0.1:55432/rinde_test"
    echo "    En Windows, localhost resuelve primero a IPv6 y el puerto se publica solo"
    echo "    en IPv4: con localhost la conexion no falla, se cuelga."
    echo "  * Para omitirlo a sabiendas: RINDE_SKIP_DB_CHECKS=1"
  } >&2
  exit 1
}

# `alembic check` compara el modelo con una base real: sin base no hay nada que
# comparar.
migrations() {
  if ! _needs_database; then
    echo "Aviso: sin base de datos se omite el chequeo de migraciones. Lo verifica la CI." >&2
    return 0
  fi
  uv run alembic upgrade head
  uv run alembic check
}

# Los tests de integración son los que cubren los repositorios. Sin base no
# corren, y entonces la cobertura medida no dice nada sobre el código que quedó
# sin ejercitar: baja alrededor de siete puntos y no llega al mínimo.
#
# Por eso, sin base, no se compara contra el mínimo. No es una excepción para
# que pase igual: es no afirmar un número que no se midió. La CI siempre tiene
# base y siempre lo compara (ADR-0012, decisión 4).
tests() {
  if ! _needs_database; then
    {
      echo "Aviso: sin base de datos no corren los tests de integración."
      echo "  * La cobertura no se compara contra el mínimo, porque faltan los tests"
      echo "    que cubren los repositorios y el número no sería comparable."
      echo "  * La CI la mide con base y con el mínimo puesto."
    } >&2
    uv run pytest -m "not integration" --cov --cov-report=term-missing --cov-fail-under=0
    return
  fi
  uv run pytest --cov --cov-report=term-missing
}

all() {
  local chequeo
  for chequeo in format lint types layers migrations tests; do
    echo "== backend: ${chequeo}"
    "$chequeo"
  done
}

chequeo="${1:-all}"
case "$chequeo" in
  format | lint | types | layers | migrations | tests | all) "$chequeo" ;;
  *)
    echo "Chequeo desconocido: ${chequeo}." >&2
    echo "Válidos: format, lint, types, layers, migrations, tests, all" >&2
    exit 2
    ;;
esac
