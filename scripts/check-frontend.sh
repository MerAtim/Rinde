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

# Los e2e corren en un navegador de verdad y ven lo que jsdom no puede ver, que
# es el maquetado (ADR-0013). Necesitan el navegador bajado una vez por clon.
e2e() {
  if [[ "${RINDE_SKIP_E2E:-}" == "1" ]]; then
    echo "Aviso: se omiten los e2e por RINDE_SKIP_E2E. Los corre la CI." >&2
    return 0
  fi
  if ! npx playwright install --dry-run chromium >/dev/null 2>&1; then
    echo "Falta el navegador de Playwright. Bajalo una vez con: npx playwright install chromium" >&2
    echo "Para omitirlos a sabiendas: RINDE_SKIP_E2E=1" >&2
    return 1
  fi
  npm run e2e
}

all() {
  local chequeo
  for chequeo in format lint types tests build e2e; do
    echo "== frontend: ${chequeo}"
    "$chequeo"
  done
}

chequeo="${1:-all}"
case "$chequeo" in
  format | lint | types | tests | build | e2e | all) "$chequeo" ;;
  *)
    echo "Chequeo desconocido: ${chequeo}." >&2
    echo "Válidos: format, lint, types, tests, build, e2e, all" >&2
    exit 2
    ;;
esac
