#!/usr/bin/env bash
# Valida el nombre de una rama contra la convención del proyecto (ADR-0004).
# Uso: scripts/check-branch-name.sh <nombre de la rama>
# Lo ejecutan el hook pre-push (local) y el pipeline de CI (en cada PR).
set -euo pipefail
export LC_ALL=C

rama="${1:?Falta el nombre de la rama}"

case "$rama" in
  main | dependabot/*) exit 0 ;;
esac

tipos='funcionalidad|correccion|refactor|rendimiento|pruebas|documentacion|ci|mantenimiento'
patron="^(${tipos})/([0-9]+-)?[a-z0-9]+(-[a-z0-9]+)*$"

if [[ ! "$rama" =~ $patron ]] || (( ${#rama} > 60 )); then
  {
    echo "Nombre de rama rechazado: ${rama}"
    echo "  * Formato: <tipo>/<número de issue opcional>-<descripción>"
    echo "  * Tipos: ${tipos//|/, }"
    echo "  * Solo minúsculas, números y guiones; sin tildes ni ñ; máximo 60 caracteres."
    echo "  * Ejemplo: funcionalidad/12-importacion-csv"
  } >&2
  exit 1
fi
