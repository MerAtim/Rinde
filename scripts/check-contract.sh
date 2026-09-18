#!/usr/bin/env bash
# Verifica que el contrato versionado coincida con el código.
# Uso: scripts/check-contract.sh
#
# Regenera el OpenAPI del backend y los tipos del frontend, y falla si alguno
# cambia: el contrato no puede quedar atrás del código, porque el frontend se
# compila contra esos tipos.
#
# Ojo: deja los archivos ya regenerados en el directorio de trabajo. Si falla,
# lo único que hay que hacer es revisar el diff y commitearlo.
set -euo pipefail

raiz="$(git rev-parse --show-toplevel)"
export PYTHONIOENCODING=utf-8

(cd "$raiz/backend" && uv run python -m rinde.openapi openapi.json)
(cd "$raiz/frontend" && npm run generate:api)

generados=(backend/openapi.json frontend/src/shared/api/schema.d.ts)
if ! git -C "$raiz" diff --exit-code -- "${generados[@]}"; then
  {
    echo "El contrato o los tipos generados no coinciden con el código."
    echo "  * Ya quedaron regenerados: revisá el diff de arriba y commiteá el resultado."
  } >&2
  exit 1
fi
