# Roadmap

Cada fase es un corte vertical desplegable. No se empieza una fase con la anterior a medias.

## Fase 0: esqueleto andante (desplegado desde el día 1)
* [x] Scaffolding backend (uv, FastAPI, SQLAlchemy, Alembic) y frontend (Vite, React, TS)
* [x] Docker Compose: api, db, web; healthchecks; imágenes multi-stage sin root
* [x] Validación de mensajes de commit: hook local `commit-msg` y job de CI con el mismo script
* [x] Escaneo de secretos en CI (gitleaks) y Dependabot para las acciones
* [x] CI: ruff, mypy, import-linter, pytest, tsc, eslint, vitest, pip-audit, npm audit, escaneo de imágenes
* [ ] pre-commit con los mismos chequeos que la CI
* [x] Protección de `main`: PR obligatorio, CI en verde, historial lineal
* [x] Estrategia de ramas con nombres en español, validada en hook y en CI (ADR-0004)
* [x] CD: al mergear a `main`, build de imágenes, migraciones, despliegue y smoke test automáticos
* [x] Tipos TS generados desde OpenAPI, con verificación de desvíos en CI
* [x] i18n base (es/en) y selector de idioma
* [x] Deploy del "hola mundo" a un entorno público: https://rinde.meratim.workers.dev

## Fase 1: autenticación (ADR-0007)
* [x] Backend: registro, inicio y cierre de sesión, recuperación con código; argon2id; sesiones opacas en cookie `__Host-`; CSRF por encabezado propio
* [x] Límite de intentos fallidos por cuenta (NIST SP 800-63B-4)
* [ ] Límite por dirección IP y por registros; limpieza periódica de intentos viejos
* [ ] Frontend: pantallas de registro, inicio de sesión, recuperación y guardado del código
* [ ] Test de autorización reutilizable (recurso ajeno → 404)

## Fase 2: cuentas y transacciones
* [ ] Cuentas (efectivo, banco, tarjeta, billetera cripto) con moneda propia
* [ ] Ingresos, gastos, transferencias (no cuentan como gasto), categorías
* [ ] Filtros, paginación por cursor, `Idempotency-Key`, log de auditoría

## Fase 3: cotizaciones (ADR-0002)
* [ ] Puerto `RateProvider` + adaptadores + fallback + caché + histórico propio
* [ ] Snapshot de conversión en la transacción; moneda y tipo de referencia por usuario

## Fase 4: dashboard
* [ ] Gasto por categoría, flujo mensual, patrimonio neto en ARS y en USD (tipo elegido)
* [ ] Filtros globales sincronizados con la URL; alternativa en tabla para accesibilidad
* [ ] Objetivo medible: p95 < 300 ms del endpoint de dashboard con 50k transacciones (sembradas)

## Fase 5: presupuestos y alertas
* [ ] Presupuestos mensuales por categoría
* [ ] Alertas in-app al 80 % y 100 %, disparadas por eventos de dominio al registrar gastos

## Fase 6: importación
* [ ] CSV/extractos: Strategy por formato, vista previa, deduplicación por hash, reglas de categorización

## Fase 7: diferenciales Argentina
* [ ] Reportes en pesos constantes (ajuste por IPC)
* [ ] Gastos en cuotas (reparto exacto por resto mayor) y transacciones recurrentes

## Fase 8: portfolio
* [ ] Cuenta demo con datos sembrados realistas (sin registro)
* [ ] README: arquitectura, diagrama, ADRs, capturas, cómo correrlo, métricas reales
* [ ] Playwright e2e de los 3 flujos críticos

## Después (solo si hay tiempo)
* MFA TOTP · exportación y borrado de datos del usuario · OpenTelemetry · PWA · notificaciones por email
