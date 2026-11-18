# Rinde

Aplicación web de finanzas personales para Argentina y LatAm. Responde una pregunta concreta: ¿me rinde el sueldo?

## Probalo

**https://rinde.meratim.workers.dev**: en la pantalla de ingreso, "Probar la demo" abre una cuenta propia con tres meses de datos inventados, sin registrarse. Se borra sola a las dos horas ([ADR-0028](docs/adr/0028-cuenta-demo.md)).

La API corre en un plan gratuito que se suspende sin tráfico: si es la primera visita en un rato, la pantalla dice que el servidor se está despertando y puede tardar alrededor de un minuto.

![Dashboard de una demo: patrimonio de hoy, su evolución y los ingresos y gastos de cada mes](docs/capturas/dashboard.png)

| Movimientos | Presupuestos | Compras en cuotas | En el celular |
| --- | --- | --- | --- |
| ![Lista de movimientos con cuotas y recurrentes marcados](docs/capturas/movimientos.png) | ![Presupuestos del mes, uno cerca del tope](docs/capturas/presupuestos.png) | ![Una compra en seis cuotas con lo que falta pagar](docs/capturas/cuotas.png) | ![Presupuestos en una pantalla de 390 px](docs/capturas/presupuestos-celular.png) |

Las capturas salen de una demo real, contra la API y la base de verdad, con el aviso que ve cualquier visitante.

**Estado:** todas las fases del [roadmap](docs/roadmap.md) están completas.

## Qué hace hoy

