# ADR-0012: Chequeos locales y su relación con la CI

* **Estado:** Aceptado
* **Fecha:** 2026-09-18

## Contexto

La regla del proyecto es que lo que no corre en la CI no está garantizado, y el roadmap pedía "pre-commit con los mismos chequeos que la CI". Hasta ahora había dos hooks locales (`commit-msg` y `pre-push`) que solo validaban el mensaje del commit y el nombre de la rama: ningún chequeo de código corría antes de pushear.

El costo de esa falta se vio en el PR de movimientos. Dos chequeos de la CI fallaban y nadie se enteró hasta que el PR estuvo abierto:

* `ruff format --check`, que es distinto de `ruff check`: uno acomoda el formato y el otro busca problemas. La verificación local corría el segundo y daba por hecho el primero.
* `alembic check`, que compara la migración con el modelo. Nunca se había corrido fuera de la CI.

El problema de fondo no fueron los dos errores, sino que el bucle local y la CI no corrían lo mismo y nadie podía notarlo.

Restricciones vigentes:

* Todo se automatiza en GitHub Actions y `main` solo entra por PR con CI en verde.
* Seguro por defecto: se deniega y se permite por excepción explícita.
* La CI completa tarda minutos e incluye cosas que una máquina de desarrollo no puede replicar: construcción de imágenes, escaneo con Trivy e instalación de gitleaks fijada por checksum.

## Decisiones

### 1. Un solo origen para cada chequeo, usado por los hooks y por la CI

Los chequeos de código viven en tres scripts (`scripts/check-backend.sh`, `scripts/check-frontend.sh`, `scripts/check-contract.sh`), que aceptan el nombre del chequeo o `all`. El hook `pre-push` los ejecuta con `all` y cada paso de la CI ejecuta uno por nombre.

* **Alternativa descartada:** que la CI siga escribiendo los comandos en su YAML y los hooks los repitan. Es lo que había, y es exactamente lo que permitió que divergieran sin que se notara.
* **Alternativa descartada:** que la CI ejecute un solo paso con `all`. Se pierde el detalle de qué chequeo falló en la interfaz de GitHub, que es lo primero que se mira cuando un PR se pone en rojo.
* **Costo aceptado:** un salto de indirección. Quien lee el YAML ya no ve el comando, tiene que abrir el script. Se compensa con un paso por chequeo, que conserva el nombre y el detalle.

### 2. El hook `pre-commit` es rápido; el `pre-push` es completo

`pre-commit` corre en segundos y solo sobre los archivos que cambiaron: formato, estilo y un freno para los archivos de entorno. `pre-push` corre todos los chequeos de código, enteros.

* **Alternativa descartada:** correr la CI completa en cada commit, que es lo que pedía el roadmap al pie de la letra. Un commit pasaría de un segundo a más de un minuto. La consecuencia conocida es que se termina usando `--no-verify` por costumbre, y entonces el hook no protege nada. Un chequeo que la gente saltea es peor que no tenerlo, porque da una sensación de cobertura que no existe.
* **Por qué sigue valiendo la garantía:** lo que importa es que nada salga de la máquina sin haber pasado los chequeos, y eso lo asegura `pre-push`. Los commits intermedios de una rama en construcción no necesitan estar todos verdes; el rango completo se valida antes del push y otra vez en la CI.
* **Costo aceptado y conocido:** `pre-commit` ejecuta las herramientas sobre los archivos del directorio de trabajo, no sobre la versión exacta que quedó en el índice. Si se commitea una parte de un archivo, se revisa el archivo entero. Arreglarlo requiere guardar y restaurar lo no indexado, que puede perder trabajo si algo sale mal a mitad de camino. Se prefiere la limitación documentada al riesgo.

### 3. Los chequeos que dependen del tiempo, y no del código, se quedan en la CI

`pip-audit`, `npm audit`, el escaneo de imágenes con Trivy, el de secretos con gitleaks y el levantado del entorno completo siguen corriendo solo en la CI.

