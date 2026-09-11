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

## Decisiones de arquitectura

Cada decisión importante está registrada con sus alternativas y costos en [docs/adr](docs/adr/README.md).

## Convenciones

* **Ramas:** GitHub Flow. Todo cambio entra a `main` por pull request desde una rama con nombre en español, por ejemplo `funcionalidad/12-importacion-csv` ([ADR-0004](docs/adr/0004-estrategia-de-ramas.md)).
* **Commits:** [Conventional Commits](https://www.conventionalcommits.org/es/v1.0.0/) con descripción en español.

Para validar ambas cosas en tu clon antes de commitear y de pushear:

```bash
git config core.hooksPath .githooks
```

La CI aplica las mismas validaciones y escanea el historial en busca de secretos.
