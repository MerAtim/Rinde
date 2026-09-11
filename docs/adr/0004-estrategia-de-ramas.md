# ADR-0004: Estrategia de ramas

* **Estado:** Aceptado
* **Fecha:** 2026-09-11

## Contexto

El proyecto tiene una sola desarrolladora, CI en cada cambio y la intención de desplegar automáticamente al integrar en `main`. Se necesita un flujo que deje evidencia revisable de cada cambio (PR con CI en verde) sin burocracia innecesaria. Los nombres de las ramas van en español.

## Opciones consideradas

### Opción A: GitHub Flow (`main` más ramas cortas integradas por PR)
* Pros: una sola rama permanente; compatible con despliegue continuo; cada cambio queda en un PR con la CI en verde; historial lineal fácil de auditar.
* Contras: `main` tiene que estar siempre desplegable; el trabajo grande obliga a partirse en PR chicos o a usar feature flags.

### Opción B: Git Flow (`main`, `develop`, `release/*`, `hotfix/*`, `feature/*`)
* Pros: modelo conocido; útil para software con varias versiones mantenidas en paralelo.
* Contras: ramas de larga vida, integraciones tardías y merges complejos. Su propio autor agregó en 2020 una nota recomendando un flujo más simple, como GitHub Flow, para aplicaciones web de entrega continua.

### Opción C: trunk-based puro (commits directos a `main`)
* Pros: máximo flujo, sin ramas.
* Contras: sin PR no queda registro de revisión ni corre la CI antes de integrar; choca con la protección de `main`.

## Decisión

Opción A, con esta convención de nombres:

```
<tipo>/<número de issue opcional>-<descripción-en-kebab-case>
```

| Prefijo | Uso | Tipo de commit habitual |
|---|---|---|
| `funcionalidad/` | funcionalidad nueva | `feat` |
| `correccion/` | corrección de un error | `fix` |
| `refactor/` | cambio interno sin cambio de comportamiento | `refactor` |
| `rendimiento/` | mejora de rendimiento | `perf` |
| `pruebas/` | solo tests | `test` |
| `documentacion/` | solo documentación | `docs` |
| `ci/` | pipeline e integración continua | `ci` |
| `mantenimiento/` | dependencias, build, tareas varias | `build`, `chore` |

Reglas:

* Nombres en español, **sin tildes ni ñ**: las ramas viajan en URLs, comandos y herramientas que no siempre manejan Unicode. Las tildes sí van en commits y PR.
* Solo minúsculas, números y guiones; máximo 60 caracteres. Ejemplo: `funcionalidad/12-importacion-csv`.
* Vida corta: idealmente menos de tres días. Se borra automáticamente al integrar.
* Integración solo por rebase, para conservar los commits atómicos con historial lineal.
* Las ramas de bots (`dependabot/*`) quedan exentas de la convención.

Cumplimiento automático: hook local `pre-push` y job de CI `Nombre de rama` con el mismo script (`scripts/check-branch-name.sh`); el ruleset de GitHub exige PR y CI en verde para `main`.

## Consecuencias

* Positivas: cada cambio en `main` tiene un PR asociado con la CI en verde; el historial es lineal y conserva los commits atómicos.
* Negativas / costos aceptados: hasta los cambios mínimos requieren rama y PR; los commits de Dependabot se integran con su mensaje en inglés, que no pasa la convención y se exime por autor.
* Riesgos: ramas que se estiran semanas. Mitigación: partir el trabajo en PR chicos alineados con el roadmap.

## Referencias

* Vincent Driessen, "A successful Git branching model", nota de reflexión de marzo de 2020.
* GitHub Docs, "GitHub flow".
