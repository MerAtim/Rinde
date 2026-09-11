# Sistema de diseño de Rinde

Material Design 3 como gramática, con voz propia. Decisión y alternativas en [ADR-0006](adr/0006-sistema-de-diseno.md). Los valores viven en `frontend/src/shared/design/tokens.css`; este documento explica el porqué.

## Principios

1. **Primero el número, después el adorno.** La pregunta del usuario es "¿cuánto?": los montos llevan la tipografía más fuerte y el mejor lugar de cada pantalla.
2. **Profundidad por tono, no por brillo.** En oscuro las sombras casi no se ven: cada capa sube un escalón de claridad (elevación tonal) y la sombra acompaña.
3. **El color tiene que significar algo.** El aqua marca la acción principal y el foco; verde hoja, coral y ámbar hablan de ingreso, gasto y alerta. Todo lo demás es neutro.
4. **Nada se mueve sin una causa.** El movimiento orienta, confirma o conecta. Con "reducir movimiento" activado, todo es instantáneo.

## Color

### Semilla y esquema

* Semilla: `#33D6C4` (aqua cian). Esquema: **Tonal Spot** de Material You.
* Se descartaron Fidelity (`#5BF3E0`, aqua neón que cae en el cliché "fondo oscuro con un solo neón") y Vibrant (`#00DECB`, demasiado saturado).
* El aqua intenso de la semilla se reserva para un único elemento firma: el indicador "¿Te rinde?". Nunca en botones ni texto.

### Superficies (oscuro por defecto)

| Token | Oscuro | Claro | Uso |
|---|---|---|---|
| `surface-container-lowest` | `#0B0D11` | `#E3EAE7` | Zonas hundidas |
| `background` / `surface` | `#0F1115` | `#EDF3F1` | Lienzo |
| `surface-container-low` | `#13161B` | `#F4FBF8` | Rail, barras fijas |
| `surface-container` | `#171A21` | `#FFFFFF` | Cards, listas |
| `surface-container-high` | `#20252D` | `#FFFFFF` | Destacados, diálogos |
| `surface-container-highest` | `#29303A` | `#E9EFED` | Menús, tooltips |

### Roles de marca (derivados, verificados por test)

| Rol | Oscuro | Claro |
|---|---|---|
| `primary` / `on-primary` | `#82D5C9` / `#003732` | `#006A60` / `#FFFFFF` |
| `primary-container` / `on-primary-container` | `#005048` / `#9EF2E4` | `#9EF2E4` / `#005048` |
| `secondary-container` / `on-secondary-container` | `#334B47` / `#CCE8E2` | `#CCE8E2` / `#334B47` |

### Semánticos

| Significado | Semilla | Texto oscuro | Texto claro | Siempre acompañado de |
|---|---|---|---|---|
| Ingreso | `#90DA4F` verde hoja | `#90DA4F` | `#386B00` | signo + y flecha ↗ |
| Gasto | `#FF6B5B` coral | `#FFB4AA` | `#AE3026` | signo − y flecha ↙ |
| Alerta | `#F5B83D` ámbar | `#FABC41` | `#7C5800` | ícono de advertencia |
| Error | rojo de Material | `#FFB4AB` | `#BA1A1A` | ícono y mensaje con salida |

**Lo que cambió después de medir.** El primer verde de ingreso (esmeralda `#57DF8D`) quedaba a 3,8 de distancia OKLab del coral bajo deuteranopía (mínimo 8) y a 10,4 del aqua de marca con visión normal (mínimo 15). El verde hoja sube la distancia con el coral a 8,5 y se aleja del aqua. Aun así, **ningún monto depende solo del color** (WCAG 1.4.1).

Las variaciones de cotizaciones van en tinta neutra: que el dólar suba no es bueno ni malo para todos.

### Contraste mínimo

Verificado por test en ambos temas: 4,5:1 para todo texto y 3:1 para elementos gráficos, sobre cada superficie donde aparecen.

## Tipografía

* **Lexend** (`--md-ref-typeface-brand`): display, headline y cifras grandes. Ancha y abierta; en montos se ve contundente.
* **Google Sans Flex** (`--md-ref-typeface-plain`): títulos de componentes, cuerpo y etiquetas.
* Cifras de ancho fijo (`tabular-nums`) en columnas y tablas.
* Formato argentino: punto para miles, coma para decimales, moneda siempre visible. En listas y tablas, siempre dos decimales.

| Rol | Familia | Tamaño / interlineado |
|---|---|---|
| Display large | Lexend 500 | 57 / 64, −3,5 % |
| Headline medium | Lexend 500 | 28 / 36, −2 % |
| Headline small | Lexend 500 | 24 / 32 |
| Title large | Google Sans Flex 500 | 22 / 28 |
| Title medium | Google Sans Flex 600 | 16 / 24 |
| Body large | Google Sans Flex 400 | 16 / 24 |
| Body medium | Google Sans Flex 400 | 14 / 20 |
| Label large | Google Sans Flex 600 | 14 / 20 |
| Label medium | Google Sans Flex 600 | 12 / 16, mayúsculas, +6 % |

