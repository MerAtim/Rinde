#!/usr/bin/env bash
# Valida un mensaje de commit contra las convenciones del proyecto.
# Uso: scripts/check-commit-msg.sh <archivo con el mensaje>
# Lo ejecutan el hook commit-msg (local) y el pipeline de CI (por cada commit).
set -euo pipefail
export LC_ALL=C.UTF-8

archivo="${1:?Falta la ruta del archivo con el mensaje}"

# Descarta el diff que agrega `git commit -v` y las líneas de comentario.
mensaje="$(sed '/^# -\{24\} >8 -\{24\}$/,$d' "$archivo" | grep -v '^#' || true)"
asunto="$(printf '%s\n' "$mensaje" | sed -n '1p')"

case "$asunto" in
  "Merge "* | "fixup! "* | "squash! "* | "amend! "*) exit 0 ;;
esac

errores=()
tipos='feat|fix|refactor|perf|test|docs|build|ci|chore|style|revert'

if ! printf '%s' "$asunto" | grep -qP "^(${tipos})(\([a-z0-9ñáéíóúü]+\))?!?: \S"; then
  errores+=("El asunto no respeta el formato <tipo>(<ámbito>): <descripción>. Tipos válidos: ${tipos//|/, }.")
fi

if printf '%s' "$asunto" | grep -qP '^[^:]+: [A-ZÁÉÍÓÚÑ]'; then
  errores+=("La descripción empieza con minúscula.")
fi

if (( ${#asunto} > 72 )); then
  errores+=("El asunto tiene ${#asunto} caracteres; el máximo es 72.")
fi

if printf '%s' "$asunto" | grep -qP '\.$'; then
  errores+=("El asunto no termina en punto.")
fi

if [[ -n "$(printf '%s\n' "$mensaje" | sed -n '2p')" ]]; then
  errores+=("La segunda línea debe quedar vacía para separar asunto y cuerpo.")
fi

# Se cuenta en caracteres con bash (LC_ALL=C.UTF-8): awk cuenta bytes en algunas
# plataformas y una línea con tildes podría pasar en local y fallar en CI.
linea_larga=false
while IFS= read -r linea; do
  if (( ${#linea} > 72 )) && [[ "$linea" != *http://* && "$linea" != *https://* ]]; then
    linea_larga=true
  fi
done <<< "$mensaje"
if [[ "$linea_larga" == true ]]; then
  errores+=("Hay líneas del cuerpo con más de 72 caracteres.")
fi

if printf '%s\n' "$mensaje" | grep -qiP '^co-authored-by:'; then
  errores+=("No se permiten trailers Co-authored-by: los commits son de autor único.")
fi

if printf '%s\n' "$mensaje" | grep -qiP 'generated with|generado con'; then
  errores+=("No se permiten firmas de herramientas en el mensaje.")
fi

if printf '%s\n' "$mensaje" | grep -qP '[\x{2013}\x{2014}\x{2015}]'; then
  errores+=("No se usan guion medio ni guion largo (– —). Reformular con coma, dos puntos o punto.")
fi

if printf '%s\n' "$mensaje" | grep -qP '(^|\s)-(\s|$)'; then
  errores+=("El guion (-) no se usa como puntuación ni como viñeta. Para listas usar *.")
fi

if printf '%s\n' "$mensaje" | grep -qP '[\x{1F000}-\x{1FAFF}\x{2600}-\x{27BF}\x{2B00}-\x{2BFF}\x{FE0F}\x{200D}]'; then
  errores+=("No se permiten emojis.")
fi

if (( ${#errores[@]} > 0 )); then
  {
    echo "Mensaje de commit rechazado:"
    printf '  * %s\n' "${errores[@]}"
    echo "Asunto: ${asunto}"
  } >&2
  exit 1
fi