* **Motivo:** su resultado cambia sin que cambie el código. Una vulnerabilidad publicada hoy pone en rojo un commit que ayer estaba verde. Un chequeo así no sirve como puerta local, porque bloquearía un push por algo que quien pushea no introdujo ni puede arreglar en ese momento. En la CI sí corresponde: ahí se ve y se atiende como lo que es, un aviso de la cadena de suministro.
* **Consecuencia:** "los mismos chequeos que la CI" es cierto para los chequeos de código, no para los de dependencias e imágenes. Queda escrito acá para que no se lea como un olvido.

### 4. Sin base de datos, los chequeos que la necesitan se omiten y se dice cuáles

Varios chequeos necesitan un PostgreSQL de verdad: `alembic check`, que compara el modelo con la base, y los tests de integración. Si falta `RINDE_DATABASE_URL`, el script falla y explica cómo levantar la base de tests, declarada en `docker-compose.yml` bajo el perfil `test`. Se puede omitir a sabiendas con `RINDE_SKIP_DB_CHECKS=1`.

* **Alternativa descartada:** omitirlo en silencio cuando no hay base. Es justo lo que dejó pasar la migración desalineada: un verde que no significaba nada.
* **Alternativa descartada:** fallar sin escapatoria. Quien no tenga Docker levantado en ese momento no podría pushear, y el camino de salida sería `--no-verify`, que apaga todos los chequeos y no solo este.
* **Nota operativa:** la base se publica en `127.0.0.1`. En Windows hay que usar esa dirección y no `localhost`, que resuelve primero a IPv6: contra un puerto publicado solo en IPv4 la conexión no falla, se cuelga. El script lo dice en su mensaje de error.

#### Sin base, la cobertura no se compara contra el mínimo

Los tests de integración son los que ejercitan los repositorios. Sin base no corren, y la cobertura medida deja de ser comparable: en el momento de escribir esto, 95,96 % con base y 88,75 % sin ella, contra un mínimo de 90 %.

Esto no se había previsto cuando se escribió la decisión, y se descubrió usando la salida: con `RINDE_SKIP_DB_CHECKS=1` el chequeo de migraciones se omitía como corresponde, pero los tests seguían comparando la cobertura contra un mínimo que ya no podían alcanzar. El push se rechazaba con un "cobertura insuficiente" que no decía nada sobre la causa, y la salida explícita servía solo por casualidad, mientras el número se mantuviera arriba del umbral.

Ahora, sin base, los tests de integración se descartan con su marca y **la cobertura no se compara contra el mínimo**.

* **Por qué no se baja el umbral:** bajarlo sería apagar la alarma. No comparar es otra cosa: es no afirmar un número que no se midió.
* **Alternativa descartada:** dejar que falle como antes. Un chequeo que rechaza un push por un motivo que no se puede resolver sin Docker, y que además no nombra la causa real, empuja a `--no-verify`.
* **Costo aceptado:** en ese modo, la cobertura no se verifica en la máquina. La CI siempre tiene base y siempre la compara, así que la garantía sigue estando donde el proyecto dice que está.

## Consecuencias

* Positivas: un chequeo nuevo entra en local y en la CI al mismo tiempo, porque es el mismo script. Los dos errores que motivaron este ADR se habrían frenado antes de abrir el PR. Los tests de integración dejan de depender de un contenedor levantado a mano y pasan a salir del repositorio.
* Negativas / costos aceptados: el YAML de la CI ya no muestra el comando; `pre-commit` revisa archivos completos y no el índice exacto; los chequeos de dependencias siguen siendo solo de CI; sin base, la cobertura no se mide en la máquina.
* Riesgos: que `pre-push` se vuelva lento a medida que crezcan los tests y empiece a saltearse. Mitigación prevista: si pasa de un par de minutos, mover los tests más lentos a una marca aparte y dejarlos solo en la CI, con este ADR actualizado.

## Referencias

* [ADR-0004: Estrategia de ramas](0004-estrategia-de-ramas.md)
* https://pre-commit.com/#pre-commit-during-push
* https://docs.github.com/en/actions/using-workflows/about-workflows