* **Cuentas** en efectivo, banco, tarjeta, billetera virtual (Mercado Pago, Ualá, Naranja X) o billetera cripto, cada una con su moneda (pesos, dólares o Bitcoin). Se renombran y se archivan sin perder su historia ([ADR-0009](docs/adr/0009-modelo-de-cuentas.md)).
* **Ingresos y gastos** con categorías propias y sembradas, borrado reversible y saldo por cuenta ([ADR-0011](docs/adr/0011-modelo-de-movimientos.md)).
* **Transferencias entre cuentas propias**, que no cuentan como gasto ni como ingreso. Entre monedas distintas se guardan los dos montos, sin inventar una cotización: la tasa real es la que te dieron ([ADR-0014](docs/adr/0014-modelo-de-transferencias.md)).
* **Una sola lista** con movimientos y transferencias, paginada por cursor. Los reportes de gasto siguen leyendo solo los movimientos: una transferencia no ensucia el resumen por categoría.
* **Cotizaciones del dólar** oficial, MEP, CCL, blue, tarjeta y cripto, con compra, venta, fuente y fecha real. Si una fuente no responde, contesta la siguiente, pero nunca con otro tipo de dólar. Los días pasados se guardan la primera vez que se piden; para un período de meses se trae la serie entera en un solo pedido ([ADR-0016](docs/adr/0016-fuentes-de-cotizaciones.md), [ADR-0018](docs/adr/0018-modelo-de-lectura-del-dashboard.md)).
* **Precio del Bitcoin** del mercado internacional, de Kraken con Bitstamp de respaldo, sin clave y con un precio por día. Una billetera en Bitcoin muestra su equivalente, el dashboard lo suma al patrimonio y un gasto en Bitcoin cuenta en su presupuesto. Se convierte en dos pasos: a dólares con el precio del Bitcoin de ese día, y a pesos con el dólar que elegiste ([ADR-0029](docs/adr/0029-precio-del-bitcoin.md)).
* **Equivalentes y preferencias:** cada persona elige en qué moneda ve los totales y con qué dólar se convierte (por defecto, pesos al MEP). En Cuentas, el saldo de cada cuenta en la otra moneda muestra su equivalente. Se convierte con la cotización guardada del día y del lado prudente: nunca se valúa de más lo que tenés ni de menos lo que debés ([ADR-0017](docs/adr/0017-conversion-al-consultar.md)).
* **Gastos en dólares con tarjeta:** se valúan con el mismo dólar de referencia que todo lo demás. Si pagás el resumen en pesos, cargalo como una transferencia de tu cuenta en pesos a la tarjeta en dólares: guarda los pesos que pagaste de verdad. La percepción del 30 % no cuenta como gasto, porque es un adelanto de impuesto; si no la podés recuperar y querés verla, cargala como un gasto en pesos y transferí el resto ([ADR-0030](docs/adr/0030-gastos-en-dolares-con-tarjeta.md)).
* **Dashboard en el inicio:** patrimonio de hoy y al cierre de cada mes, ingresos y gastos de cada mes y gasto por categoría, en la moneda de referencia. Cada monto se convierte con la cotización de su día, y lo que no se puede convertir se muestra aparte en vez de inventarse. El período y la cuenta se eligen arriba y quedan en la dirección; cada gráfico tiene su tabla equivalente. La API responde en menos de 300 ms con 50.000 movimientos, y una prueba lo verifica en cada cambio ([ADR-0018](docs/adr/0018-modelo-de-lectura-del-dashboard.md), [ADR-0020](docs/adr/0020-pantalla-del-dashboard.md)).
* **Pesos de hoy:** en el dashboard, los ingresos y gastos de cada mes también se ven ajustados por inflación, en pesos del último mes con IPC publicado. Usa el índice oficial del INDEC, que se guarda la primera vez que se pide. Un mes sin IPC todavía, como el mes en curso, queda vacío en lugar de mostrarse sin ajustar ([ADR-0025](docs/adr/0025-pesos-constantes.md)).
* **Compras en cuotas:** se anota la compra una vez, con el total y la cantidad de cuotas, y cada cuota se vuelve un gasto el día que vence, así cuenta en su mes. El reparto cierra exacto al centavo. Una pantalla muestra cuánto falta pagar y el calendario de cada compra, y se puede cancelar sin tocar lo ya pagado. Al abrir la app se registran las cuotas que vencieron, sin duplicarse ([ADR-0026](docs/adr/0026-compras-en-cuotas.md)).
* **Movimientos recurrentes:** el alquiler, el sueldo o una suscripción se anotan una vez, con su monto y cada cuánto se repiten (semanal, mensual o anual), y se registran solos cada vez que llega la fecha, con el mismo mecanismo que las cuotas. Si el monto aumenta, se cambia y vale desde la próxima vez, sin tocar lo ya registrado ([ADR-0027](docs/adr/0027-movimientos-recurrentes.md)).
* **Presupuestos mensuales por categoría,** en pesos o en dólares. Cada tope muestra cuánto gastaste, cuánto queda y si estás cerca o te pasaste. Lo gastado en otra moneda se convierte con la cotización de su día. Cambiar un tope vale desde el mes en curso: los meses que ya pasaron conservan el que tenían ([ADR-0021](docs/adr/0021-modelo-de-presupuestos.md)).
* **Alertas de presupuesto** cuando un gasto deja una categoría en el 80 % o en el 100 % de su tope: una campana con las que no leíste y un aviso en el momento. Cada umbral avisa una sola vez por mes, y solo el mes en curso. El aviso guarda lo que había al dispararse, aunque después cambie el tope ([ADR-0022](docs/adr/0022-alertas-de-presupuesto.md)).
* **Importar movimientos desde un CSV** del banco. Elegís cómo está escrito (separador, codificación, formato de montos y fechas) y qué columna es cada cosa, con el monto en una columna o en débito y crédito. Antes de guardar ves todo: lo que ya importaste queda afuera, lo que se parece a algo cargado a mano se marca, y una línea que no se entiende se informa en lugar de adivinarse. Reimportar el mismo archivo no duplica nada ([ADR-0023](docs/adr/0023-modelo-de-importacion.md)).
* **Importar el resumen PDF de Banco Macro**, tal como lo baja la app. Débitos y créditos se leen de su columna, y nada entra si las líneas no cierran con el saldo de cada renglón y con los totales del resumen. Un resumen escaneado, de otra moneda o con dos cuentas se rechaza diciendo por qué ([ADR-0023](docs/adr/0023-modelo-de-importacion.md)). El PDF se lee en un proceso aparte con tope de memoria, CPU y tiempo: un archivo armado para inflarse al abrirse no puede tumbar el servidor ([ADR-0031](docs/adr/0031-pdf-en-proceso-aislado.md)).
* **Reglas de categoría al importar:** en la vista previa podés recordar "si dice COTO, es Supermercado", y las próximas importaciones lo aplican solas. Si coinciden dos reglas gana la más específica, y cada categoría propuesta dice qué regla la eligió ([ADR-0024](docs/adr/0024-reglas-de-categoria.md)).
* **Filtros por categoría y por texto**, que se comparten en la dirección. La búsqueda no distingue tildes ni mayúsculas: "panaderia" encuentra "Panadería".
* **Cuenta y sesión** con usuario, contraseña y código de recuperación, sin email ([ADR-0007](docs/adr/0007-autenticacion.md)).
* **Demo sin registrarse:** "Probar la demo", en la pantalla de ingreso, abre una cuenta propia con tres meses de datos inventados: cuentas en pesos y en dólares, gastos, transferencias, una compra en cuotas, recurrentes y un presupuesto con su alerta. Cada visita tiene la suya, se carga por los mismos casos de uso que cualquier dato y se borra sola a las dos horas, con todo lo que tenga. Un aviso fijo dice a qué hora ([ADR-0028](docs/adr/0028-cuenta-demo.md)).
* **Interfaz en español y en inglés**, con modo oscuro y claro.

