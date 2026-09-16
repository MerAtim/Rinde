# ADR-0008: Nombre del proyecto y elemento firma

* **Estado:** Aceptado
* **Fecha:** 2026-09-16

## Contexto

El proyecto se llama Rinde. El nombre viene de la pregunta que da origen al producto: "¿me rinde el sueldo?". Sobre esa idea se construyó la identidad: el titular de la portada, el color aqua reservado (`--rinde-signature`) y un elemento firma previsto para la fase 4, el indicador "¿Te rinde?".

En septiembre de 2026, ya desplegada la fase 1, se detectó que existe otra aplicación llamada **Rinde**, en español y de la misma región, dirigida a conductores de Uber, DiDi y Cabify. Calcula si un viaje conviene y muestra un cartel flotante con tres estados: "Rinde", "Casi Rinde" y "No Rinde".

Hechos relevados:

* La coincidencia es de nombre y, además, de vocabulario: el veredicto "rinde / no rinde" es el mecanismo central de esa aplicación.
* Los mercados son distintos: finanzas personales y de inversión frente a decisión por viaje para trabajo de plataforma.
* "Rinde" es una forma conjugada del verbo rendir. Es una palabra común y descriptiva, de las que resultan difíciles de registrar como marca y difíciles de defender en exclusiva.
* El proyecto no es comercial, no tiene dominio propio y hoy se sirve en un subdominio de Cloudflare.
* El nombre está presente en todas las capas: el paquete Python `rinde`, el proyecto de Docker Compose, los tokens CSS `--rinde-*`, las clases de los módulos CSS, el subdominio y los ADR anteriores.

## Opciones consideradas

### Opción A: mantener el nombre y no registrar nada
* Pros: costo cero.
* Contras: la coincidencia queda sin documentar. Ante una auditoría o una entrevista, la pregunta "¿verificaron el nombre?" no tiene respuesta. El solapamiento del vocabulario del indicador sigue en pie.

### Opción B: renombrar el proyecto
* Pros: elimina toda ambigüedad futura.
* Contras: el nombre atraviesa backend, frontend, infraestructura, despliegue y documentación. El costo es alto y desproporcionado frente a un riesgo legal que hoy es bajo, tratándose de una palabra descriptiva, un proyecto no comercial y mercados distintos.

### Opción C: mantener el nombre, apartar el vocabulario del indicador y dejar registrado el análisis
* Pros: conserva la identidad ya construida; elimina la parte del solapamiento que sí es evitable y todavía no cuesta nada, porque el indicador no está construido; deja por escrito el porqué y el momento de revisarlo.
* Contras: la coincidencia de nombre persiste, con su costo de descubrimiento en buscadores.

## Decisión

**Opción C.**

1. **El proyecto sigue llamándose Rinde.** El riesgo legal actual es bajo y el costo de renombrar es alto. La decisión se revisa en el disparador definido más abajo, no antes.
2. **El titular "¿Me rinde el sueldo?" se conserva.** Es una pregunta completa sobre el sueldo del mes, no una etiqueta de veredicto. No se confunde con el mecanismo de la otra aplicación.
3. **El elemento firma deja de llamarse "¿Te rinde?" y pasa a llamarse "Días cubiertos".** Es exactamente lo que el indicador muestra: las casillas de los días del mes que el sueldo alcanza a cubrir. El nombre describe la medición en lugar de emitir un veredicto, que es justamente donde estaba el solapamiento.
4. **Queda prohibido el vocabulario de veredicto de tres estados** del tipo "rinde / casi rinde / no rinde" en la interfaz, en cualquiera de los dos idiomas.
5. El aqua `--rinde-signature` sigue reservado para ese único elemento, ahora bajo su nombre nuevo.

### Disparador de revisión

Esta decisión se vuelve a evaluar **antes de comprar un dominio propio o de cualquier uso comercial**, lo que ocurra primero. En ese momento corresponde una búsqueda de antecedentes en el registro de marcas antes de gastar dinero en el nombre.

## Consecuencias

* Positivas: la identidad construida no se tira; la parte evitable del solapamiento se elimina cuando todavía es gratis; la decisión queda justificada ante un auditor y con un momento de revisión explícito.
* Negativas / costos aceptados: quien busque "Rinde" en un buscador va a encontrar antes la otra aplicación. Se acepta mientras el proyecto no sea comercial.
* Riesgos: que la otra aplicación registre la marca y crezca en la misma región. Mitigación: el disparador de revisión actúa antes de que el proyecto invierta dinero o reputación en el nombre.

## Referencias

* https://rutarentable.app
* https://donuberto.com
* https://uddi-app.com
* [ADR-0006: Sistema de diseño propio sobre Material 3](0006-sistema-de-diseno.md)
