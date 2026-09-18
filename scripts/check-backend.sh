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
tests() { uv run pytest --cov --cov-report=term-missing; }

# `alembic check` compara el modelo con una base real: sin base no hay nada que
# comparar. Se deniega por defecto y se permite por excepción explícita, en vez
# de devolver un verde que no significa nada.
migrations() {
  if [[ -z "${RINDE_DATABASE_URL:-}" ]]; then
    if [[ "${RINDE_SKIP_DB_CHECKS:-}" == "1" ]]; then
      echo "Aviso: sin base de datos se omite el chequeo de migraciones. Lo verifica la CI." >&2
      return 0
    fi
    {
      echo "Falta RINDE_DATABASE_URL: sin base no se puede comparar la migracion con el modelo."
      echo "  * Levantá la base de tests:"
      echo "      docker compose --profile test up --detach --wait test-db"
      echo "  * Y exportá (con 127.0.0.1, no localhost):"
      echo "      export RINDE_DATABASE_URL=postgresql+psycopg://rinde:solo_para_tests@127.0.0.1:55432/rinde_test"
      echo "    En Windows, localhost resuelve primero a IPv6 y el puerto se publica solo"
      echo "    en IPv4: con localhost la conexion no falla, se cuelga."
      echo "  * Para omitirlo a sabiendas: RINDE_SKIP_DB_CHECKS=1"
    } >&2
    return 1
  fi
  uv run alembic upgrade head
  uv run alembic check
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
