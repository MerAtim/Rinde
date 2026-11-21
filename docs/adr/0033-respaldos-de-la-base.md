# ADR-0033: Respaldo diario de la base, cifrado y probado, en GitHub Actions

* **Estado:** Aceptado
* **Fecha:** 2026-11-21

## Contexto

La base de producción está en Neon Free (ADR-0005). Hechos del plan, según [la página de planes de Neon](https://neon.com/docs/introduction/plans) (consultada el 2026-11-21):

* La historia para volver a un punto anterior dura 6 horas, con un tope de 1 GB de cambios.
* No hay respaldos programados: "scheduled backups are not available on the Free plan". Hay un único snapshot manual.

Entonces, un borrado por error, una migración que rompe datos o un acceso indebido a la cuenta de Neon que se descubre después de 6 horas no tiene vuelta atrás. Para una app que guarda las finanzas de sus usuarios no es aceptable. Las guías de referencia piden copias periódicas fuera del proveedor principal, protegidas y con la restauración probada:

* NIST SP 800-34, plan de contingencia.
* CIS Controls v8, control 11, "Data Recovery".
* OWASP ASVS V8, protección de datos.

Restricciones:

* Todo en planes gratuitos.
* Una sola persona opera el sistema.
* El repositorio es público: los logs y artefactos de Actions los lee cualquiera con cuenta de GitHub.

## Opciones consideradas

### Dónde se guardan las copias

#### Opción A: artefactos de GitHub Actions

* Pros:
  * No hay cuenta nueva ni credencial nueva que custodiar.
  * El workflow ya tiene acceso a la base en el entorno `produccion`, que solo admite `main`.
  * Es un proveedor distinto de Neon.
* Contras:
  * La retención máxima es de 90 días.
  * Quien tome la cuenta de GitHub puede borrar las copias.
  * En un repositorio público cualquiera puede descargar el archivo, así que el cifrado es obligatorio.

#### Opción B: Cloudflare R2 con bloqueo de borrado

* Pros:
  * 10 GB gratis.
  * Las copias no se pueden borrar antes de tiempo, ni con un token robado.
  * Ya hay cuenta de Cloudflare.
* Contras:
  * Activar R2 exige cargar un medio de pago.
  * Suma un token con permiso de escritura que custodiar.

#### Opción C: Backblaze B2 con bloqueo de borrado

* Pros:
  * 10 GB gratis, sin tarjeta.
  * Bloqueo de borrado.
* Contras:
  * Un proveedor y una credencial más para administrar.

### Cómo se cifran

#### Opción 1: OpenPGP con clave pública (GnuPG)

* Pros:
  * La CI solo puede cifrar: aunque se filtren todos los secretos de GitHub, las copias siguen cerradas.
  * GnuPG ya está en el runner y en Git para Windows: no se descarga ningún binario.
  * Es un estándar (RFC 9580).
* Contras:
  * La clave privada la custodia una persona, y si se pierde, se pierden las copias.

#### Opción 2: age con clave pública

* Pros:
  * Formato más simple y moderno.
* Contras:
  * No viene instalado.
  * Sus versiones no publican checksums, solo pruebas de transparencia que requieren otra herramienta para verificarse. Sería un binario más en la cadena de suministro.

#### Opción 3: cifrado simétrico con una frase guardada como secreto de GitHub

* Pros:
  * Es lo más simple.
* Contras:
  * El mismo lugar que guarda las copias guarda la clave para abrirlas. Quien tome la cuenta de GitHub tiene las dos.

## Decisión

Opción A con opción 1. La persona que opera el sistema eligió A el 2026-11-21: cubre el hueco real, que es no tener ninguna copia fuera de Neon, sin sumar cuentas ni credenciales. El cifrado con clave pública compensa que el repositorio sea público y que GitHub guarde las copias.

Cada día, el workflow `respaldo.yml` corre `scripts/backup-database.sh`:

1. **Copia:** `pg_dump` en formato custom, sin dueños ni permisos, con el cliente de PostgreSQL 18 de la imagen oficial fijada por digest. El cliente del runner es más viejo y `pg_dump` no copia un servidor más nuevo que él.
2. **Prueba de restauración:** la copia se restaura entera en una base vacía, en una sola transacción y cortando en el primer error. Después se comparan con producción la cantidad de tablas y la migración de Alembic. Una copia que no pasa no se guarda.
3. **Cifrado:** la copia se cifra con la clave pública de `.github/respaldo/clave-publica.asc` y se guarda 90 días como artefacto.
4. **Aviso:** si falla, se abre un issue, como en la auditoría de dependencias, y se cierra solo con la primera copia buena.

Ni el log ni el resumen muestran datos de la base, ni siquiera cantidades de filas, y el detalle de un error de restauración no se publica porque puede citar valores. Cómo restaurar y la tabla de ensayos están en [docs/respaldos.md](../respaldos.md).

## Consecuencias

* Positivas:
  * Se puede volver a cualquier día de los últimos 90, no solo a las últimas 6 horas.
  * Cada copia guardada ya se restauró una vez.
  * Las copias no se pueden leer sin la clave privada, que no está en GitHub.
* Negativas / costos aceptados:
  * Con una copia por día se pueden perder hasta 24 horas de datos. Las primeras 6 horas las cubre la historia de Neon.
  * No hay copias de más de 90 días.
  * Quien tome la cuenta de GitHub puede borrar las copias, aunque no leerlas. Las opciones B o C lo evitarían.
  * El workflow usa el usuario de la base que corre las migraciones. Un rol de solo lectura para el respaldo achicaría el daño si se filtrara ese secreto, a cambio de otro secreto más.
  * Cada corrida queda registrada como un despliegue del entorno `produccion`.
* Riesgos y cómo se mitigan:
  * **Pérdida de la clave privada:** se guarda en un gestor de contraseñas y en una segunda copia fuera de línea, con frase de contraseña.
  * **Workflow desactivado:** GitHub desactiva los workflows programados de un repositorio público tras 60 días sin actividad. Si pasa, no se abre ningún issue. El ensayo trimestral lo detecta, y se reactiva desde la pestaña Actions.
  * **Restauración que nunca se ensaya:** la prueba automática cubre el formato y el esquema. El ensayo trimestral cubre el descifrado, la descarga y el cambio de base, y queda anotado en la tabla de `docs/respaldos.md`.

## Supuestos y datos faltantes

* **Tamaño de la base:** se asume que sigue chica, de pocos megas, y que la copia termina en minutos. El log de cada corrida informa el tamaño cifrado. Si pasara del límite de 0,5 GB de Neon Free, el problema sería otro.
* **Versión de PostgreSQL en Neon:** se asume que es la 18 o una anterior. Si Neon pasara a una más nueva, `pg_dump` fallaría y el aviso lo haría ver.

## Referencias

* [Neon: planes, historia y snapshots](https://neon.com/docs/introduction/plans)
* [GitHub: retención de artefactos](https://docs.github.com/en/actions/writing-workflows/choosing-what-your-workflow-does/storing-and-sharing-data-from-a-workflow)
* [PostgreSQL 18: pg_dump](https://www.postgresql.org/docs/18/app-pgdump.html)
* [RFC 9580: OpenPGP](https://www.rfc-editor.org/rfc/rfc9580)
* NIST SP 800-34 Rev. 1, Contingency Planning Guide for Federal Information Systems
* CIS Controls v8, control 11: Data Recovery
