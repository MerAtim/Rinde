#!/usr/bin/env bash
# Verifica el contenido de la cabecera Content-Security-Policy de una URL.
# Uso: scripts/check-csp.sh <url> [reintentos]
# Lo ejecutan la CI (entorno local) y el CD (URL pública).
#
# Antes solo se comprobaba que la cabecera existiera. Una CSP vacía o con
# 'unsafe-inline' habría pasado igual, que es justamente el caso que interesa
# detectar: la defensa contra XSS depende de que script-src siga siendo estricto.
set -euo pipefail
export LC_ALL=C

url="${1:?Falta la URL}"
reintentos="${2:-0}"

cabeceras="$(curl -fsSI --retry "$reintentos" --retry-delay 10 --retry-all-errors "$url")"
csp="$(printf '%s' "$cabeceras" | tr -d '\r' | grep -i '^content-security-policy:' || true)"

if [[ -z "$csp" ]]; then
  echo "::error::La respuesta de ${url} no trae cabecera Content-Security-Policy" >&2
  exit 1
fi

echo "$csp"

errores=()

# Directivas que tienen que estar tal cual. Si alguna se afloja, falla acá.
requeridas=(
  "default-src 'self'"
  "script-src 'self'"
  "style-src 'self'"
  "object-src 'none'"
  "frame-ancestors 'none'"
  "base-uri 'self'"
  "form-action 'self'"
)
for directiva in "${requeridas[@]}"; do
  if ! printf '%s' "$csp" | grep -qF "$directiva"; then
    errores+=("Falta la directiva: ${directiva}")
  fi
done

# Palabras clave que vacían la protección contra XSS.
for prohibida in "unsafe-inline" "unsafe-eval" "unsafe-hashes"; do
  if printf '%s' "$csp" | grep -qF "$prohibida"; then
    errores+=("La CSP permite '${prohibida}', que anula la defensa contra XSS")
  fi
done

if (( ${#errores[@]} > 0 )); then
  {
    echo "::error::CSP rechazada en ${url}"
    printf '  * %s\n' "${errores[@]}"
  } >&2
  exit 1
fi

echo "CSP verificada en ${url}"
