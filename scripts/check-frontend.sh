#!/usr/bin/env bash
# Chequeos de calidad del frontend: uno por nombre, o todos.
# Uso: scripts/check-frontend.sh [format|lint|types|tests|build|all]
#
# Igual que el del backend: lo ejecutan el hook pre-push y la CI con los mismos
# nombres, para que no puedan separarse.
set -euo pipefail

raiz="$(git rev-parse --show-toplevel)"
cd "$raiz/frontend"

format() { npm run format:check; }
lint() { npm run lint; }
types() { npm run typecheck; }
tests() { npm test; }
# El build entra porque compila distinto que `tsc -b` solo: rompe cosas que los
# tests no ven, como una importación que no existe en producción.
build() { npm run build; }

all() {
  local chequeo
  for chequeo in format lint types tests build; do
    echo "== frontend: ${chequeo}"
    "$chequeo"
  done
}

chequeo="${1:-all}"
case "$chequeo" in
  format | lint | types | tests | build | all) "$chequeo" ;;
  *)
    echo "Chequeo desconocido: ${chequeo}." >&2
    echo "Válidos: format, lint, types, tests, build, all" >&2
    exit 2
    ;;
esac
