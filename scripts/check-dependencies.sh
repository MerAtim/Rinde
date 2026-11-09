#!/usr/bin/env bash
# Vulnerabilidades conocidas en dependencias e imágenes: una por nombre.
# Uso: scripts/check-dependencies.sh [backend|frontend|images]
#
# Lo ejecutan la CI en cada PR y la auditoría diaria sobre main, con los mismos
# comandos, para que no puedan separarse. No entra en el hook pre-push: su
# resultado cambia sin que cambie el código (ADR-0012, decisión 3).
set -euo pipefail

raiz="$(git rev-parse --show-toplevel)"

# Se audita el lockfile exportado con hashes y no el entorno instalado: es lo
# que se va a instalar de verdad, incluidos los grupos de desarrollo.
backend() {
  cd "$raiz/backend"
  local requisitos
  requisitos="$(mktemp)"
  trap 'rm -f "$requisitos"' RETURN
  uv export --locked --all-groups --no-emit-project --format requirements-txt > "$requisitos"
  uv run pip-audit --strict --disable-pip --require-hashes -r "$requisitos"
}

frontend() {
  cd "$raiz/frontend"
  npm audit --audit-level=moderate
}

# Las imágenes tienen que estar construidas antes (docker compose build).
# --ignore-unfixed: un aviso sin versión corregida no tiene acción posible y
# solo dejaría la CI en rojo sin salida.
images() {
  local imagen
  for imagen in rinde/api:local rinde/web:local; do
    trivy image --exit-code 1 --severity HIGH,CRITICAL --ignore-unfixed --no-progress "$imagen"
  done
}

chequeo="${1:-}"
case "$chequeo" in
  backend | frontend | images) "$chequeo" ;;
  *)
    echo "Chequeo desconocido: ${chequeo:-(ninguno)}." >&2
    echo "Válidos: backend, frontend, images" >&2
    exit 2
    ;;
esac
