# ADR-0015: Integración automática de parches de Dependabot con una GitHub App

* **Estado:** Aceptado
* **Fecha:** 2026-11-09

## Contexto

Dependabot abre por semana varios PR de actualización, y además los de seguridad apenas sale un aviso. Hasta ahora cada uno se integraba a mano. En noviembre de 2026 se juntaron diez PR abiertos a la vez; una vulnerabilidad nueva en `main` los dejó a todos en rojo y ninguno podía entrar solo (ver #80). Cuanto más tiempo queda abierto un PR de dependencias, más se atrasa `main` y más grande es el salto cuando finalmente se actualiza.

Hechos verificados:

* La regla `Proteger main` exige siete chequeos de la CI, que la rama esté al día con `main` (`strict_required_status_checks_policy`) y solo admite integrar con rebase. No tiene excepciones (`bypass_actors` vacío).
* Un push hecho con `GITHUB_TOKEN` no dispara workflows nuevos, salvo `workflow_dispatch` y `repository_dispatch` (documentación de GitHub, "Triggering a workflow from a workflow"). CI y CD corren en `push` a `main`.
* Los workflows que dispara Dependabot en `pull_request` solo ven los secretos de Dependabot, no los de Actions.
* Modificar archivos de `.github/workflows` exige el permiso `workflows`, que un token de App no tiene si no se le da.

Restricciones: seguro por defecto, permisos mínimos y nada de `main` sin CI en verde.

## Opciones consideradas

### Opción A: seguir integrando todo a mano
* Pros: una persona mira cada cambio. No hace falta ninguna credencial nueva.
* Contras: los PR se acumulan y se repite lo de noviembre. Revisar a mano un parche con la CI en verde aporta poco: casi nunca se lee el código de la dependencia.

### Opción B: auto-merge con `GITHUB_TOKEN`
* Pros: es el ejemplo de la documentación de GitHub y no necesita credenciales nuevas.
* Contras: el push a `main` lo hace `GITHUB_TOKEN`, así que no corren ni la CI de `main` ni el despliegue. Producción queda atrás de `main` sin que nadie lo note, hasta que se integre otra cosa a mano.

### Opción C: auto-merge con un token personal (PAT)
* Pros: dispara los workflows. Se arma en un minuto.
* Contras: dura meses y está atado a la cuenta de una persona. Si se filtra, sirve hasta que venza o se revoque. Hay que renovarlo a mano, y cuando vence el auto-merge deja de andar sin avisar.

### Opción D: auto-merge con una GitHub App propia
* Pros: dispara los workflows. Cada token dura una hora, se pide en cada corrida con solo `contents` y `pull-requests` de escritura, y queda acotado a este repositorio. No está atado a una persona.
* Contras: hay que crear la App y guardar dos secretos. Es una pieza más que mantener.

## Decisión

Opción D. Es la única que deja `main` con CI y despliegue en cada commit sin una credencial de larga duración.

Alcance del auto-merge, de lo más seguro a lo menos:

* Solo actualizaciones de **parche** (`semver-patch`). Las menores y mayores siguen pasando por una persona.
* Nunca en el ecosistema **`github_actions`**: cambian la CI misma, y la App necesitaría el permiso `workflows`.
* Nunca si cambió quien publica el paquete (`maintainer-changes`), que es la señal típica de un ataque a la cadena de suministro.
* Solo si el autor del PR y quien disparó el evento son Dependabot. Si una persona pushea a la rama, se revisa a mano.

El workflow no integra nada: solo activa el auto-merge. GitHub integra cuando se cumple la regla de `main`.

## Consecuencias

* Positivas: los parches entran solos, con la misma CI que cualquier PR, y cada uno se despliega. Los PR que quedan abiertos son los que de verdad piden una decisión.
* Negativas / costos aceptados:
  * Entra código de terceros a producción sin que una persona lo mire. La garantía pasa a ser la CI, así que una dependencia con un cambio malicioso que pase los tests llega a producción.
  * Hay que mantener una GitHub App y su clave privada.
  * Las imágenes Docker fijadas por digest no tienen versión semántica, así que no entran en el auto-merge y siguen siendo manuales.
* Riesgos y cómo se mitigan:
  * **Clave privada filtrada:** permite pedir tokens con permisos de escritura en este repositorio. Solo vive como secreto de Dependabot, la App se instala solo en este repositorio, y se rota desde la configuración de la App. La regla de `main` sigue exigiendo PR y CI aunque el token sea válido.
  * **Paquete comprometido en un parche:** `maintainer-changes` frena el caso más común. Los escaneos de la CI (`pip-audit`, `npm audit`, Trivy, gitleaks) corren antes de integrar.
  * **App mal configurada:** si faltan los secretos, el paso falla y el PR queda abierto para integrarlo a mano. Nunca se integra sin chequeos.

## Supuestos y datos faltantes

* Se asume que los mantenedores respetan el versionado semántico, o sea que un parche no rompe la API. Los tests lo controlan.
* Se asume que la cobertura de tests (mínimo vigente en la CI) alcanza para detectar un parche que rompa algo. Si un parche roto llega a producción, se revisa este ADR.

## Referencias

* [Automating Dependabot with GitHub Actions](https://docs.github.com/en/code-security/dependabot/working-with-dependabot/automating-dependabot-with-github-actions)
* [Triggering a workflow from a workflow](https://docs.github.com/en/actions/using-workflows/triggering-a-workflow#triggering-a-workflow-from-a-workflow)
* [Making authenticated API requests with a GitHub App in a GitHub Actions workflow](https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/making-authenticated-api-requests-with-a-github-app-in-a-github-actions-workflow)
* [ADR-0004](0004-estrategia-de-ramas.md): estrategia de ramas e integración por rebase.
* [ADR-0012](0012-chequeos-locales-y-en-ci.md): chequeos locales y en CI.
