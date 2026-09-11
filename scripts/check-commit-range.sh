#!/usr/bin/env bash
# Valida los mensajes de todos los commits de un rango (uso en CI).
# Uso: scripts/check-commit-range.sh <sha base> <sha head>
# Si la base está vacía, es 000…0 (primer push de una rama) o no existe en el
# clon (push forzado que reemplazó el historial), valida todo el historial
# alcanzable desde head.
set -euo pipefail

base="${1:-}"
head="${2:?Falta el sha head}"

if [[ -z "$base" || "$base" =~ ^0+$ ]] || ! git cat-file -e "${base}^{commit}" 2>/dev/null; then
  rango="$head"
else
  rango="${base}..${head}"
fi

dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
tmp="$(mktemp)"
trap 'rm -f "$tmp"' EXIT

fallos=0
while read -r sha; do
  # Los commits de bots (Dependabot) usan el formato que define GitHub:
  # excepción documentada en ADR-0004.
  if [[ "$(git log -1 --format=%ae "$sha")" == *"[bot]@users.noreply.github.com" ]]; then
    continue
  fi
  git log -1 --format=%B "$sha" > "$tmp"
  if ! "$dir/check-commit-msg.sh" "$tmp"; then
    echo "  (commit ${sha})" >&2
    fallos=1
  fi
done < <(git rev-list --no-merges "$rango")

exit "$fallos"