## Forma

El redondeo crece con el tamaño de la pieza: aplicar 28 px a todo infla los elementos chicos.

| Token | Valor | Piezas |
|---|---|---|
| `--rinde-shape-badge` | 8 px | Tooltips, insignias |
| `--rinde-shape-chip` | 10 px | Chips |
| `--rinde-shape-field` | 14 px | Campos, snackbar |
| `--rinde-shape-fab` | 16 px | Botón flotante, filas |
| `--rinde-shape-card` | 20 px | Cards, tablas |
| `--rinde-shape-dialog` | 28 px | Diálogos, hojas, héroe |
| `--rinde-shape-full` | píldora | Botones |

## Espacio

Grilla de 4: `4, 8, 12, 16, 24, 32, 48, 64` (`--rinde-space-1` a `--rinde-space-8`).

## Elevación

Seis niveles (`--md-sys-elevation-level0` a `level5`): cada uno sube un escalón de superficie y suma una sombra más profunda. Un filo de luz de un píxel en el borde superior da volumen sin gradientes. El vidrio esmerilado solo aparece donde el contenido pasa por debajo: la barra superior y el velo de los diálogos.

## Movimiento

| Token | Valor | Uso |
|---|---|---|
| `--md-sys-motion-easing-standard` | `cubic-bezier(0.2, 0, 0, 1)` | Cambios dentro de la pantalla |
| `--md-sys-motion-easing-emphasized-decelerate` | `cubic-bezier(0.05, 0.7, 0.1, 1)` | Entradas: diálogos, hojas, snackbar |
| `--md-sys-motion-easing-emphasized-accelerate` | `cubic-bezier(0.3, 0, 0.8, 0.15)` | Salidas: cerrar, descartar |
| `--md-sys-motion-duration-short3` | 150 ms | Hover y foco |
| `--md-sys-motion-duration-medium1` | 250 ms | Selección |
| `--md-sys-motion-duration-medium4` | 400 ms | Entradas |
| `--md-sys-motion-duration-long2` | 500 ms | Cambio de pantalla |

Las salidas duran menos que las entradas: el usuario ya decidió irse.

## Estados

Capa del color del contenido sobre el componente, con las opacidades de Material 3: hover 8 %, foco 10 % más anillo de 3 px en `primary`, presionado 10 %, arrastrado 16 %. Nunca se oscurece ni se aclara el fondo a mano.

## Componentes

Se construyen sobre React Aria cuando una pantalla los necesita, cada uno con tests de interacción y de accesibilidad (`axe-core`).

| Componente | Especificación |
|---|---|
| Botón | Píldora, 40 px de alto, variantes rellena, tonal, con borde y de texto. Una sola acción rellena por pantalla. |
| Botón flotante extendido | 56 px, `shape-fab`, `primary-container`, elevación 3, atajo de teclado visible. |
| Campo de texto | Con borde, 56 px, `shape-field`, etiqueta flotante; el error dice cómo corregir. |
| Chip de filtro | 32 px, `shape-chip`; el check aparece al elegir. |
| Botón segmentado | 40 px, píldora, `secondary-container` en el elegido, con check. |
| Lista de movimientos | Filas de 68 px, avatar de 44 px, monto a la derecha con signo y flecha; cuotas y dólar de conversión visibles. Las transferencias propias van en tinta neutra. |
| Tabla | Encabezado fijo en `surface-container-high`, cifras de ancho fijo, estado con ícono y texto. |
| Gráfico de magnitud | Un solo tono (`--rinde-chart-mark`), etiquetas directas, tooltip con porcentaje, tabla equivalente. |
| Skeleton | Pulso de opacidad (sin brillo en degradé) con la forma exacta del contenido. |
| Estado vacío | Explica el porqué y ofrece la próxima acción. |
| Snackbar | `inverse-surface`, `shape-field`, Deshacer durante 6 segundos. |
| Diálogo | `shape-dialog`, elevación 5, velo con vidrio. Solo para acciones irreversibles. |
| Hoja inferior | Solo en pantallas chicas; el botón dice el resultado ("Ver 42 movimientos"). |
| Navigation rail | 88 px; en pantallas chicas pasa a barra inferior. |

## Patrones de interacción

* **Tiempos de respuesta:** menos de 100 ms, instantáneo (crear y editar son optimistas); 100 a 300 ms, nada extra; 300 ms a 2 s, skeleton; más de 2 s, skeleton y un texto que explica qué pasa.
* **Deshacer antes que preguntar:** confirmar todo entrena a tocar "Sí" sin leer. El diálogo queda para lo irreversible.
* **Atajos:** `N` nuevo movimiento, `/` buscar, `Esc` cerrar; siempre visibles junto a la acción.
* **Errores:** dicen qué pasó y cómo seguir, sin disculpas ni códigos.
* **Accesibilidad:** contraste AA o más, foco siempre visible, orden de tabulación lógico, alternativa textual o tabla para cada gráfico.
