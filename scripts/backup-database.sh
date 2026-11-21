#!/usr/bin/env bash
# Respaldo de la base: copia, prueba de restauración y cifrado (ADR-0033).
# Uso: scripts/backup-database.sh <archivo de salida .gpg>
#
# Variables:
#   ORIGEN        URL de la base que se respalda. Acepta la de SQLAlchemy
#                 (postgresql+psycopg://...), la misma que usa la API.
#   VERIFICACION  URL de una base vacía donde se prueba la restauración.
#   CLAVE         Archivo con la clave pública OpenPGP que cifra la copia.
#   PG            Prefijo para pg_dump, pg_restore y psql. En la CI es un
#                 `docker run` con la imagen de PostgreSQL 18, la misma versión
#                 de la base. Vacío, se usan las del PATH.
#
# El log de un repositorio público lo lee cualquiera: el script nunca imprime
# datos de la base, ni siquiera cantidades de filas, y solo deja salir la copia
# ya cifrada.
set -euo pipefail

salida="${1:?Falta el archivo de salida}"
: "${ORIGEN:?Falta ORIGEN}"
: "${VERIFICACION:?Falta VERIFICACION}"
: "${CLAVE:?Falta CLAVE}"
read -r -a pg <<< "${PG:-}"

trabajo="$(mktemp -d)"
trap 'rm -rf "$trabajo"' EXIT
copia="$trabajo/rinde.dump"
origen="${ORIGEN/postgresql+psycopg:/postgresql:}"

consultar() {
  "${pg[@]}" psql --no-psqlrc --quiet --tuples-only --no-align \
    --set ON_ERROR_STOP=1 --dbname="$1" --command="$2"
}

# Formato custom: comprimido, y pg_restore elige qué restaurar y en qué orden.
# Sin dueños ni permisos: la base de destino tiene sus propios roles.
echo "Copiando la base..."
"${pg[@]}" pg_dump --format=custom --no-owner --no-acl --dbname="$origen" > "$copia"

# Una copia que no se puede restaurar no es un respaldo. Se restaura entera, en
# una sola transacción y cortando en el primer error, en una base vacía.
echo "Probando que se restaura en una base vacía..."
if ! "${pg[@]}" pg_restore --exit-on-error --single-transaction --no-owner --no-acl \
  --dbname="$VERIFICACION" < "$copia" 2> "$trabajo/restauracion.log"; then
  echo "::error::La copia no se pudo restaurar. No se guarda." >&2
  # El mensaje puede citar valores de una fila: se publica solo qué objeto del
  # esquema falló (la línea "from TOC entry", que nombra tipo y nombre), el
  # error y el comando de esquema que lo causó ("Command was"; las filas viajan
  # aparte, en el COPY, y no aparecen ahí), con todo lo que va entre comillas
  # tapado. Las líneas DETAIL, que citan valores, no salen.
  grep -E 'from TOC entry|ERROR:|Command was:' "$trabajo/restauracion.log" \
    | sed -E "s/\"[^\"]*\"/\"...\"/g; s/'[^']*'/'...'/g" \
    | cut -c1-300 | head -n 6 >&2 || true
  exit 1
fi

tablas="SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public'"
version="SELECT version_num FROM alembic_version"
if [[ "$(consultar "$origen" "$tablas")" != "$(consultar "$VERIFICACION" "$tablas")" ]]; then
  echo "::error::La restauración no tiene las mismas tablas que la base." >&2
  exit 1
fi
migracion="$(consultar "$VERIFICACION" "$version")"
if [[ -z "$migracion" || "$migracion" != "$(consultar "$origen" "$version")" ]]; then
  echo "::error::La restauración no quedó en la misma migración que la base." >&2
  exit 1
fi

# Cifrado con clave pública: la CI puede cifrar, pero no descifrar. La clave
# privada no está en GitHub. Un directorio de GnuPG descartable evita depender
# del llavero de la máquina.
echo "Cifrando..."
(umask 077 && mkdir "$trabajo/gnupg")
gpg --batch --no-tty --quiet --homedir "$trabajo/gnupg" \
  --recipient-file "$CLAVE" --output "$salida" --encrypt "$copia"

echo "Copia en la migración $migracion, restaurada y cifrada: $(wc -c < "$salida") bytes."