## Arquitectura

Un monolito modular ([ADR-0001](docs/adr/0001-monolito-modular-fastapi-clean-architecture.md)): un solo despliegue, con módulos que se comunican como si fueran servicios. Cada módulo tiene cuatro capas, y la regla de dependencia la verifica [import-linter](backend/pyproject.toml) en cada cambio, con 25 contratos:

* `domain`: entidades y reglas en Python puro. No importa FastAPI, SQLAlchemy, Pydantic ni httpx.
* `application`: casos de uso y puertos (`Protocol`). Solo conoce al dominio.
* `infrastructure`: repositorios SQLAlchemy y adaptadores a servicios externos.
* `api`: routers FastAPI y esquemas Pydantic.

Un módulo usa a otro solo por su capa de aplicación. Así quedan las dependencias, tal como están en el código:

```mermaid
flowchart LR
  dashboard --> transactions
  dashboard --> rates
  dashboard --> preferences
  dashboard --> inflation
  budgets --> transactions
  budgets --> rates
  budgets --> preferences
  alerts --> budgets
  alerts --> transactions
  imports --> transactions
  demo --> accounts
  demo --> transactions
  demo --> budgets
  transactions --> accounts
  transactions -. "evento: gasto registrado" .-> alerts
  demo -. "implementa el puerto DemoSeeder" .-> auth
```

Las flechas punteadas no son importaciones. Las alertas se enteran de un gasto por un evento de dominio ([ADR-0022](docs/adr/0022-alertas-de-presupuesto.md)), y auth siembra la demo por un puerto que implementa otro módulo: ninguno de los dos conoce al otro. Todos usan el kernel compartido (`Money`, `Currency`, el calendario argentino), que no depende de nadie.

Algunos patrones, donde resuelven un problema concreto:

* **Chain of Responsibility y Decorator** en las cotizaciones: si una fuente no responde contesta la siguiente, y lo respondido se guarda en memoria un rato ([ADR-0016](docs/adr/0016-fuentes-de-cotizaciones.md)). Un enrutador manda cada pedido a su cadena: los dólares por un lado y el Bitcoin por otro ([ADR-0029](docs/adr/0029-precio-del-bitcoin.md)).
* **Strategy** en la importación: CSV configurable y PDF de Banco Macro detrás de la misma interfaz ([ADR-0023](docs/adr/0023-modelo-de-importacion.md)).
* **Specification** en las reglas de categoría: gana la más específica ([ADR-0024](docs/adr/0024-reglas-de-categoria.md)).
* **Unit of Work** por pedido, y operaciones de varias filas en una sola transacción.

En producción ([ADR-0005](docs/adr/0005-hosting-gratuito.md)):

```mermaid
flowchart LR
  navegador["Navegador"] --> worker["Cloudflare Worker<br/>frontend y proxy de /api"]
  worker --> api["Render<br/>API FastAPI en Docker"]
  api --> base[("Neon<br/>PostgreSQL 18")]
  api --> fuentes["Fuentes públicas<br/>dólar, Bitcoin, IPC del INDEC"]
```

El navegador ve un único origen, así que no hace falta CORS y la política de contenido puede quedar en `'self'`. La API solo atiende a quien pasa por el Worker: cada pedido lleva un secreto compartido, y sin él responde 403. Así nadie puede llamar directo a Render, inventar la dirección de origen y esquivar los límites de intentos ([ADR-0032](docs/adr/0032-secreto-entre-worker-y-api.md)).

**Dinero.** Nunca `float`: `Decimal` en Python, `NUMERIC` en PostgreSQL y strings en JSON. El frontend no hace cuentas con montos, solo los formatea. Las conversiones no se guardan: se calculan al consultar, con la cotización inmutable de cada día, y cada una informa la tasa, el tipo de dólar, la fuente y la fecha que usó ([ADR-0017](docs/adr/0017-conversion-al-consultar.md)).

## Calidad, medida

