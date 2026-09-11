# Rinde

Aplicación web de finanzas personales para Argentina y LatAm. Responde una pregunta concreta: ¿me rinde el sueldo?

**Estado:** en construcción. El avance está en el [roadmap](docs/roadmap.md).

## Qué va a hacer

* Registrar ingresos, gastos y transferencias en varias cuentas y monedas.
* Convertir con la cotización que corresponda (oficial, MEP, CCL, blue, tarjeta o cripto) a la fecha de cada operación.
* Presupuestos mensuales con alertas.
* Reportes en pesos constantes, ajustados por inflación.
* Interfaz en español y en inglés.

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

Para validar ambas cosas en tu clon antes de commitear y de pushear:

```bash
git config core.hooksPath .githooks
```

La CI aplica las mismas validaciones y escanea el historial en busca de secretos.
