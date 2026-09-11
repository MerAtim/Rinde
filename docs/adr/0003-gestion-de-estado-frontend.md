# ADR-0003: Gestión de estado en el frontend

* **Estado:** Aceptado
* **Fecha:** 2026-09-11

## Contexto

La premisa dice "Context API/Zustand" sin elegir. Hay dos tipos de estado con necesidades opuestas:

* **Estado de servidor** (transacciones, presupuestos, cotizaciones): necesita caché, invalidación, reintentos, deduplicación de requests y estados de carga/error.
* **Estado de UI** (filtros de fecha, cuenta y moneda de referencia del dashboard): es local, síncrono y compartido entre gráficos.

## Opciones consideradas

### Opción A: TanStack Query (servidor) + Zustand (UI) + Context solo para tema e idioma
* Pros: cada herramienta para lo que resuelve. Los filtros en Zustand, con selectores, evitan re-renders de todos los gráficos.
* Contras: dos librerías de estado que aprender y justificar.

### Opción B: todo en Zustand, incluidas las respuestas del servidor
* Pros: una sola herramienta.
* Contras: hay que reimplementar a mano la caché, la invalidación y la sincronización. Es un antipatrón conocido y un revisor lo detecta.

### Opción C: solo Context API
* Pros: sin dependencias.
* Contras: cualquier cambio en un Context re-renderiza a todos sus consumidores. Con varios gráficos dependiendo de filtros, degrada la fluidez que pide la premisa.

## Decisión

Opción A. Los filtros del dashboard se sincronizan con la URL (query params) para que una vista sea compartible y sobreviva a un refresh.

## Consecuencias

* Positivas: separación explicable en una entrevista; menos código propio de caché.
* Negativas / costos aceptados: dos dependencias más; hay que decidir la fuente de verdad entre la URL y Zustand (se toma la URL).

## Supuestos y datos faltantes

* Se asume que no hace falta modo offline. Si más adelante se quiere PWA offline-first, esta decisión se revisa.
