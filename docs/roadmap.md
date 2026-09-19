# Roadmap

Cada fase es un corte vertical desplegable. No se empieza una fase con la anterior a medias.

## Fase 0: esqueleto andante (desplegado desde el día 1)
* [x] Scaffolding backend (uv, FastAPI, SQLAlchemy, Alembic) y frontend (Vite, React, TS)
* [x] Docker Compose: api, db, web; healthchecks; imágenes multi-stage sin root
* [x] Validación de mensajes de commit: hook local `commit-msg` y job de CI con el mismo script
* [x] Escaneo de secretos en CI (gitleaks) y Dependabot para las acciones
* [x] CI: ruff, mypy, import-linter, pytest, tsc, eslint, vitest, pip-audit, npm audit, escaneo de imágenes
* [x] Hooks locales con los mismos scripts que la CI: `pre-commit` rápido sobre lo
  que cambió y `pre-push` con todos los chequeos de código (ADR-0012)
* [x] Base de datos de tests declarada en `docker-compose.yml` (perfil `test`), para
  que los tests de integración y `alembic check` salgan del repositorio
* [x] Pruebas de extremo a extremo en navegador (Playwright) sobre el build de
  producción, con la invariante de que la navegación no se recorta (ADR-0013)
* [x] Protección de `main`: PR obligatorio, CI en verde, historial lineal
* [x] Estrategia de ramas con nombres en español, validada en hook y en CI (ADR-0004)
* [x] CD: al mergear a `main`, build de imágenes, migraciones, despliegue y smoke test automáticos
* [x] Tipos TS generados desde OpenAPI, con verificación de desvíos en CI
* [x] i18n base (es/en) y selector de idioma
* [x] Deploy del "hola mundo" a un entorno público: https://rinde.meratim.workers.dev

## Fase 1: autenticación (ADR-0007)
* [x] Backend: registro, inicio y cierre de sesión, recuperación con código; argon2id; sesiones opacas en cookie `__Host-`; CSRF por encabezado propio
* [x] Límite de intentos fallidos por cuenta (NIST SP 800-63B-4)
* [x] Límite por dirección de origen y por registros; limpieza de intentos viejos en cada escritura
* [x] Frontend: pantallas de registro, inicio de sesión, recuperación y guardado del código
* [x] Test de autorización reutilizable (recurso ajeno → 404), construido con las cuentas (ADR-0009)

## Fase 2: cuentas y transacciones
* [x] Kernel de dinero: `Money` y `Currency`
* [x] Cuentas (efectivo, banco, tarjeta, billetera cripto) con moneda propia: API y pantallas (lista, alta, detalle con renombrar y archivar)
* [x] Ingresos y gastos con categorías propias y sembradas, y saldo por cuenta
* [x] Transferencias entre cuentas propias (no cuentan como gasto), con el monto de
  cada lado cuando cambian de moneda (ADR-0014). Falta sumarlas a la lista de
  movimientos: por ahora se ven en el detalle de cada cuenta
* [x] Paginación por cursor, `Idempotency-Key` y log de auditoría append-only
* [ ] Filtros por categoría y por texto en la lista de movimientos
* [ ] Tipo de cuenta billetera virtual (Mercado Pago, Ualá, Naranja X), después de
  los movimientos: hoy hay que cargarlas como efectivo. Admite pesos y dólares, no
  Bitcoin, que sigue solo en billeteras cripto (ADR-0009, decisión 4). Sumar un
  valor al tipo de cuenta toca dominio, migración con la restricción de la base,
  contrato y pantallas

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
* [ ] Playwright e2e de los 3 flujos críticos contra el entorno completo. El
  andamiaje ya existe y corre en CI desde la fase 0: se adelantó porque es el
  único tipo de prueba que ve el maquetado (ADR-0013)

## Después (solo si hay tiempo)
* Secreto compartido entre el Worker y la API: hoy el origen de Render es alcanzable
  desde internet, así que quien lo llame directo puede inventar la cabecera con la
  dirección de origen y esquivar ese límite (no el límite por cuenta)
* Ingreso con Google y Microsoft por OpenID Connect (código con PKCE, validado en el
  backend), con la misma sesión en cookie. Requiere un ADR que reemplace a ADR-0007
  (hoy sin email ni datos personales), dominio propio para las URL de retorno y
  vinculación solo desde una sesión abierta, nunca por coincidencia de email
* MFA TOTP · exportación y borrado de datos del usuario · OpenTelemetry · PWA · notificaciones por email