| Qué | Cuánto | Cómo se verifica |
| --- | --- | --- |
| Tests del backend | 1165: dominio, casos de uso, API e integración contra PostgreSQL | En cada cambio, en la CI |
| Cobertura del backend | 98 % | La CI falla por debajo del mínimo |
| Tests del frontend | 364, con axe-core en las pantallas | En cada cambio, en la CI |
| Pruebas de extremo a extremo | 42 en Chromium, a 360 px y en los dos idiomas | Contra el build de producción ([ADR-0013](docs/adr/0013-pruebas-de-extremo-a-extremo.md)) |
| Flujos críticos | 3, sin nada simulado: registrarse y volver a entrar, abrir una cuenta y registrar un gasto, y probar la demo | Contra el entorno completo de `docker compose`, en cada cambio |
| Dashboard con 50.000 movimientos | p95 de 123 ms, con un límite de 300 ms | Una prueba lo mide en cada cambio y deja el número en el resumen de la corrida |
| Una cuenta demo | 127 filas y 34 kB | Una prueba falla si pasa de 100 kB |
| Acceso a datos ajenos | Ningún endpoint lo permite | Una prueba recorre todas las rutas: sin sesión dan 401, con recursos de otra persona dan 404 |
| Dependencias e imágenes | Auditadas todos los días | Si aparece una vulnerabilidad, se abre un issue solo |
| Análisis estático de seguridad | CodeQL sobre Python, TypeScript y los workflows, con las reglas extendidas de seguridad | En cada cambio y una vez por semana; los hallazgos van a la pestaña Security |
| Decisiones | 32 ADR, con alternativas y costos | [docs/adr](docs/adr/README.md) |

Los números de tiempo son de una corrida local; los de la CI quedan en cada corrida.

## Qué falta

Las fases del roadmap están completas. Lo que podría venir después está en el [roadmap](docs/roadmap.md).

## Stack

* **Backend:** Python 3.15, FastAPI, SQLAlchemy 2 con mapeo imperativo, Alembic, Pydantic v2, PostgreSQL 18, uv.
* **Frontend:** React 19, TypeScript, Vite, TanStack Query, React Aria, Chart.js, react-i18next.
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

La API corre en una instancia gratuita de Render (0,1 CPU, 512 MB de RAM) que se suspende tras 15 minutos sin tráfico: el primer pedido después de una pausa puede tardar alrededor de un minuto. Por eso los números de rendimiento se miden en la CI y no contra producción.

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

Los tres flujos críticos van aparte, porque necesitan el entorno completo arriba y
no simulan nada: nginx, la API y PostgreSQL de verdad. La CI los corre en cada
cambio; a mano, con el compose levantado:

```bash
cd frontend && npm run e2e:flujos   # otra dirección: RINDE_FLUJOS_URL
```

Cada corrida registra dos cuentas y abre una demo, y el registro y la demo tienen
límite por dirección de origen: repetirlas muchas veces en una hora termina en
"demasiados intentos", que es la protección funcionando.

Para omitir las de maquetado a sabiendas: `RINDE_SKIP_E2E=1`. Usan el puerto 4173, el de
`vite preview`. Si otro proyecto lo tiene ocupado, el arranque falla en lugar de
probar contra esa aplicación; se cambia con `RINDE_E2E_PORT=4199`.

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
decisión 3). Los comandos están en `scripts/check-dependencies.sh`, que usan la CI
y la auditoría diaria (`.github/workflows/auditoria.yml`). La auditoría corre
todos los días sobre `main`; si encuentra algo abre un issue, y lo cierra cuando
todo vuelve a estar en verde.

Un aviso del frontend sin versión corregida deja la CI en rojo sin ninguna acción
posible, y `npm audit` no permite ignorar uno solo. Esos avisos se aceptan de a
uno en `frontend/audit-exceptions.json`, con el motivo y una fecha de revisión.
El chequeo falla si aparece un aviso que no está en la lista, si una excepción
vence o si una ya no hace falta. Hoy no hay ninguna vigente.

Cuando una vulnerabilidad está en una dependencia transitiva y el paquete que la
trae todavía no admite la versión corregida, se fuerza con `overrides` en
`frontend/package.json`, acotado al rango vulnerable. Overrides vigentes:

* `minimatch` 10.x a `^11.0.5` por
  [GHSA-g3hv-75wg-m249](https://github.com/advisories/GHSA-g3hv-75wg-m249).
  ESLint ya pide `^11`; typescript-eslint todavía pide `^10`, y el lint, los
  tipos y los tests pasan con la 11. Se quita cuando typescript-eslint acepte
  `^11`.

Los PR de Dependabot que suben una versión de parche se integran solos cuando la
CI da verde ([ADR-0015](docs/adr/0015-auto-merge-de-dependabot.md)). Quedan
afuera las actualizaciones menores y mayores, las de acciones de GitHub y las
de paquetes que cambiaron de mantenedor: esas se revisan a mano. El auto-merge
usa una GitHub App, cuyo client ID y clave privada viven como secretos de
Dependabot (`AUTOMERGE_APP_CLIENT_ID` y `AUTOMERGE_APP_PRIVATE_KEY`).
