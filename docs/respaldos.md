# Respaldos de la base

Todos los días, el workflow [Respaldo de la base](../.github/workflows/respaldo.yml) copia la base de producción, prueba que la copia se restaura en una base vacía, la cifra y la guarda 90 días como artefacto de GitHub Actions. Por qué así y no de otra forma: [ADR-0033](adr/0033-respaldos-de-la-base.md).

Este documento dice cómo abrir y restaurar una copia. Conviene tenerlo ensayado antes de necesitarlo: un respaldo que nunca se restauró no está probado.

## La clave

La copia se cifra con OpenPGP, con una clave pública que está en [.github/respaldo/clave-publica.asc](../.github/respaldo/clave-publica.asc). La CI solo puede cifrar. Para descifrar hace falta la clave privada, que **nunca** entra al repositorio ni a GitHub.

Si se pierde la clave privada, las copias guardadas no se pueden abrir. Si se filtra, quien la tenga puede leer las copias de los últimos 90 días. Por eso:

* La clave privada vive en un gestor de contraseñas y, si es posible, en una segunda copia fuera de línea.
* La clave tiene frase de contraseña: un archivo robado no alcanza.

### Generarla (una sola vez)

En Git Bash, que ya trae `gpg`:

```bash
gpg --quick-gen-key "Rinde respaldo" future-default default never
gpg --armor --export "Rinde respaldo" > .github/respaldo/clave-publica.asc
gpg --armor --export-secret-keys "Rinde respaldo" > rinde-respaldo-privada.asc
```

El primer comando pide la frase de contraseña. El segundo deja la clave pública en el repositorio. El tercero exporta la privada: se guarda en el gestor de contraseñas y el archivo se borra.

### Cambiarla

Si la privada se filtró o se perdió, se genera una nueva, se reemplaza `clave-publica.asc` por PR y se corre el workflow a mano. Si se filtró, las copias viejas cifradas con ella se borran desde la pestaña Actions.

## Restaurar

### 1. Descargar una copia

Desde la pestaña Actions, en una corrida de "Respaldo de la base", o con la CLI:

```bash
gh run list --workflow respaldo.yml --status success --limit 5
gh run download <id de la corrida> --name rinde-AAAA-MM-DD.dump.gpg --dir respaldo
```

Cada artefacto se llama como su archivo, `rinde-AAAA-MM-DD.dump.gpg`, con la fecha de la copia en UTC.

### 2. Descifrar

```bash
gpg --output rinde.dump --decrypt respaldo/rinde-AAAA-MM-DD.dump.gpg
```

Si la clave privada no está en el llavero, primero `gpg --import rinde-respaldo-privada.asc`. El archivo descifrado tiene datos reales: no se commitea, no se sube a ningún lado y se borra al terminar.

### 3. Restaurar en una base nueva

Nunca sobre la base en uso: primero en una base nueva, y se cambia cuando está verificada. En Neon, una base nueva dentro del mismo proyecto o un proyecto nuevo, con la URL de conexión directa (la que no dice `-pooler`).

```bash
docker run --rm -i postgres:18-alpine pg_restore \
  --exit-on-error --single-transaction --no-owner --no-acl \
  --dbname="postgresql://<usuario>:<contraseña>@<host>/<base>?sslmode=require" < rinde.dump
```

### 4. Verificar y cambiar

* `SELECT version_num FROM alembic_version` da la misma migración que dice el log del workflow para esa copia.
* Se entra a la app con una cuenta conocida y se ven sus movimientos.

Si está bien, se cambia `RINDE_DATABASE_URL` en Render y en el entorno `produccion` de GitHub por la URL de la base restaurada, y se vuelve a desplegar.

## Ensayos

Se ensaya la restauración completa, pasos 1 a 4 contra una base descartable, al menos una vez por trimestre y cada vez que cambia la clave.

| Fecha | Copia usada | Resultado |
| --- | --- | --- |
| | | |
