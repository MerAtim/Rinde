# ADR-0001: Monolito modular con FastAPI y Clean Architecture

* **Estado:** Aceptado
* **Fecha:** 2026-09-11

## Contexto

La premisa pide "Python para analítica + REST API" y demostrar Clean Architecture, SOLID y patrones. Hay un solo desarrollador, sin tráfico real, y el objetivo es un portfolio fullstack. "Analítica" puede leerse como un servicio aparte, pero las agregaciones previstas (gasto por categoría, flujo mensual, patrimonio neto) son consultas SQL con agregación, no cómputo pesado.

## Opciones consideradas

### Opción A: monolito modular en FastAPI, capas por módulo
* Pros: un solo deploy, transacciones ACID entre módulos, límites de módulo verificables con import-linter, OpenAPI automático para generar el cliente TS.
* Contras: FastAPI no trae auth, admin ni ORM integrados; hay más código propio (más superficie de bugs).

### Opción B: microservicios (API + servicio de analítica)
* Pros: suena mejor en un CV.
* Contras: consistencia distribuida, dos deploys, red entre servicios, observabilidad distribuida. Complejidad sin un problema que la justifique; un revisor técnico lo lee como sobreingeniería.

### Opción C: Django + DRF
* Pros: auth, admin y migraciones de serie.
* Contras: los modelos Active Record acoplan dominio y persistencia. Aplicar Clean Architecture ahí es ir contra el framework.

## Decisión

Opción A. La separación que importa es de responsabilidades dentro del código, y se puede verificar; la separación en procesos no aporta nada con este volumen.

## Consecuencias

* Positivas: dominio testeable sin base de datos, límites auditables en CI, un solo `docker compose up`.
* Negativas / costos aceptados: capa de mapeo entidad ↔ ORM (boilerplate); en módulos CRUD triviales las capas pesan más de lo que aportan.
* Riesgos: sobreingeniería en CRUD simple. Mitigación: módulos triviales pueden tener capas más delgadas, pero siempre respetando la regla de dependencia.

## Supuestos y datos faltantes

* Se asume que las librerías clave (asyncpg/psycopg, argon2-cffi, SQLAlchemy) tienen wheels para la versión de Python elegida. Se verifica en el scaffolding; si fallan, fijar la versión menor anterior en Docker.

## Referencias

* import-linter: contratos de capas verificables en CI.
