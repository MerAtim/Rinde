# ADR-0019: El job de frontend corre en la imagen oficial de Playwright

* **Estado:** Aceptado
* **Fecha:** 2026-11-11

## Contexto

Las pruebas de extremo a extremo (ADR-0013) necesitan Chromium y sus bibliotecas del sistema. Hasta ahora, cada corrida de CI las instalaba con `npx playwright install --with-deps chromium`. Ese comando baja el navegador del CDN de Playwright y las bibliotecas con `apt`, desde los mirrors de Ubuntu.

Hecho verificado: el 2026-11-11 el job de frontend del PR #89 falló tres veces seguidas en ese paso, sin relación con el código.
* En dos corridas, el runner no pudo resolver `azure.archive.ubuntu.com`.
* En la tercera no pudo bajar paquetes de `security.ubuntu.com`.

Los pasos anteriores pasaron las tres veces: formato, estilo, tipos, pruebas y build. Como el check es obligatorio para `main`, una caída ajena bloqueaba cualquier integración, incluidos los parches de Dependabot (ADR-0015).

## Opciones consideradas

### Opción A: dejarlo como está y reintentar cuando falla
* Pros: no cambia nada.
* Contras:
  * Cada corte de los mirrors bloquea `main` hasta que alguien reintente.
  * El auto-merge de Dependabot se traba en silencio.
  * Sigue bajando cientos de MB en cada corrida.

### Opción B: reintentar el paso de instalación varias veces
* Pros: un cambio chico.
* Contras: no sirve si el corte dura más que los reintentos, como el del 2026-11-11, que duró más de media hora. Además agrega minutos a cada corrida fallida.

### Opción C: correr el job dentro de la imagen oficial `mcr.microsoft.com/playwright`
* Pros:
  * Navegador y bibliotecas ya vienen en la imagen: no queda ningún `apt` en la CI de frontend.
  * Es lo que recomienda la documentación de Playwright para GitHub Actions.
  * Fijada por digest, cada corrida usa exactamente la misma imagen.
* Contras:
  * La versión de la imagen tiene que coincidir con la de `@playwright/test`.
  * Bajar la imagen depende del registro de Microsoft, que es otro tercero.

## Decisión

Opción C. Saca de la CI la dependencia que falló, `apt` contra los mirrors de Ubuntu, y deja una sola descarga fijada y verificable.

* La imagen se fija por versión y por digest, con el mismo criterio que las acciones de terceros.
* El job corre con `--user 1001`, el usuario del runner, para que el espacio de trabajo tenga el mismo dueño. Es la configuración de la documentación de Playwright.
* Un paso compara la versión instalada de `@playwright/test` con la de la imagen. Si difieren, corta con un mensaje que dice qué actualizar, en vez de fallar más adelante porque no encuentra el navegador.
* Todo el job corre en el contenedor, no solo las pruebas de navegador: `container` aplica a un job entero, y separar las pruebas en otro job cambiaría el nombre de un check obligatorio de `main`.

## Consecuencias

* Positivas:
  * Un corte de los mirrors de Ubuntu ya no deja la CI en rojo.
  * Cada corrida baja una imagen ya armada en lugar de instalar paquetes: menos piezas que pueden fallar.
* Negativas / costos aceptados:
  * Cuando Dependabot actualice `@playwright/test`, el paso de comparación falla. Hay que subir a mano la versión y el digest de la imagen en `ci.yml`, y ese PR de Dependabot no se integra solo.
  * El registro de Microsoft pasa a ser un tercero del que depende la CI de frontend. Antes lo era el CDN de Playwright, que es del mismo proveedor.
* Riesgos y cómo se mitigan:
  * **El digest fijado queda viejo y la imagen trae vulnerabilidades del sistema.** Solo corre en CI, contra el código del propio repositorio y sin secretos en el job. Se actualiza junto con `@playwright/test`.

## Supuestos y datos faltantes

* Se supone que el registro de Microsoft es más estable que los mirrors de Ubuntu desde los runners de GitHub. No hay datos propios todavía: si la descarga de la imagen fallara con frecuencia, se reevalúa con un registro espejo.
* No se verificó si Dependabot puede actualizar la imagen de `container` en un workflow. Mientras no lo haga, la actualización es manual, y el paso de comparación lo hace visible.

## Referencias

* [ADR-0013](0013-pruebas-de-extremo-a-extremo.md): pruebas de extremo a extremo.
* [ADR-0015](0015-auto-merge-de-dependabot.md): auto-merge de Dependabot.
* Documentación de Playwright, "Continuous Integration", sección GitHub Actions con contenedor.
* PR #89, corridas 43038080346 y 43040178215: los fallos de `apt` del 2026-11-11.
