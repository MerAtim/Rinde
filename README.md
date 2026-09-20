# Rinde

Aplicación web de finanzas personales para Argentina y LatAm. Responde una pregunta concreta: ¿me rinde el sueldo?

**Estado:** en construcción. El avance está en el [roadmap](docs/roadmap.md).

## Qué hace hoy

* **Cuentas** en efectivo, banco, tarjeta o billetera cripto, cada una con su moneda (pesos, dólares o Bitcoin). Se renombran y se archivan sin perder su historia ([ADR-0009](docs/adr/0009-modelo-de-cuentas.md)).
* **Ingresos y gastos** con categorías propias y sembradas, borrado reversible y saldo por cuenta ([ADR-0011](docs/adr/0011-modelo-de-movimientos.md)).
* **Transferencias entre cuentas propias**, que no cuentan como gasto ni como ingreso. Entre monedas distintas se guardan los dos montos, sin inventar una cotización: la tasa real es la que te dieron ([ADR-0014](docs/adr/0014-modelo-de-transferencias.md)).
* **Una sola lista** con movimientos y transferencias, paginada por cursor. Los reportes de gasto siguen leyendo solo los movimientos: una transferencia no ensucia el resumen por categoría.
* **Filtros por categoría y por texto**, que se comparten en la dirección. La búsqueda no distingue tildes ni mayúsculas: "panaderia" encuentra "Panadería".
* **Cuenta y sesión** con usuario, contraseña y código de recuperación, sin email ([ADR-0007](docs/adr/0007-autenticacion.md)).
* **Interfaz en español y en inglés**, con modo oscuro y claro.

## Qué falta

* Convertir con la cotización que corresponda (oficial, MEP, CCL, blue, tarjeta o cripto) a la fecha de cada operación.
* Presupuestos mensuales con alertas.
* Reportes en pesos constantes, ajustados por inflación.
* Importar resúmenes en CSV.

El detalle y el orden están en el [roadmap](docs/roadmap.md).

## Stack

* **Backend:** Python, FastAPI, SQLAlchemy, PostgreSQL.
* **Frontend:** React, TypeScript, TanStack Query, Zustand, Chart.js.
* **Infraestructura:** Docker Compose y GitHub Actions.

## Cómo correrlo

Requisito: Docker. Para desarrollar sin contenedores hacen falta además [uv](https://docs.astral.sh/uv/) y Node 22.

```bash
cp .env.example .env   # completar POSTGRES_PASSWORD
docker compose up --build
```

La aplicación queda en http://localhost:8080 y el estado de la API en http://localhost:8080/api/health/ready. Si el puerto 8080 está ocupado, definí otro en `RINDE_WEB_PORT` dentro de `.env`.

### Desarrollo

* **Backend** (`backend/`): `uv sync`, `uv run pytest`, `uv run ruff check .`, `uv run mypy`, `uv run lint-imports`.
* **Frontend** (`frontend/`): `npm ci`, `npm run dev`, `npm test`, `npm run lint`, `npm run typecheck`.
* **Base de datos:** no se publica fuera de la red interna de Docker. Para conectarte desde tu máquina, creá un `docker-compose.override.yml` (ignorado por git) que agregue `ports: ["127.0.0.1:<puerto>:5432"]` al servicio `db`.
* **Contrato de la API:** el backend publica su contrato en `backend/openapi.json` y el frontend genera sus tipos a partir de él. Si cambia un endpoint, regenerar con `uv run python -m rinde.openapi openapi.json` (en `backend/`) y `npm run generate:api` (en `frontend/`). La CI verifica que estén al día.

## En producción

Se publica automáticamente al integrar en `main` ([ADR-0005](docs/adr/0005-hosting-gratuito.md)): frontend en Cloudflare Workers, API en Render y PostgreSQL en Neon, todo en planes gratuitos. La imagen que se despliega es la misma que pasó el escaneo de vulnerabilidades.

**Dirección pública:** https://rinde.meratim.workers.dev

La API corre en una instancia gratuita de Render (0,1 CPU, 512 MB de RAM) que se suspende tras 15 minutos sin tráfico: el primer pedido después de una pausa puede tardar alrededor de un minuto.

## Decisiones de arquitectura

Cada decisión importante está registrada con sus alternativas y costos en [docs/adr](docs/adr/README.md).

## Convenciones

* **Ramas:** GitHub Flow. Todo cambio entra a `main` por pull request desde una rama con nombre en español, por ejemplo `funcionalidad/12-importacion-csv` ([ADR-0004](docs/adr/0004-estrategia-de-ramas.md)).
* **Diseño:** Material 3 con identidad propia, modo oscuro por defecto. Especificación en [docs/design-system.md](docs/design-system.md) ([ADR-0006](docs/adr/0006-sistema-de-diseno.md)).
* **Commits:** [Conventional Commits](https://www.conventionalcommits.org/es/v1.0.0/) con descripción en español.

## Chequeos locales

Los hooks del repositorio corren los mismos scripts que la CI, para que no puedan
divergir ([ADR-0012](docs/adr/0012-chequeos-locales-y-en-ci.md)). Se activan una
sola vez por clon:

```bash
git config core.hooksPath .githooks
```

Qué hace cada uno:

* `commit-msg`: valida el mensaje del commit.
* `pre-commit`: formato y estilo sobre los archivos que cambiaron, y frena
  cualquier archivo de entorno que no sea `.env.example`. Tarda segundos.
* `pre-push`: bloquea el push directo a `main`, valida el nombre de la rama y
  corre todos los chequeos de código: `scripts/check-backend.sh`,
  `scripts/check-frontend.sh` y `scripts/check-contract.sh`.

Los scripts también se pueden correr a mano, enteros o de a un chequeo:

```bash
scripts/check-backend.sh          # format, lint, types, layers, migrations, tests
scripts/check-frontend.sh types   # solo uno
scripts/check-contract.sh
```

Las pruebas de extremo a extremo corren en un navegador de verdad, contra el
build de producción ([ADR-0013](docs/adr/0013-pruebas-de-extremo-a-extremo.md)).
El navegador se baja una sola vez por clon:

```bash
cd frontend && npx playwright install chromium
```

Para omitirlas a sabiendas: `RINDE_SKIP_E2E=1`.

El chequeo de migraciones y los tests de integración necesitan un PostgreSQL de
verdad. Está declarado en el compose bajo el perfil `test`, así que no se levanta
con `docker compose up`:

```bash
docker compose --profile test up --detach --wait test-db
export RINDE_DATABASE_URL=postgresql+psycopg://rinde:solo_para_tests@127.0.0.1:55432/rinde_test
```

En Windows va `127.0.0.1` y no `localhost`: `localhost` resuelve primero a IPv6 y
el puerto se publica solo en IPv4, así que la conexión no falla, se cuelga.

Sin base se puede seguir con `RINDE_SKIP_DB_CHECKS=1`: se omiten el chequeo de
migraciones y los tests de integración, y **la cobertura no se compara contra el
mínimo**, porque sin esos tests el número no sería comparable. La CI siempre
tiene base y siempre la compara
([ADR-0012](docs/adr/0012-chequeos-locales-y-en-ci.md), decisión 4).

Los chequeos de dependencias (`pip-audit`, `npm audit`), el escaneo de imágenes y
el de secretos corren solo en la CI: su resultado cambia sin que cambie el código
y no sirven como puerta local ([ADR-0012](docs/adr/0012-chequeos-locales-y-en-ci.md),
decisión 3).
