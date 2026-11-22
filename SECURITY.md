# Política de seguridad

Rinde guarda las finanzas personales de cada persona. Si encontrás una vulnerabilidad, gracias por avisar en privado: así se puede corregir antes de que alguien la aproveche.

## Cómo reportar

Usá el reporte privado de vulnerabilidades de GitHub:

**[Reportar una vulnerabilidad](https://github.com/MerAtim/Rinde/security/advisories/new)**

El reporte solo lo ven quienes mantienen el repositorio. No abras un issue público, un pull request ni una discusión sobre una vulnerabilidad que todavía no está corregida.

Para que se pueda reproducir, incluí si podés:

* qué componente está afectado (API, frontend, Worker, CI) y en qué versión o commit;
* los pasos para reproducirla, con los pedidos y las respuestas;
* qué puede lograr quien la aproveche;
* si la conocés, una forma de corregirla.

## Qué esperar

| Paso | Plazo |
| --- | --- |
| Confirmación de que el reporte llegó | 5 días hábiles |
| Evaluación inicial, con la gravedad según CVSS 4.0 | 10 días hábiles |
| Corrección de una vulnerabilidad crítica o alta | 30 días corridos |
| Corrección de una media o baja | 90 días corridos |

Rinde lo mantiene una sola persona, así que los plazos son los que se pueden cumplir. Si una corrección se demora, se avisa en el mismo reporte por qué y para cuándo.

Cuando la corrección está en producción, se publica un aviso de seguridad en GitHub con los detalles y, si querés, con tu nombre. La publicación se coordina con quien reportó; si no se llega a un acuerdo, el aviso sale a los 90 días del reporte.

No hay recompensa económica.

## Versiones con soporte

Solo la versión en producción, que es la de la rama `main`. No hay versiones anteriores mantenidas.

## Alcance

Dentro del alcance:

* la API (`backend/`), el frontend y el Worker de Cloudflare (`frontend/`);
* los workflows de GitHub Actions y los scripts del repositorio;
* la configuración de despliegue que está en el repositorio.

Fuera del alcance:

* vulnerabilidades de Cloudflare, Render, Neon o GitHub: se reportan a cada proveedor;
* denegación de servicio por volumen, y cualquier prueba que degrade el servicio para otras personas;
* ingeniería social o ataques físicos;
* resultados de escáneres automáticos sin una forma concreta de aprovecharlos;
* que falte una cabecera o una opción que no tenga un efecto demostrable.

## Reglas para probar

Se considera de buena fe, y no se van a iniciar acciones contra quien la haga, cualquier investigación que cumpla estas reglas:

* Probá solo con tus propias cuentas o con la demo ("Probar la demo", sin registrarse). Nunca accedas, modifiques ni borres datos de otra persona.
* Si por accidente llegás a datos ajenos, frená ahí, no los guardes y contalo en el reporte.
* Nada de pruebas que degraden el servicio: sin ataques de volumen y con escaneos automáticos a un ritmo razonable.
* No publiques la vulnerabilidad antes de que esté corregida o de que pasen los 90 días.

## Cómo se protege Rinde

El [modelo de amenazas](docs/modelo-de-amenazas.md) describe qué se protege, de quién, con qué controles y qué riesgos se aceptaron. Las decisiones de diseño están en los [ADR](docs/adr/README.md).
