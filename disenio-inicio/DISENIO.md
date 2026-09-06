# Guía de diseño — IMPULSAR

Acá se van anotando las decisiones de diseño a medida que las tomamos: colores,
fuentes, medidas y por qué. Es la referencia para cualquier pantalla nueva.

La fuente de verdad del código sigue siendo `static/css/styles.css` (bloques
`:root` y `[data-theme="dark"]`). Este archivo explica de dónde salen esos
valores y qué se decidió encima de ellos.

---

## El logo

`static/icons/logo_impulsar.png` — 1279 × 463 px, PNG con transparencia, 130 KB.
Es la barra inclinada doble (el "1" / la pluma) más la palabra *mpulsar* en
minúsculas, con la barra haciendo de "I".

Colores muestreados del archivo, pixel por pixel:

| Pieza del logo | Color |
| --- | --- |
| Barra delantera, base (lo más oscuro) | `#302778` |
| Barra delantera, punta (lo más claro del índigo) | `#4A3B8E` |
| Barra de atrás (el gris azulado claro) | `#A4B1C4` |
| Palabra "mpulsar" | `#5D6F87` |

**La barra tiene un degradado**, no un plano: va de un violeta más vivo arriba a
un índigo casi negro abajo.

### Cómo se traduce a tokens

El índigo del logo es el que manda en toda la interfaz. Ya está en el CSS:

- `--color-primary: #3E2F94` — el índigo del logo. Antes era `#665DF1` (un
  violeta más claro y más saturado, herencia de `#6C63FF`); se cambió al del
  logo porque el blanco encima gana contraste: **10.3:1**, muy arriba del 4.5:1
  que pide AA.
- `--color-primary-hover: #33267C` — 13.0:1 contra blanco, y 1.27:1 contra el
  normal, así que el hover se sigue notando.
- `--color-primary-deep: #2A2068` — el índigo profundo, para bloques de marca
  con texto blanco fijo. **Mismo valor en los dos temas a propósito**: no es una
  superficie que siga al tema. 13.9:1 contra blanco.
- `--color-primary-soft: #ECEAF7` — el índigo lavado, para fondos suaves.

El gris de la palabra (`#5D6F87`) y la barra clara (`#A4B1C4`) **no tienen
token**: son del logo, no de la interfaz. Los neutros de la UI son otra familia
(abajo), aunque comparten la misma tirada fría azulada a propósito.

---

## Paleta

Fría y apenas azulada, de la misma familia que el índigo — no grises neutros.

### Tema claro

| Rol | Token | Valor |
| --- | --- | --- |
| Primario | `--color-primary` | `#3E2F94` |
| Primario hover | `--color-primary-hover` | `#33267C` |
| Índigo profundo | `--color-primary-deep` | `#2A2068` |
| Índigo lavado | `--color-primary-soft` | `#ECEAF7` |
| Texto sobre índigo | `--color-on-primary` | `#FFFFFF` |
| Fondo | `--color-bg` | `#F5F7FA` |
| Superficie | `--color-surface` | `#FFFFFF` |
| Superficie alterna | `--color-surface-alt` | `#EEF1F7` |
| Texto | `--color-text` | `#1B2430` |
| Texto suave | `--color-text-soft` | `#4A5666` |
| Texto apagado | `--color-muted` | `#5F6B7C` (5.5:1 sobre blanco) |
| Borde | `--color-border` | `#E2E6EE` |
| Acento (terracota) | `--color-accent` | `#D97544` |
| Éxito / "abierto ahora" | `--color-success-bg` / `-text` | `#E6F4EC` / `#1F7A4D` |
| Aviso / "esperando" | `--color-warning-bg` / `-text` / `-strong` | `#FBEDE4` / `#8C4A22` / `#D97544` |
| Error | `--color-danger-bg` / `-text` | `#FEE2E2` / `#B91C1C` |
| Estrella | `--color-star` / `-empty` | `#E8A33D` / `#E2E6EE` |

### Tema oscuro

No es "todo gris invertido": los fondos mantienen la tirada violeta
(azul-violeta desaturado, nunca negro neutro) y **el primario se aclara**,
porque el índigo oscuro sobre fondo oscuro queda apagado. Como el violeta claro
es luminoso, el texto que va *encima* del primario pasa a ser oscuro.

| Rol | Valor |
| --- | --- |
| Primario | `#9B93FF` (hover `#B3ACFF`) |
| Texto sobre primario | `#16132A` |
| Fondo / superficie / superficie alterna | `#141222` / `#1D1A2E` / `#292440` |
| Texto / suave / apagado | `#ECEAF7` / `#C6C2DA` / `#A29DBA` |
| Borde | `#342E4D` |
| Acento | `#F1965D` (más claro que el `#D97544` del tema claro) |

### Reglas de color que no se rompen

1. **Nada de colores hardcodeados en el CSS de la app.** Color nuevo = token
   nuevo, definido en **los dos** bloques. Si sólo se define en `:root`, el modo
   oscuro queda roto en silencio.
2. **La terracota `#D97544` nunca es color de texto.** Sobre fondo claro da
   3.2:1 y no llega a AA. Es marca de color: el punto, la barra de la fila, el
   rótulo. Para texto sobre terracota suave, `#B85F30`.
3. **Los bloques de marca usan `--color-primary-deep`, no `color-mix()` sobre el
   primario.** El `color-mix` falla contraste en modo oscuro.
4. Los acentos nuevos se definen en oklch, compartiendo croma y luminosidad y
   variando sólo el tono. No inventar colores desde cero: primero mirar si ya
   hay uno que sirva.
5. Blancos y negros van sutilmente entonados (nunca `#FFF` puro como fondo de
   página, nunca saturación > 0.02 en los blancos).

---

## Paleta de rubros

Los siete rubros del inicio son una **paleta categórica**: colores que se
distinguen entre sí sin que ninguno pese más que otro. Cada uno es un par —
fondo del ícono + tinta — y todos comparten luminosidad y croma, variando sólo
el tono. Eso es la regla 4 de arriba aplicada en serio.

El orden es el de `Categorias.ETIQUETAS` en `app/blog/modelo_post.py:31`, que es
el que recorre `home.html`. No reordenar por gusto: es el orden real de la app.

| Rubro | Fondo | Tinta | Tono | Contraste |
| --- | --- | --- | --- | --- |
| Alimentos | `#FDECE5` | `#9A5230` | 45° | 5.05:1 |
| Servicios | `#F4F0E1` | `#7C6700` | 95° | 4.85:1 |
| Hogar | `#E5F5EC` | `#1C7B53` | 160° | 4.64:1 |
| Tecnología | `#E5F2FD` | `#1D6FA0` | 240° | 4.81:1 |
| Artesanías | `#EEEFFE` | `#635EA3` | 285° | 5.03:1 |
| Indumentaria | `#FBEBF2` | `#954D71` | 350° | 5.11:1 |
| Otros | `#EEF1F7` | `#5F6B7C` | neutro | 4.86:1 |

- Las tintas están todas en **L 0.519 / C 0.107**; los fondos en **L 0.955 /
  C 0.020**, cada uno en el tono de su rubro.
- Ese croma no se eligió por gusto: es **el más alto que los seis tonos aguantan
  a la vez dentro de sRGB** sin bajar de 4.6:1. El que manda es el tono 95
  (el oliva): un amarillo oscuro y saturado se sale de gama, así que marca el
  techo para todos.
- **"Otros" es neutro a propósito**: es el cajón de sastre, no una categoría más,
  y usa directamente `--color-muted` sobre `--color-surface-alt`.
- El color del rubro es **una identidad, no una decoración**: el mismo par tiene
  que usarse en el ícono de la grilla de rubros y en el puntito de la tarjeta de
  emprendimiento. Si aparece en un lugar nuevo, va el mismo par.

### El índigo del anuncio y de los botones (2026-09-04)

Tomás no quería el morado oscuro casi negro. Dos cambios:

- **El panel del anuncio y el bloque del CTA** pasaron de
  `#2F2578 → #241C63 → #171046` (casi negro) al índigo real del logo:
  `#4A3B8E → #3E2F94 → #33267C`.
- **Los botones primarios** subieron dos pasos de luminosidad, de `#3E2F94` a
  **`#5248AE`** (hover `#483BA1`). 7,25:1 con el texto blanco.
  **Ojo:** ese `#5248AE` ya no es `--color-primary`. Cuando esto pase a código
  hay que decidir si se cambia el token o si el botón queda como excepción.

### Qué tenía de malo la anterior

Vale anotarlo para no repetirlo:

- **Alimentos daba 3.9:1** (`#B85F30` sobre `#FBEDE4`) — no llegaba a AA.
- **Tres pares eran indistinguibles**: Indumentaria (283°) y Artesanías (288°)
  estaban a 5° uno del otro, y Tecnología (259°) con Servicios (253°) a 6°.
- **Tecnología era gris** (croma 0.036): leía como deshabilitado, no como rubro.
- La luminosidad iba de 0.388 a 0.583 y el croma de 0.036 a 0.158, así que unos
  rubros gritaban y otros desaparecían.
- Indumentaria usaba el índigo de marca (`--color-primary`) y Hogar el verde de
  "abierto ahora" (`--color-success-text`): un rubro no puede quedarse con un
  color que ya significa otra cosa.

---

## Tipografía

Se cargan las dos de Google Fonts, en un solo `<link>`:

```html
<link href="https://fonts.googleapis.com/css2?family=Poppins:wght@500;600;700&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
```

- **Poppins** (500 / 600 / 700) — títulos, botones, chips, etiquetas de rubro.
  `font-family: "Poppins", system-ui, sans-serif`
- **Inter** (400 / 500 / 600) — cuerpo, formularios, todo lo demás.
  `font-family: "Inter", system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif`

Los títulos llevan `text-wrap: pretty` y `letter-spacing: -.02em` en los tamaños
grandes.

> Nota: la exportación a PNG/PDF del canvas de diseño **no incrusta las fuentes
> de Google**, así que ahí los títulos salen con la tipografía de respaldo. Por
> eso los titulares se dimensionan con ~10 % de holgura.

---

## Formas y sombras

| Token | Valor |
| --- | --- |
| `--radius-sm` | `8px` |
| `--radius-md` | `12px` |
| `--radius-lg` | `16px` |
| `--shadow-soft` | `0 10px 30px rgba(15, 23, 42, .10)` |
| `--shadow-light` | `0 4px 12px rgba(15, 23, 42, .08)` |
| `--shadow-card` | `0 8px 20px rgba(15, 23, 42, .06)` |
| `--shadow-navbar` | `0 1px 4px rgba(15, 23, 42, .06)` |

En modo oscuro las sombras pasan a negro puro y bastante más opacidad
(`.40`–`.55`): una sombra azulada translúcida sobre fondo oscuro no se ve y las
tarjetas no despegan.

---

## Medidas del inicio

Lo que quedó fijado en el canvas del inicio:

- **Escritorio**: artboard de 1440 px; el contenido va en una caja de
  `max-width: 1160px` con `padding: 0 24px`.
- **Teléfono**: artboard de 390 px. Todos los controles tocables miden **44 px
  como mínimo** — es piso, no sugerencia.
- **Navbar**: `min-height: 68px`, fondo `#FFFFFF`, borde inferior de 1 px.
- **Buscador de la navbar**: 40 px de alto, `border-radius: 999px`.
- Los grupos de hermanos (chips, botones, rubros, tarjetas) se maquetan con
  `display: flex` / `grid` + `gap`, nunca con márgenes por elemento ni espacios
  del código fuente.
- Los íconos son SVG en línea, trazo de 1.7, grilla de 16/20/24 px. **Nunca
  emoji.**

---

## Qué del diseño existe en la app y qué no

El inicio se dibujó contra el repositorio, no de memoria. Estado al 2026-09-03:

**Existe y el diseño lo respeta:**

- Navbar: Inicio · Emprendimientos · Eventos · Servicios · Acceder · Registrarse
  (`templates/base.html`). La app ya mostraba el logo como imagen.
- Los 7 rubros, con los nombres y el orden de `Categorias.ETIQUETAS`.
- Buscador de 3 campos: qué, rubro y dónde, con los placeholders reales
  ("Pan de masa madre", "Tu barrio o dirección").
- Últimos emprendimientos, ferias y eventos con calendario, CTA y pie.
- "Abierto ahora" (`services/horarios.py`, y en SQL en `app/blog/consultas.py`),
  promedio de reseñas (`services/ratings.py`) y favoritos.

**NO existe en la app:**

- **Toda la sección de publicidad.** No hay modelo, ni vista, ni ruta, ni
  columna: `grep` de publicidad/anuncio en el repo no devuelve nada fuera del
  bundle del rediseño. Es una funcionalidad **propuesta** por el diseño, no una
  pantalla existente. Lo mismo el enlace "Planes de publicidad" del pie.
  Si se aprueba, hay que diseñar el modelo, el alta del anunciante, la
  rotación y el criterio de qué se muestra a quién antes de maquetarlo.

---

## El carrusel de publicidad

Sección nueva, arriba de todo en el inicio. Decisiones:

- Panel de índigo profundo (`#2A2068`) de fondo, con la columna izquierda fija
  de IMPULSAR y la derecha del anunciante.
- **Cada anunciante trae su propio color de acento**, que sólo pinta su plancha
  — nunca el chrome de alrededor.
- **Rota solo cada 6 segundos, sin flechas ni selector.** No es un carrusel que
  el visitante tenga que operar: es un anuncio, y la rotación reparte la
  exposición sola. La fila de anunciantes con nombre y plan que había antes se
  sacó (2026-09-03) por decisión de Tomás.
- **La creatividad del anunciante es un hueco marcado, no una cuadrícula.** El
  degradado del anunciante, sus iniciales de marca de agua y la medida que tiene
  que entregar (1200 × 680). La cuadrícula de papel milimetrado que había antes
  leía como maqueta sin terminar.
- **La galería es de cuatro fotos**: una principal de 1200×680 y tres de
  800×800. En escritorio se ven las cuatro (la grande arriba, las tres abajo).
- **En teléfono va UNA sola foto**, a sangre, de 160 px, y el resto se anuncia
  con un chip "+3 fotos". Las tres miniaturas se probaron y quedaron mal: tres
  cajitas vacías con un iconito adentro leen como carga rota, y se comían 70 px
  arriba del texto. Tampoco va ahí la marca de agua con las iniciales (se
  cortaba contra el borde) ni el rótulo con la medida, que es una nota para el
  anunciante y no para quien mira.
- El rótulo "Publicidad" vive dentro del panel en vez de ser una banda propia.
- **El buscador no lleva titular.** Ni "Todo lo que se hace cerca tuyo", ni el
  contador de publicados, ni bajada: sólo el filtro. Decisión de Tomás
  (2026-09-03). Ojo: eso deja la página sin `<h1>`; cuando se pase a código hay
  que resolver dónde vive el encabezado accesible.
- **El logo del pie va a 38 px**, más grande que el de la barra (32 px): la
  palabra del logo es gris (`#5D6F87`) y al lado de los títulos de columna en
  `#1B2430` a 30 px se veía lavada. El PNG incrustado se rehízo a 240 px de
  ancho (antes 440) para que el navegador haga una reducción limpia de ~2x en
  vez de una de 3.9x, con un unsharp suave: los trazos finos de la barra salían
  blandos.

---

## Pendientes anotados

- [x] ~~La navbar del canvas usa un cuadradito con la letra "I".~~ Hecho: el
  canvas usa el logo de verdad en los tres lugares (navbar de escritorio a
  32 px, pie a 30 px, barra del teléfono a 28 px). El archivo del canvas es
  `logo-impulsar.png`: el original recortado al contenido y llevado a 440 px de
  ancho (36 KB), porque el canvas incrusta las imágenes y el original de 130 KB
  era innecesario para ese tamaño.
- [x] ~~Tres neutros cerca pero no iguales a los tokens.~~ Hecho: `#6B7686` y
  `#9AA3B2` pasaron a `--color-muted` `#5F6B7C`, y `#E6E9F1` a `--color-border`
  `#E2E6EE`. El `#9AA3B2` estaba en las iniciales de los días del calendario, a
  10.5 px: daba ~2.5:1 sobre blanco y no llegaba ni cerca de AA.
- [ ] **La app tiene su propia paleta de rubros y no es ésta.** En
  `static/css/styles.css:6199` están los `.rubro__tono--*`, siete colores que
  arrastran los mismos problemas que tenía el canvas: `#C3CEE3` (Servicios) es
  un gris azulado pálido, `#4A5666` (Tecnología) es `--color-text-soft`,
  `#E8A33D` (Otros) es el amarillo de las estrellas y `#3E2F94`
  (Indumentaria) el índigo de marca. Ahí son sólo puntitos, sin texto encima,
  así que no hay problema de contraste — pero sí de identidad: el mismo rubro
  tiene dos colores según la pantalla. Sincronizarlos con la tabla de arriba.
- [ ] Faltan los estados del inicio: cargando, sin resultados, y la navbar con
  sesión iniciada.
- [ ] No hay artboard intermedio (~768 px) para ver cómo caen rubros y ferias
  entre escritorio y teléfono.

---

## Posicionamiento: contra Mercado Libre y Marketplace

Decisión del 2026-09-04, y es la que ordena todo el diseño de acá en adelante.

**Competir de frente es una pelea perdida.** Mercado Libre gana en catálogo,
logística, pagos y protección al comprador; Marketplace gana por estar adentro
de Facebook. Nada de eso se resuelve con diseño, y el repo no tiene ni pagos ni
envíos.

**Lo que ninguno de los dos hace es lo local con identidad**, y eso IMPULSAR ya
lo tiene en el modelo:

- **Horarios reales** (`app/perfil/modelo_horario.py`), con el filtro
  "abierto ahora" resuelto en SQL en `app/blog/consultas.py`.
- **Distancia real**: `Post.latitude/longitude`, geocodificación con MapTiler y
  orden por cercanía con radio en km.
- **La persona detrás**, con antigüedad y reseñas.
- **Ferias**: dónde encontrarla en persona esta semana. Esto es lo más difícil
  de copiar para ellos.
- **Contacto directo, sin comisión.** Es un argumento, y se dice en la ficha.

**Regla de diseño que sale de esto:** esos cinco datos van adelante y en grande,
nunca escondidos en un panel de filtros ni en una pestaña secundaria. Y no se
copian los códigos de Mercado Libre — nada de precios gritados, "envío gratis",
cuotas ni contadores de urgencia. Ese no es el juego.

### Las dos pantallas de la página "Competir"

- **`Resultados.dc.html`** — el listado. Los cinco filtros son exactamente los
  que `app/blog/vistas.py:117` ya resuelve. "Abierto ahora" y el radio en km van
  como fichas grandes y encendidas. Cada tarjeta lleva número que coincide con
  el pin del mapa, así la lista y el mapa se leen juntos.
- **`Ficha.dc.html`** — la ficha. Cada bloque sale de una tabla que existe:
  productos con precio (`models/product.py`), servicios con zona, precio
  estimado y turnos (`app/servicios/modelo.py`), reseñas, horarios de la semana
  con hoy marcado, ferias y mapa.

Cada una tiene su versión de teléfono (`ResultadosMovil.dc.html`,
`FichaMovil.dc.html`), con tres decisiones propias del móvil:

- **La tarjeta del listado es horizontal y compacta** (foto cuadrada de 104 px).
  Una tarjeta vertical por emprendimiento obliga a scrollear muchísimo para
  comparar, y comparar es a lo que se viene.
- **El mapa es un botón al lado del buscador**, no una columna ni un botón
  flotante. Flotando tapaba una tarjeta.
- **El contacto de la ficha va en una barra fija abajo**, con "Sin comisión" al
  lado. Es la acción de la pantalla y el argumento contra Mercado Libre; no
  puede vivir al final de 2.000 px de scroll.
- Las tiras que se deslizan de costado llevan la clase `.u-tira`, que esconde la
  barra de scroll: en un teléfono real no se dibuja, pero en el artboard sí y
  ensucia.

Las cuatro son maquetas estáticas: los filtros del listado alternan de verdad,
el resto no tiene comportamiento.

---

## Qué está pasado a código (2026-09-04)

El diseño dejó de vivir sólo en el canvas. Lo que ya está en la app:

**Tokens** (`static/css/styles.css`, los dos temas):

- `--color-primary-boton` `#5248AE` y `--color-primary-boton-hover` `#483BA1`.
  **No es `--color-primary`**: el índigo del logo manda en texto (enlaces,
  íconos, títulos), y el relleno de los botones es dos pasos más claro. En
  oscuro el botón sigue al primario, que ahí ya es claro.
- `--color-panel-from/mid/to` (`#4A3B8E` / `#3E2F94` / `#33267C`), iguales en
  los dos temas: son bloques de marca con texto blanco fijo, como
  `--color-primary-deep`.
- Los siete pares `--rubro-*-bg` / `--rubro-*-ink`, con su versión oscura.
  Los `.rubro__tono--*` ahora salen de ahí en vez de ser colores sueltos, y hay
  una clase `.rubro-pastilla--*` para usarlos como pastilla con texto.

**Home** (`templates/home.html`):

- Sin titular ni contador: la banda es el filtro y nada más. El `<h1>` sigue
  existiendo como `.sr-only`, porque la página no puede quedarse sin uno.
- El CTA pasó de la caja lila clara al panel índigo (`.cta__caja--panel`), con
  el botón primario invertido a blanco: el índigo sobre índigo no despegaba.

### El inicio entero, pasado a código (2026-09-04, segunda tanda)

Lo que faltaba del artboard `Main.dc.html`:

- **El buscador es UNA caja**, no tres inputs con su borde cada uno: un
  recuadro de 18 px de radio con los tres campos separados por líneas
  (`box-shadow: inset 1px 0 0`, sin `<span>` vacío por medio), la lupa dentro
  del primer campo, campos de 64 px y el botón "Buscar" grande a la derecha.
  Es la misma forma que la barra del listado a propósito — buscar tiene que
  ser el mismo gesto en las dos pantallas — pero con clases propias: ésta no
  es pegajosa y su botón es de 64 px, no de 44.
  - "Cerca de mí" dejó de ser un link debajo del campo y es una **pastilla
    dentro** del campo "Dónde", con el pin. Sigue sin ser sólida para no
    competir con "Buscar".
  - Las proporciones del artboard (2 / 1 / 1,15) son para una caja de 1160 px.
    El container de la app es más angosto y con ésas el placeholder
    "Tu barrio o dirección" quedaba cortado; quedaron en 1,8 / 1 / 1,4.
  - En teléfono los tres campos se apilan y el botón va a lo ancho, igual que
    la barra del listado.
- **Los rubros son fichas con ícono**: plancha de 42 px con el **par completo**
  del rubro (fondo + tinta) y un SVG propio para cada uno
  (`partials/_icono_rubro.html`). Antes era un cuadradito de 26 px pintado sólo
  con la tinta, que no usaba la mitad del par. Grilla de 4 columnas
  (`auto-fit` de 230 px) con la **octava ficha, "Ver todo"**, en el bloque de
  marca: cierra el 4×2 y es la salida al listado sin filtrar.
- **Rótulos de sección** (`.section__rotulo`): RUBROS, RECIÉN PUBLICADOS,
  AGENDA. Van en `--color-warning-text` y no en el `#D97544` de marca, que a
  ese tamaño no llegaría a AA. Los enlaces "Ver todos" llevan la flecha del
  artboard, que se corre 3 px al pasar por encima.
- **La tarjeta del inicio pasó a ser la `.tarjeta` del listado en vertical**
  (`.tarjeta--vertical`), no la `.ficha` vieja: foto de 188 px de cabecera, la
  pastilla del rubro y las acciones **sobre la foto** (así la tarjeta arranca
  por el nombre), reseñas, descripción y pie con quién publicó y el botón
  "Ver". El CSS vive al final de `styles.css`, con el resto de `.tarjeta`:
  definido antes perdía por orden, porque tienen la misma especificidad.
- **`/api/posts/` ahora manda `avg_rating`, `review_count` y `author_name`.**
  Salen de `query_posts_con_rating()` (la misma subquery agrupada del listado,
  no un promedio por tarjeta) y de la relación `author_user`, que es
  `lazy="joined"`: no suma consultas. El promedio va en `float` y no en el
  `Decimal` que devuelve MySQL, que `jsonify` serializaría como cadena.
  Sin reseñas viaja `None` y no `0`: un emprendimiento nuevo no está
  calificado con un cero.

Lo que **no** se pasó del artboard del inicio, y por qué:

- **La publicidad**, entera. Sigue sin haber modelo, tabla ni ruta.
- **Los chips de "Buscado hoy"** del buscador. No hay registro de búsquedas:
  serían cuatro términos inventados con cara de dato.
- **"Abierto ahora", el barrio y los km en la tarjeta.** Los horarios y las
  coordenadas existen, pero hoy no viajan por fila en `/api/posts/` y sin
  geolocalizar no hay distancia que calcular. Sigue siendo la mejora de mayor
  valor que queda.

**Listado** (`app/blog/templates/blog/index.html`):

- Los filtros salieron de la columna izquierda y subieron a una barra pegajosa
  (`.barra-filtros`). Es el mismo `<form method="get">` con los mismos `name`,
  así que la vista no cambió.
- "Abierto ahora" y "Con reseñas" dejaron de ser checkbox y son fichas que
  alternan: la macro `url_alternando()` arma la misma URL con el parámetro dado
  vuelta. El hidden los hace viajar si además se aprieta "Buscar".
- El radio pasó de un grupo de radios a un `<select>` que se manda solo, y
  **sólo se dibuja cuando hay coordenadas**: sin ellas la consulta lo ignora.
- "Solo verificados" se fue del todo. Estaba dibujado y apagado con un aviso
  al lado; en una barra no hay lugar para un control que no hace nada.
- La tarjeta es horizontal (`.tarjeta`): foto a la izquierda, y a la derecha lo
  que decide una comparación. En teléfono la foto baja a 116 px y la
  descripción se esconde.
- En teléfono los tres campos van adentro de un `<details>` que `main.js`
  cierra al cargar. Arranca con `open` en el HTML: **sin JS queda desplegado**,
  que es peor pero nunca roto. La barra bajó de 310 px a 135 px y el primer
  resultado pasó de estar a 633 px a estar a 412 px.

### Detalles que cuestan una tarde si no están anotados

- **`display: contents` en un `<details>` no alcanza en Chrome.** Los hijos van
  adentro de una caja generada, `::details-content`, así que hay que ponerle
  `display: contents` también, y devolvérsela a `block` en la media query del
  teléfono — si no, el `<details>` no puede esconder su contenido y no cierra.
- **El vacío del listado mentía.** Con sólo "abierto ahora" puesto decía "No hay
  emprendimientos registrados todavía". Los hay: están cerrados. Ahora tiene su
  propia rama, que además dice qué hacer.
- Las fichas y los títulos de tarjeta necesitan `text-decoration: none`
  explícito: son `<a>` y heredan el subrayado.

### Lo que NO se pasó, y por qué

- **La publicidad, entera.** No hay modelo, ni tabla, ni ruta. Portarla es
  diseñar el anunciante, el plan contratado, la rotación y el alta: es una
  feature, no un pase a front.
- **El mapa de la columna derecha del listado.** MapTiler se usa sólo para
  geocodificar; no hay widget de mapa. Dibujar uno falso sería mentir.
- **"Abierto ahora" y la feria en cada tarjeta.** Los datos existen
  (`_abierto_ahora_sql`, `Post.eventos`) pero hoy no viajan por fila: hay que
  agregarlos como columna del select. Es la mejora de mayor valor que queda.
- **La ficha del emprendimiento** (`detail.html`, 466 líneas) y las versiones
  de teléfono del canvas más allá de lo responsive del listado.

Los tests del listado se actualizaron a la interfaz nueva (15 de ellos):
afirmaban sobre los radios, los checkbox y los chips que ya no existen. La
suite queda en 832 en verde.

---

## Entrar y crear cuenta (2026-09-04)

Reemplazan a la pantalla partida mitad y mitad, con el panel índigo del conteo
de emprendimientos y los cuatro beneficios numerados. Se sacó entera: partía la
vista al medio y en teléfono era un segundo scroll de relleno.

**La pantalla.** A pantalla completa sobre una foto semioscura, sin barra y sin
pie: la barra ofrecía "Acceder" y "Registrarse", que es lo que la pantalla ya
está haciendo. Para poder sacarlos, `base.html` envuelve la barra y el pie en
`{% block navbar %}` y `{% block footer %}`, y las dos plantillas de auth los
vacían. El logo va adentro, arriba de la tarjeta, invertido a blanco con un
filtro CSS (la palabra del logotipo es gris azulado y sobre la foto no se
leería).

**La foto todavía no está**, y hay UN solo lugar para ponerla: la regla
`.auth__foto` en `static/css/styles.css`. Se deja el archivo en `static/icons/`,
se descomenta el `background-image` y listo. Mientras tanto hay un degradado
oscuro con una luz cálida arriba a la izquierda, que reproduce los valores que
va a tener la foto. La que entre tiene que ser horizontal, de 2400 px de ancho o
más, con el sujeto **a un costado**: el centro lo tapa la tarjeta.

Encima de la foto van tres capas, cada una con su motivo:

1. `.auth__velo` — índigo al 46 %: la baja a semioscura y la tiñe con el color
   de la marca en vez de dejarla en gris.
2. `.auth__degradado` — oscurece arriba y abajo, para que el logo y las líneas
   del pie se lean contra **cualquier** foto que se ponga después.
3. `.auth__vineta` — cierra la composición sobre la tarjeta.

**La tarjeta no sigue al tema.** El fondo es una foto con valores fijos en los
dos temas; si la tarjeta siguiera al tema, en oscuro quedaría gris oscuro sobre
foto oscura y se perdería el único contraste que sostiene la composición. Es la
misma regla de `--color-primary-deep`: un bloque con valores propios. Se
resuelve redeclarando los tokens del tema claro dentro de `.auth__card`, más un
`color:` explícito — redeclarar los tokens no alcanza, porque los títulos no
fijan color sino que lo **heredan** del `<body>`, que ya lo resolvió.

**El rol pasó de un `<select>` a dos fichas**, Comprar y Vender, con
`<input type="radio">` de verdad escondidos con `clip-path` (no `display:none`,
que los sacaría del orden de tabulación). Funciona sin JavaScript.

**"Administrador" se fue, y no sólo del HTML.** El `<select>` lo ofrecía y la
vista guardaba lo que viniera: cualquiera se registraba como admin llenando un
formulario público, o mandando `{"rol": "admin"}` a la API sin pasar por el
formulario. Ahora las dos vistas filtran contra `ROLES_AL_REGISTRARSE`
(`views/auth.py`) y lo que no sea `usuario` o `emprendedor` cae en `usuario`:
ante un valor raro se elige el **menor** privilegio. Hay cinco tests nuevos.

**El botón de la contraseña es el ojo solo**, sin la palabra "Mostrar": el
ícono ya lo dice. La palabra queda en el `aria-label`, que es donde hace falta.
Se dibuja escondido y lo enciende `main.js`: sin JS no queda un botón pintado
que no responde. Al apretarlo el foco vuelve al campo con el cursor al final.

**El error dejó de ser un flash suelto arriba de todo** y se dibuja adentro de
la tarjeta, arriba de los campos: es la respuesta a lo que se acaba de mandar y
se lee donde se estaba mirando.

### Lo que NO se pasó, y por qué

- **El chequeo de "Disponible" en el usuario.** El canvas lo muestra al lado
  del campo. `User.existe_username_equivalente` existe, pero contestar en vivo
  pide una ruta nueva y un fetch con debounce: es una funcionalidad, no un pase
  a front. Dibujarlo apagado sería mentir.
- **"¿La olvidaste?".** No hay recuperación de contraseña: no hay ruta, no hay
  token, no se mandan mails. Un link muerto en la pantalla de entrar es peor
  que no tenerlo.
- **El conteo de emprendimientos.** Se fue con el panel. Las dos vistas ya no
  pasan `total_posts` y `auth/_panel.html` se borró.

### Medidas

- Tarjeta de 468 px de ancho, radio 26, sombra
  `0 44px 96px rgba(8,4,28,.52)` — más fuerte que la de una tarjeta normal,
  porque sobre fondo oscuro una sombra suave no despega nada.
- Campos de 48 px con el ícono adentro; el borde y el foco los lleva la caja,
  no el `<input>`.
- En teléfono: 20 px de margen a cada lado (con `box-sizing: border-box` en la
  tarjeta, si no el `width: 100%` le sumaba su propio padding y quedaba pegada
  a los bordes), solapas de 44 px, y del argumento queda **una** sola línea.


## Dónde está cada cosa

| Qué | Dónde |
| --- | --- |
| Tokens de color, tipografía, sombras | `static/css/styles.css` (`:root`, `[data-theme="dark"]`) |
| Carga de las fuentes | `templates/base.html` |
| Logo | `static/icons/logo_impulsar.png` |
| Plantilla del inicio | `templates/home.html` |
| Entrar y crear cuenta | `templates/auth/` (login, register y los tres parciales) |
| **Dónde va la foto de auth** | la regla `.auth__foto` en `static/css/styles.css` |
| Artboards de auth | `disenio-auth/*.dc.html`, que salen de `disenio-auth/generar.py` |
| Artboards del rediseño del inicio | `disenio-inicio/*.dc.html` + `canvas.json` |
| Canvas publicado | https://claude.ai/code/artifact/d084b4e0-99a9-4ce4-ae31-62e5da16aa2d |

## El perfil (2026-09-04)

Seis artboards en `disenio-perfil/`: emprendedor visto por un visitante y por
su dueña, y cliente (rol `usuario`), cada uno con su versión de teléfono.

- **Identidad y contacto en una sola tarjeta blanca** sobre `#F5F7FA`, con
  portada de 232 px y avatar de 132 px montado sobre ella. Se probó una
  cabecera de índigo profundo con la identidad en blanco y **se descartó**
  (decisión de Tomás, 2026-09-04): el bloque de marca queda para el anuncio y
  el CTA del inicio, no para el perfil.
- **Emprendimientos, reseñas y ferias van en pestañas** (pastillas sobre
  `#ECEAF7` la activa), no apiladas: hoy la página se hace larguísima.
- **Los tres datos que deciden van juntos y arriba**: dónde queda, si está
  abierto ahora y cuánto puntúa. El botón de mensaje no vive al final del
  scroll.
- **El cliente no tiene portada** y su avatar es de 96 px: un cliente no es un
  negocio y el perfil no tiene que aparentarlo.
- **"Tus números"** son los cuatro de `consultas.estadisticas_de_usuario`. La
  variación del mes (`+18%`, `+9`) **no la calcula nada todavía**: es una
  propuesta.
- **El interruptor "Ver como visitante"** apaga de verdad números, botones de
  editar y "Sigo a". La app no dice en ningún lado que estás viendo tu propio
  perfil ni qué ves de más.

### Teléfono: menos, no lo mismo más angosto

Decisión de Tomás: en 390 px las pantallas quedaban llenas. Tres reglas:

- **Los horarios son una fila que se despliega** ("Abierto ahora · cierra
  19:00" + `<details>`), no siete filas abiertas. Se ahorran ~300 px que nadie
  pidió.
- **El mapa sale del flujo**: queda un renglón con la dirección y la distancia
  que abre el mapa aparte. El bloque de 140 px no aportaba nada tocable.
- **Cada pestaña muestra dos ítems** y manda el resto a su pantalla con un
  botón. Lo mismo con "Tus números" de la dueña: dos en la fila y los cuatro
  detrás del desplegable.

### Qué NO existe en la app

- La variación mensual de "Tus números".
- "Lo que más le piden" es una consulta nueva sobre `products`.
- Que un cliente tenga **sólo sus reseñas como público**: es una decisión de
  este diseño, no una regla que el código aplique hoy.

### El perfil, pasado a código (2026-09-05)

Lo que del canvas quedó andando en la app, en `app/perfil/` y en los dos
archivos estáticos. La primera tanda (23:00 del 04) dejó hecho lo de abajo y
paró antes de las dos últimas piezas; ésta las cerró.

De la primera tanda: **"Lo que tenés en curso"** (turnos y presupuestos del
dueño, tres de cada uno, `reglas.turnos_en_curso` y
`reglas.presupuestos_en_curso`), las **pestañas** (`[data-perfil-tabs]` en
`main.js`, la barra nace con `hidden` y la enciende el JS), el **hueco de
"todavía no publicaste" dicho como invitación** (`.perfil-vender`), y los
**plegables de teléfono** para la semana de horarios y el mapa
(`[data-plegar-en-movil]`, con el `resize` que le avisa a maplibre cuando se
abre adentro de un `<details>` cerrado).

De esta tanda:

- **Las reseñas son la tercera pestaña.** Estaban sólo en
  `/perfil/<slug>/resenias`: la prueba de que a este emprendimiento ya le
  compraron quedaba a un click, justo cuando el visitante está decidiendo. Van
  las últimas tres (`reglas.MAX_RESENIAS_EN_EL_PERFIL`) con el resumen de
  **todas** al costado, y el pie lleva a la página completa, que sigue
  existiendo paginada. Las tarjetas reusan `review-card` y la distribución
  `distribucion__*` de `/resenias` sin tocarlas: es la misma cosa en otro lado
  y tiene que verse igual. **Responder no va acá** — es una pantalla de
  trabajo, no del perfil. La pestaña se dibuja con la misma condición que su
  panel: un botón sin panel detrás queda vivo en la barra y no hace nada,
  porque el JS lo saltea al no encontrar el destino.
- **"Ver como visitante" es una URL, no un interruptor de JS.** `?ver=visitante`
  sobre el perfil propio. Se eligió así porque el estado queda compartible,
  marcable, vuelve con el botón de atrás y funciona sin JS.
- **Y apaga de verdad.** El corte está en `vistas.py`, no en el template: con
  el parámetro puesto, `es_dueño` es `False` y las estadísticas, los turnos y
  los presupuestos **ni se consultan**. La vista previa no es un dibujo, es la
  misma consulta que corre para un visitante. De paso, `es_dueno` dejó de
  calcularse en el template (`{% set es_dueno = g.user and ... %}`) y lo manda
  la vista: la cuenta vive en un solo lado, que es lo que hace que apagar sea
  confiable.
- **El perfil de un cliente cambia de forma.** Rol `usuario` y sin
  emprendimientos publicados: sin portada, avatar de 96 px en vez de 112 (sin
  portada no pisa nada, así que también pierde el margen negativo) y sin la
  tarjeta "Horarios de atención", que para el dueño era una invitación a llenar
  algo que no atiende a nadie. **Dos cosas se respetan igual**: si subió una
  portada, va —la cargó a propósito—, y si ya tiene horarios cargados, se
  siguen mostrando. Se pide el rol Y que no haya publicado nada, porque si un
  "usuario" tiene emprendimientos el que está equivocado es el rol, y quedarse
  con la forma de negocio es lo que no rompe la pantalla.
- **La barra usa `es_dueno_real`** y no `es_dueno`, porque tiene que seguir
  viéndose mientras la vista previa está prendida: si no, no habría desde dónde
  volver.

**Medidas y color.** La barra va sobre `--color-primary-soft` y no sobre el
índigo profundo de los paneles: es un aviso permanente, no un bloque de marca,
y dos bloques oscuros pegados a la portada quedaban peleando. La variante
`--previa` sube el borde a `--color-primary`, porque mientras mirás recortado
esa barra es el único cartel que lo dice. El resumen de reseñas es una columna
de 240 px que cae arriba de la lista abajo de 960 px, el mismo corte que usan
los plegables de teléfono.

**Verificado**: la suite queda en **851 en verde** (832 antes de la tanda del
perfil), y las dos vistas probadas contra el servidor con sesión iniciada — la
normal muestra "Tus números" y "Lo que tenés en curso", la previa no muestra
ninguno de los dos y sigue ofreciendo "Volver a mi vista".

### Lo que del perfil NO se pasó, y por qué

- **La variación mensual de "Tus números"** (`+18%`, `+9`). No hay con qué
  calcularla: `estadisticas_de_usuario` da el total de hoy y no hay histórico.
  Es una propuesta del canvas y sigue siéndolo.
- **"Lo que más le piden"**. Es una consulta nueva sobre `products` que todavía
  no existe.
- **La mitad del perfil del cliente que el canvas propone como listas propias**:
  turnos, presupuestos, reseñas escritas, guardados y a quién sigue como cinco
  bloques. En la app hay tres de esos cinco y en otra forma —"Lo que tenés en
  curso" funde turnos y presupuestos, y guardados y seguidos siguen viviendo en
  sus pantallas—, que alcanza para que el perfil no esté vacío. Partirlo en
  cinco secciones es la tanda que sigue.
- **Que de un cliente sólo sean públicas sus reseñas**. Es una decisión del
  diseño, no una regla que el código aplique hoy.

---

## Ajustes: editar el perfil (2026-09-05)

El canvas está en `disenio-ajustes/` (siete artboards, dos páginas). Reemplaza
al formulario único de `/perfil/edit`: diez controles en una sola columna —las
dos fotos como `<input type=file>` pelados, la biografía, los dos teléfonos,
las tres redes y las dos ubicaciones— con el botón de guardar al final del
scroll.

**La estructura.** Ajustes pasa a ser una sección con solapas de verdad, y los
ocho campos se reparten por lo que responde cada grupo:

- **Perfil público** (`/perfil/edit`): fotos, biografía y las dos ubicaciones.
- **Contacto y redes** (`/perfil/edit/contacto`, ruta nueva): los dos teléfonos
  y los tres links. Se cargan una vez y no se vuelven a tocar, pero estaban
  entre la biografía y la dirección, que son las dos que sí se editan seguido.
- **Horarios** (`/perfil/horarios`): deja de ser una tarjeta suelta de 640 px
  fuera del menú de cuenta y entra como una solapa más.

`formulario.leer_perfil()` se partió en `leer_perfil_publico()` y
`leer_contacto()`; `campos_guardados()` sigue devolviendo los ocho, porque las
dos pantallas pintan la misma vista previa.

**Lo que cambia adentro de cada una:**

- **La vista previa** (`partials/_ajustes_previa.html`), fija a la derecha.
  Editar el perfil era escribir a ciegas y salir a mirar. Se pinta en el
  servidor desde `campos` —así existe sin JS y, al volver por un error, muestra
  lo que la persona escribió y no lo viejo de la base— y `main.js` le va
  acompañando la biografía y la ciudad mientras se escribe. La bio entra por
  `textContent` y no por `innerHTML`: el markdown lo renderiza el servidor al
  guardar, y meterlo como HTML sería ejecutar lo que se escriba en el campo.
- **Las fotos muestran la que hay cargada.** Y se pueden **quitar**
  (`quitar_avatar` / `quitar_cover`), que antes no se podía: se cambiaba la foto
  pero no se volvía a no tener ninguna. Subir le gana a quitar. La columna queda
  en `None` y el archivo no se borra, como el resto de los uploads viejos.
- **Ciudad y dirección dejan de confundirse**: cada una lleva su pastilla
  encima («Solo texto» / «Mueve el mapa») en vez de un texto de ayuda que se
  leía después de equivocarse. Y **la geocodificación deja de ser muda**: si la
  dirección guardada no tiene coordenadas, el campo lo dice cada vez que se
  entra, no una sola vez al guardar.
- **El error del teléfono se dibuja EN el campo**, con `aria-describedby`.
  Volvía como un aviso suelto arriba de todo y había que adivinar cuál de los
  diez campos lo había producido. El mensaje se filtra de la lista de flashes
  para no decirlo dos veces (empieza con «El teléfono» o «El WhatsApp», y eso
  es lo que decide en qué campo se dibuja).
- **Guardar es una barra fija** con el estado. Nace diciendo «Todo guardado»
  desde el HTML (que es cierto al entrar) y `main.js` la tiñe al primer cambio.
  Sin JS queda el texto de arranque y el botón, que es lo que había.
- **Horarios**: el checkbox «Cerrado» del final es un interruptor que apaga su
  fila, y al costado se ve el cartel que las siete filas encienden en el perfil.
  Dos atajos (`Copiar el lunes`, `Cerrar sábado y domingo`) hacen el trabajo
  repetido; nacen con `hidden` y los enciende el JS, porque sin él no harían
  nada y un botón muerto es peor que ninguno.

**El interruptor no cambió el backend.** Sigue siendo el mismo
`<input type="checkbox" name="cerrado_N">` de siempre: lo que se invierte es el
color (encendido = abierto, que es como se lee un interruptor) con
`:checked + .sr-only + .interruptor__pista`. El nombre accesible sigue diciendo
lo que el control hace al marcarse («Cerrado el lunes»).

### El bug que apareció de paso: los campos sin recuadro

El rediseño de entrar/crear cuenta le pasó el borde a `.auth__campo` —que
envuelve al input junto con el ícono y el ojo— y dejó a `.auth__input` sin
borde, sin fondo y sin padding. Pero esa clase la usan **trece formularios
más** que nunca tuvieron ese envoltorio (eventos, productos, servicios, turnos,
reportes, la bio, editar perfil): ahí los campos quedaron sin recuadro, texto
suelto sobre la tarjeta.

Se arregló invirtiendo el default: `.auth__input` vuelve a ser la caja, y
`.auth__campo .auth__input` la apaga cuando el borde ya lo pone el envoltorio.
Así ninguno de los dos grupos depende de que el otro se acuerde de algo.

### Lo que NO se pasó, y por qué

- **Cuenta y contraseña.** No hay nada detrás: `views/auth.py` tiene register,
  login y logout, y ninguna ruta para cambiar la contraseña ni el correo, ni
  para cerrar la cuenta. La advertencia del nombre de usuario que dibuja el
  canvas (cambiarlo cambia el slug y rompe los links compartidos) **sí es
  real**, y es lo primero que valdría la pena pasar.
- **Notificaciones.** Los tres avisos existen (`services/notificaciones_email.py`)
  pero no hay dónde guardar la preferencia: hace falta una columna o una tabla
  y que los tres envíos la consulten.
- Las dos siguen dibujadas y apagadas en la barra de solapas, con el aviso
  abajo, que es la regla del resto del proyecto.

**Verificado**: la suite queda en **862 en verde** (853 antes de esta tanda), y
las tres pantallas probadas contra el servidor con sesión iniciada.

---

## Servicios (2026-09-05)

El canvas está en `disenio-servicios/` (siete artboards, dos páginas). Cubre las
cinco pantallas que quedaban con el diseño viejo: buscar, pedir presupuesto,
mis servicios, nuevo/editar y verificar. Presupuestos y el detalle del pedido ya
estaban rediseñados y no se tocan.

**Los servicios no tienen foto.** `Service` no tiene columna de imagen, así que
la ficha no puede usar `.tarjeta` tal cual (que reserva 232 px para la foto del
emprendimiento). En su lugar va un **emblema del oficio**: un cuadrado de 84 px
(44 en teléfono) con el índigo lavado de fondo y un ícono de línea del rubro
dibujado en SVG, sobre la grilla de 24. Un hueco gris con un iconito adentro se
lee como carga rota; el emblema se lee como categoría.

**Los 13 rubros de servicio no son los 7 del emprendimiento.** `Rubros` en
`app/servicios/modelo.py` es un catálogo aparte (plomería, gas, herrería…) y no
tiene paleta: la de la guía es para `Categorias`, que son otra cosa. Acá van
todos en `--color-primary-soft` y el rubro se distingue por el ícono, no por el
color. Trece pares de fondo + tinta que pasen AA no valen el esfuerzo para una
lista que además se filtra.

**El filtro es la columna de Emprendimientos**, la que ya existe en el CSS
(`.explorar` 276 px + `.filtros`), y no la fila de tres campos de hoy. De los 13
rubros se muestran los que tienen a alguien, con el conteo al lado, y el resto se
despliega: trece renglones en 276 px son una lista, no un filtro.

**"A presupuestar" es un estado, no un renglón.** `precio_estimado` en NULL es lo
que distingue esta tabla de `products`, así que tiene su propio filtro y su propia
tipografía (más chica y en `--color-text-soft`, contra el precio cerrado en 18 px
y `--color-text`).

**La fila de Mis servicios reemplaza a la tarjeta.** Se agrupan por
emprendimiento, con el cupo (`MAX_SERVICIOS_POR_POST`, 50) visible antes de que
te lo rechace. Dos cosas que la fila dice y hoy no se ven en ningún lado:

- **Los cuatro estados de la verificación.** Hoy la tarjeta sabe decir
  "Verificado" o nada; `VerificationRequest` tiene PENDIENTE y RECHAZADA y no se
  muestran. La cola del admin los escribe y el dueño no se entera hasta que entra
  a `/servicios/<id>/verificar`.
- **El interruptor de Disponible.** Es lo único de esta tanda que necesita
  backend nuevo: un POST chico (`/servicios/<id>/disponible`). Hoy apagar un
  servicio obliga a abrir el formulario de ocho campos y guardar los ocho.

**La duración del turno no existe hasta que se prenden los turnos.** Hoy el campo
está siempre y dice "obligatorio si tomás turnos", que hay que leer para saber si
te toca. Los topes del canvas son los de `reglas.py`: 5 a 480 minutos, con
30/45/60/90 como pastillas y el campo libre al lado.

**Verificar deja de ser cuatro párrafos.** Los tres pasos (subís, lo mira un
admin, aparece el sello) están siempre arriba y marcan en cuál estás, y el motivo
del rechazo se dibuja al lado de la foto que mandaste: hoy son un alert y una
imagen suelta, y rehacerla es adivinar qué se veía mal.

### Lo que el canvas dice y la app no

Dos textos nuevos, los dos al costado de Verificar: qué papel sirve (matrícula
con el número visible, certificado del rubro, habilitación municipal) y qué
significa el sello — que alguien de IMPULSAR miró un papel, no que el trabajo
esté garantizado. Es la parte que hoy no está escrita en ningún lado y es la que
decide si el sello vale algo para quien lo mira.

| Qué | Dónde |
| --- | --- |
| Artboards de servicios | `disenio-servicios/*.dc.html` + `canvas.json` |
| Canvas publicado | https://claude.ai/code/artifact/069e1492-b8cb-4c58-8cf0-b036dc06e7c2 |

### Servicios, pasado a código (2026-09-05)

Las cinco pantallas del canvas están en la app. Lo que se tocó:

| Qué | Dónde |
| --- | --- |
| Buscar servicios | `app/servicios/templates/servicios/buscar.html` |
| Mis servicios | `app/servicios/templates/servicios/index.html` |
| Nuevo / editar | `app/servicios/templates/servicios/form.html` |
| Pedir presupuesto | `app/servicios/templates/servicios/solicitar.html` |
| Verificar credenciales | `app/servicios/templates/servicios/verificar.html` |
| Los íconos de los 13 oficios | `templates/partials/_icono_oficio.html` |
| Estilos | `static/css/styles.css`, bloque "SERVICIOS (2026-09-05)" |
| Previa del formulario | `static/js/main.js`, al final |

**Los filtros son enlaces, no un formulario.** Rubro, precio y el interruptor de
verificados cambian un parámetro de la URL y recargan; solo la zona es un
`<form>`, porque hay que escribirla. Así la búsqueda entera se puede compartir,
se vuelve con el botón de atrás y —lo que decide— funciona sin JavaScript. Es
el mismo criterio que ya usaban las fichas de "Abierto ahora" y "Con reseñas"
del listado de emprendimientos.

**El conteo al lado de cada rubro no se filtra a sí mismo.**
`consultas.conteos_por_rubro()` aplica todos los filtros MENOS el rubro: el
número tiene que decir cuántos hay en Electricidad mientras estás parado en
Plomería, que es lo que lo hace servir para decidir a dónde ir. Los filtros
viven en `_filtrar_busqueda()`, compartida con la búsqueda, para que el
contador no pueda desincronizarse de lo que el rubro va a devolver.

**El filtro de precio no es un rango de plata.** Son los dos estados que de
verdad separan a los servicios: con precio publicado, o a presupuestar
(`precio_estimado` en NULL, que es lo que distingue esta tabla de `products`).

**El orden por defecto cambió**: era por emprendimiento y título, ahora es por
fecha descendente (`reglas.Ordenes.RECIENTE`), con "Nombre (A-Z)" como la otra
opción. Lo último cargado es lo que todavía nadie vio, y por título "Aberturas"
quedaba primero para siempre. Los dos órdenes desempatan por id: sin eso, dos
servicios del mismo segundo pueden salir en distinto orden en cada consulta y
en una lista paginada eso significa una fila repetida o una que no aparece
nunca.

**"Mejor puntuados" no se pasó**, aunque el canvas lo dibujaba: el promedio de
reseñas es del EMPRENDIMIENTO, no del servicio, así que ordenaría los servicios
de uno por una nota que no es suya. Por el mismo motivo la ficha no muestra
estrellas.

**La fila de Mis servicios dice dos cosas que antes no se veían**: el estado del
último pedido de verificación (`consultas.estados_de_verificacion()`, una
consulta para todos y no una por fila) y el cupo por emprendimiento
(`MAX_SERVICIOS_POR_POST`), que antes se conocía recién cuando el alta lo
rechazaba.

**Backend nuevo: `POST /servicios/<id>/disponible`.** Es lo único de la tanda
que no existía. Apagar un servicio obligaba a abrir el formulario de ocho
campos y volver a guardarlos todos, con el riesgo de pisar algo de paso. Es un
form de un botón y no un checkbox con JavaScript, por lo mismo que los filtros.

**La previa del formulario se pinta en el servidor** y `main.js` la va
acompañando, igual que la de Ajustes: así existe sin JS y, al volver por un
error, muestra lo que la persona escribió y no lo viejo de la base. Los trece
íconos van dibujados y escondidos en el HTML porque el marcado vive en las
plantillas; el JS solo muestra el del rubro elegido.

**El campo de duración del turno nace visible** y lo esconde el JS cuando los
turnos están apagados. Al revés —nacer oculto— dejaría, sin JavaScript, un
campo obligatorio que no se puede completar.

### Lo que de servicios NO se pasó, y por qué

- **Las estrellas y la reputación en la ficha.** Ver arriba: la nota es del
  emprendimiento.
- **"Abierto ahora" en la ficha de la búsqueda.** El dato existe
  (`services/horarios.py`) pero es del emprendimiento y calcularlo por fila en
  una lista paginada es una consulta por resultado. Cuando se cablee, va con el
  mismo helper que usa el inicio.
- **El aviso de "no cargaste horarios" del formulario** quedó como el texto
  genérico que ya estaba, sin consultar si la persona tiene horarios: eso es
  otra consulta y el canvas lo dibujaba como si el dato estuviera.

**Verificado**: la suite queda en **873 en verde** (862 antes de esta tanda:
once tests nuevos y dos actualizados). Los dos que se actualizaron lo fueron a
propósito y no para que pasaran: `test_la_busqueda_pagina` daba por sentado el
orden alfabético viejo, y el del checkbox de verificados probaba un control que
ahora es un enlace con `aria-pressed`.

---

## Favoritos (2026-09-05)

Sin canvas: la pantalla no necesitaba un diseño nuevo sino entrar al que ya
existe. Era la única de las cinco del menú de cuenta que seguía con
`.section__header` y la grilla de `.card` genéricas, al lado de Mis
emprendimientos, Mis servicios y Reseñas recibidas, que ya estaban
rediseñadas.

- Pasa al layout `.cuenta` con el menú a la izquierda, igual que sus hermanas.
- Las fichas son las mismas `.tarjeta` del listado de emprendimientos, con la
  pastilla del rubro, el corazón, el promedio y el autor. Es la misma ficha que
  la persona ya vio al marcar el favorito: no hay motivo para que se vea
  distinta acá.
- **El orden dejó de ser un `<select>` y pasó a ser dos enlaces**, como en la
  búsqueda de servicios: son dos opciones, y desplegar un select para elegir
  entre dos es un paso de más. El rubro sigue siendo un `<select>` con
  `onchange` (siete opciones) y su botón "Aplicar" de fallback para quien tenga
  JS apagado.
- El vacío usa el `.vacio` de servicios, y distingue los dos casos que ya
  distinguía: sin favoritos, o sin favoritos EN ESE RUBRO.

Se actualizaron tres tests de `tests/test_favorites.py` que leían el marcado
viejo: el helper que sacaba los títulos buscaba `<h3 class="card__title">`, y
dos que verificaban que el orden volviera con `selected` ahora miran
`aria-current` en el enlace activo.

---

## El chat (2026-09-05)

Sin canvas, como Favoritos: las dos pantallas ya existían y lo que faltaba era
que entraran al diseño del resto.

**La bandeja** (`templates/messages/inbox.html`) pasa al layout de cuenta y cada
conversación es una fila con avatar. Los tres datos que se agregan salen de lo
que la consulta ya traía, así que no hay ninguna consulta nueva:

- **De qué lado estás**: «le escribís como cliente» o «te escribieron a tu
  emprendimiento». Es lo que decide con quién estás hablando, y antes había que
  deducirlo del nombre.
- **La fecha** del último mensaje.
- **Sin leer**: el punto índigo y el fondo teñido, cuando el último mensaje es
  de la otra parte y no tiene `read_at`. Antes la única forma de saber si te
  habían contestado era abrir las conversaciones una por una. Los propios no se
  marcan: nacen sin `read_at` y decir que tenés algo pendiente con vos mismo no
  significa nada.

La vista previa va a una sola línea con puntos suspensivos: sirve para
reconocer la conversación, no para leerla.

**La conversación** (`templates/messages/conversation.html`) pasa a ser una
ventana de chat: cabecera con la otra parte y el emprendimiento del que se
habla, el historial en el medio con alto mínimo, y el campo de escribir abajo,
todo dentro de la misma caja. Antes eran tres bloques sueltos separados por
márgenes.

**Lo que NO se tocó es el cableado.** El div del historial conserva su `id` y
sus tres `data-*`, el `<script>` con el JSON del historial queda igual, y las
burbujas conservan sus clases (`.chat-message` y sus dos modificadores):
`static/js/chat.js` las escribe, así que renombrarlas las habría dejado sin
estilo y habría roto el polling. Lo que cambió es el CSS de esas clases: cada
burbuja muerde la esquina de su lado, para que se lea quién dijo qué sin
depender solo del color.

---

## Auditoría de la tanda del inicio (2026-09-05)

Lo que salió de revisar el inicio ya pasado a código. Lo medido, para no
volver a discutirlo:

- **La consulta de `/api/posts/` no tiene N+1 ni duplica filas.** Usa el mismo
  `query_posts_con_rating()` que el listado — outerjoin contra una subquery
  agrupada por `post_id`, así que un emprendimiento con cinco reseñas sigue
  siendo una fila. Medido vaciando el *identity map* antes de la request: **2
  consultas fijas** (el SELECT y el `count(*)` del paginado) con 5, 20 y 40
  emprendimientos. `author_name` no suma ninguna porque `Post.author_user` es
  `lazy="joined"`.
- **El shape de la respuesta es aditivo.** Aparecen `avg_rating`,
  `review_count` y `author_name`; no desaparece ninguna clave, las de primer
  nivel del paginado quedan igual y `favorito` sigue sin viajar cuando no hay
  sesión. El único consumidor es `static/js/main.js`.
- **Los siete pares de rubro pasan AA en los dos temas**: 4,64:1 a 5,11:1 en
  claro y 5,68:1 a 7,00:1 en oscuro, calculados con la fórmula de WCAG. El
  blanco al 72 % del conteo de "Ver todo" sobre el panel da 6,15:1.
- **La grilla de rubros no puede quedar coja.** El bucle es sobre
  `Categorias.ETIQUETAS` (los siete, siempre) y el conteo entra con
  `.get(clave, 0)`, así que un rubro en cero dibuja su ficha igual y dice
  "0 activos". Con la octava ficha de "Ver todo" son 8 celdas: 4x2 exactas.

### Lo que hubo que arreglar

- **Tres controles nuevos no llegaban a los 44 px en teléfono.** "Cerca de mí"
  medía 34, los dos botones sobre la foto 38x38 y el "Ver" del pie 32. Los
  valores del artboard son de escritorio y ahí están bien; el piso de 44 se
  aplica en la media query de 860 px y sólo ahí. Verificado midiendo dentro de
  un iframe de 390 px (la media query mira el `innerWidth` del documento, así
  que redimensionar la ventana no sirve).
- **La pastilla del rubro no se anunciaba.** Estaba dentro del
  `<a class="tarjeta__foto" aria-hidden="true">` — ese enlace es un duplicado
  del título y por eso se esconde, pero se llevaba puesto el rubro. Pasó a ser
  hermano suyo, posicionado contra la tarjeta (que ya es `position: relative`)
  y con `z-index: 1`. En el listado no pasaba: ahí la pastilla vive en
  `.tarjeta__cuerpo`.
- **Las iniciales del avatar salían del nombre ya escapado.** `escapeHtml(...)`
  y después `.slice(0, 2)` deja "&a" o "&l" en el círculo si el nombre empieza
  con `&`, `<`, `"` o `'`. Se corta el crudo y se escapa después, que es el
  orden del listado (`username[:2] | upper`).
- **CSS muerto del cambio de `.ficha` a `.tarjeta`.** Se fueron `.ficha` y sus
  nueve hijos, `.resultados__grid` y sus reglas de media query. Sobreviven
  `.ficha__rating` y `.ficha__estrella`, que `blog/detail.html` sigue pidiendo,
  y no se tocan `.ficha-filtro*`, `.fichas-filtro*` ni `.ficha-servicio*`, que
  son otras clases.

Nada de lo que pinta la tarjeta del inicio es inventado: sólo `avg_rating`,
`review_count` y `author_name`, los tres reales. "Abierto ahora", el barrio y
los km siguen fuera, como dice la sección de arriba.

La suite queda en **873 en verde**.

---

## Rediseño global 2026-09-06: dónde quedamos

Tanda nueva, a partir del pedido completo de rediseño UX/UI de Tomás (marketplace
familiar, identidad propia, `#3E2F94` como primario y `#665DF1` como legado).
**Todo esto es diseño aprobado y NADA está pasado a código todavía.**

Se trabaja **sección por sección**: se dibuja, Tomás la mira, se corrige hasta que
la aprueba, y recién ahí se pasa a la siguiente. Cuatro aprobadas.

### Las cuatro tandas, y dónde vive cada una

| Sección | Carpeta | Canvas publicado |
| --- | --- | --- |
| Navegación global | `disenio-navegacion/` | https://claude.ai/code/artifact/b752a01f-a2be-495c-b0cf-ac660dc65c84 |
| Ficha del emprendimiento | `disenio-ficha/` | https://claude.ai/code/artifact/423b9dbb-2c0d-4eb3-87e1-19bf140d1ace |
| Catálogo de productos | `disenio-productos/` | https://claude.ai/code/artifact/332d05a2-7ac7-4f03-a0fb-de90acf291e9 |
| Panel del vendedor | `disenio-panel/` | https://claude.ai/code/artifact/538a4d0a-52cb-4781-a7e6-717557523761 |

Cada carpeta tiene sus `*.dc.html`, su `canvas.json` con las notas de decisión, y
el `.html` sembrado que se publica. Para cambiar algo: se edita el `.dc.html`, se
vuelve a sembrar y se republica al MISMO archivo, que conserva la URL.

### 1. Navegación global (aprobada)

Reemplaza a la barra de `templates/base.html`.

- **Dos filas en escritorio.** Fila 1 (68 px): logo a la izquierda, las tres
  secciones **centradas al 50 % exacto** (posicionadas, no en grilla: con
  `1fr auto 1fr` el bloque de acciones es más ancho que el logo y corría la nav
  a la izquierda), y a la derecha Publicar, favoritos, mensajes, tema y avatar.
  Fila 2: **el buscador solo, centrado, 720 px de ancho y 52 px de alto**. Tenía
  que salir de la fila 1: ahí competía con el logo y las acciones.
- **Favoritos y Mensajes salen del menú** y pasan a ser íconos visibles. Hoy
  están a dos clicks y el badge de avisos vive escondido adentro del menú.
- **El badge deja de mentir.** `/mensajes/notificaciones` (`views/messages.py:186`)
  devuelve un `total` que suma mensajes + reseñas + presupuestos, y ese número se
  pega al ítem "Mensajes". El endpoint ya los da separados: **cada contador va en
  SU ítem**, y el del sobre de la barra es sólo `unread_messages`.
- **La zona se dice una vez por lugar.** Con sesión: el campo "dónde" del
  buscador, y una pastilla debajo del título de la página. Sin sesión: sólo el
  campo, con "Cerca de mí" adentro. Se probó con tres controles de ubicación
  (campo + "Elegí dónde buscar" + "Cerca de mí" suelto) y Tomás lo rechazó por
  repetido.
- **Se va el hamburguesa**: cinco pestañas abajo, Inicio · Explorar · Favoritos ·
  Mensajes · Perfil. **Publicar NO entra en la barra** — es acción de dueño y vive
  arriba de la pestaña Perfil; nada de botón flotante, que taparía una tarjeta.
- **Publicar tampoco entra en la barra de ESCRITORIO (2026-09-06).** Era el único
  botón lleno de la barra y se repetía en las seis tandas, aunque cada sección ya
  tiene su propio llamado; en la cartelera de eventos la misma acción llegó a
  aparecer tres veces en una pantalla. Pasa al **menú de la cuenta**, como primer
  ítem y en pastilla llena de 44 px, que es exactamente donde vive en el teléfono:
  las dos plataformas dicen lo mismo. De paso libera ~130 px en la fila 1, que era
  el espacio que apretaba contra la nav centrada.
  "Explorar" agrupa en el teléfono lo que en escritorio son tres entradas: es una
  asimetría a propósito, en 390 px no entran tres.
- **Turnos entra al menú de cuenta.** `/turnos/mios` y `/turnos/agenda` existen y
  no están en ningún menú (`templates/partials/_menu_cuenta.html` tiene ocho ítems
  y ninguno es turnos).
- Se van los emoji de la barra (luna, sol y el caret de texto): SVG de trazo 1,7,
  como manda la guía.
- "Quiero vender" se dibujó y **Tomás lo sacó**. "Acceder" es texto sin caja y
  "Crear cuenta" una pastilla llena de 42 px con sombra índigo; los botones
  primarios de la barra pasaron todos a `border-radius: 999px`, la misma forma
  que el "Buscar" del buscador.

### 2. Ficha del emprendimiento (aprobada)

Sale del `Ficha.dc.html` que ya existía en `disenio-inicio/` y nunca se pasó a
código. Reemplaza a `app/blog/templates/blog/detail.html` (466 líneas).

- **Anclas, no pestañas.** El pedido proponía `Inicio | Productos | Servicios |
  Reseñas | Información`. No van: la mayoría de los emprendimientos tiene dos o
  tres productos y ninguna reseña, así que tres de cuatro solapas abrirían vacías.
  En su lugar, una barra de anclas que se pega arriba y marca en qué bloque estás.
- Las **visitas** (`views_count`, real) viven en esa barra y no al lado del
  nombre: son dato del dueño, no ayudan a decidir.
- Se fue **"responde en el día"**: no hay ninguna métrica de tiempo de respuesta.
- Tercer artboard: **la ficha recién publicada vista por su dueña**, que es el
  estado en el que va a estar toda ficha nueva y hoy no está diseñado. Barra que
  avisa que estás parada en tu propia ficha, cada hueco explica por qué conviene
  llenarlo, y "Completá tu ficha" con cinco tareas contra campos que existen.
- **Productos y servicios son dos bloques distintos.** A la dueña se le muestran
  los dos siempre, aunque estén vacíos — si no, nunca se entera de que puede
  cargar servicios. A un visitante se le dibuja **sólo el que tiene algo adentro**,
  así un emprendimiento de puro servicio no muestra un "Lo que vende" en blanco.
  El vacío de servicios explica la diferencia: producto = precio cerrado,
  servicio = trabajo a pedido con presupuesto o turno.

**Lo que hoy está mal en `detail.html` y esta ficha corrige:**

- Las reseñas dicen **"Usuario #7"**: el nombre de quien escribió no se muestra.
- Las estrellas son glifos de texto, y hay un emoji de pin en cada servicio. Las
  dos cosas van contra la regla de iconografía.
- **Las ferias no aparecen**, aunque `Post.eventos` existe y es el dato que
  ninguna otra plataforma tiene.
- "Abierto ahora" no dice a qué hora cierra, y la distancia no se muestra aunque
  hay `latitude`/`longitude`.
- Las miniaturas abren el archivo suelto en `/static/uploads/`, no un visor.
- No hay ningún estado vacío pensado.

### 3. Catálogo de productos (aprobada)

**Es lo único de la tanda que necesita rutas nuevas.** Hoy `/productos/` es sólo
el panel privado del dueño (`views/products.py`, todo con `login_required`) y un
producto únicamente se ve incrustado en la ficha de su emprendimiento. Faltan
`/productos` (catálogo público) y `/productos/<id>` (detalle).

Tres cosas que el modelo decide y el diseño respeta:

1. **Una sola foto.** `Product.foto` es una columna, no una galería. La "galería
   de imágenes" del pedido no se puede dibujar sin mentir: el detalle muestra la
   foto grande con "Ampliar" y nada más.
2. **No hay categoría de producto.** `Product` no tiene rubro propio: se filtra
   por `Post.category`, los siete de siempre. Por eso el punto de color de cada
   tarjeta es el del rubro del negocio.
3. **No es una tienda.** El docstring del modelo lo dice: sin stock, sin
   variantes, sin carrito, sin pago. No hay "Comprar", ni cuotas, ni envío, ni
   "más vendido" — no existe ninguna métrica de ventas. **La acción es
   "Consultar por este producto"** y termina en el chat interno con el nombre del
   producto ya escrito (eso es un parámetro nuevo en la ruta de mensajes).

Filtros: rubro, precio desde/hasta (`Numeric(10,2)`, rango exacto), disponibles
(encendido por defecto), abierto ahora y radio en km. Enlaces que cambian un
parámetro de la URL, no un formulario, como ya hacen el listado y servicios.

El detalle contesta **dos** preguntas: qué es, y quién lo vende. En una plataforma
sin pagos ni protección al comprador, la confianza en la persona pesa igual que el
producto.

**Productos NO entra en la barra global (2026-09-06).** El canvas se había dibujado
con cuatro secciones — Emprendimientos · Productos · Servicios · Eventos y ferias —
y el cuarto ítem hizo que la nav, que va centrada al 50 % exacto, se montara encima
del botón Publicar. La nav aprobada son **tres**: al catálogo se entra desde
Emprendimientos y desde el buscador, y en la barra queda marcado "Emprendimientos".
Con tres ítems sobran ~35 px hasta el bloque de acciones. Panel y Turnos tenían el
mismo cuarto ítem: corregidos el 2026-09-06 (Panel/Main y Panel/Catalogo;
Turnos/Main, Turnos/Agenda y Turnos/Mios). En Turnos la sección marcada es
"Servicios" — el turno se saca desde un servicio.

**El filtro de precio se queda.** Se discutió sacarlo porque la venta la coordina
el vendedor, pero cada tarjeta muestra un precio que pone el emprendimiento
(`Product.precio`): el filtro sólo acota el rango, no fija nada.

**En el teléfono no hay botón Publicar, y está bien.** Vale la regla de la
navegación: Publicar no entra en la barra de pestañas ni como botón flotante
—taparía una tarjeta—, vive arriba de la pestaña Perfil.

### 4. Panel del vendedor (aprobada)

Junta seis pantallas que hoy viven sueltas: emprendimientos, catálogo, servicios,
presupuestos, turnos y eventos.

- **Arranca por lo que hay que hacer, no por los números.** "Lo que te está
  esperando" va primero, con los contadores que `/mensajes/notificaciones` ya
  devuelve separados. Sólo se dibuja lo que tiene algo pendiente: una fila que
  dice "0" es ruido, y sin nada pendiente la sección entera no aparece.
- **Los números son los cinco que la base sabe contar**, tal cual salen de
  `app/perfil/consultas.estadisticas_de_usuario`: suma de `views_count`,
  favoritos, promedio y cantidad de reseñas, y seguidores.
- **Sin variación mensual, sin sparklines, sin gráficos.** No hay histórico: la
  consulta da el total de hoy. El "+18%" del canvas del perfil sigue siendo una
  propuesta y acá no se dibuja. Si algún día se guarda una foto diaria de esas
  métricas, ahí entra un gráfico; hasta entonces, número y etiqueta.
- **El catálogo se agrupa por emprendimiento** porque `MAX_PRODUCTOS_POR_POST`
  (50) es por emprendimiento: un contador global no diría nada sobre el techo que
  se puede chocar. El aviso aparece a los 40, como ya decide `UMBRAL_AVISO_LIMITE`.
- **Backend nuevo, uno solo:** el interruptor de "sin stock" del catálogo, un POST
  chico igual al de `/servicios/<id>/disponible`. Hoy marcar un producto como
  agotado obliga a abrir el formulario entero y volver a guardar los cinco campos.
- En teléfono el panel vive adentro de la pestaña Perfil, sin menú lateral: cada
  emprendimiento abre su pantalla con catálogo, servicios y ferias adentro.

### 5. Turnos (dibujada, a revisar)

Canvas en `disenio-turnos/`: seis artboards (reservar, mis turnos y la agenda, cada
una con su teléfono). Reemplaza a las cuatro plantillas de `app/turnos/templates/`.

**Reservar deja de ser un campo de fecha a ciegas.** Hoy es un `<input type="date">`
con "Ver ese día" y, abajo, una fila de botones sueltos donde **cada botón es un
submit**: hay que adivinar qué día tiene lugar, y un click de más ya reserva. Ahora
hay una tira de siete días con lo que tiene cada uno, y un paso de confirmación.

- **Es lo único de la tanda que pide backend nuevo**, y es barato: hoy
  `consultas.slots_disponibles()` calcula UN día y la tira pide los siete. El corte
  (`reglas.cortar_en_slots`) ya es puro y las horas tomadas salen de una consulta
  por rango en vez de una por día.
- **Los slots ocupados se dibujan apagados** en vez de desaparecer. Hoy
  `slots_disponibles()` los filtra, y cuatro horas sueltas sin explicación se leen
  como que el negocio casi no atiende. El dato ya lo tiene `horas_tomadas()`.
- **Los seis vacíos de `slots_disponibles()` son tres mensajes distintos** para quien
  mira: "ese día no atiende" (cerrado o sin horario cargado), "no queda ningún
  horario" (todo tomado) y "este servicio no toma turnos".
- **El turno queda confirmado al reservarse y se dice en pantalla.** `EstadosTurno`
  tiene sólo `ACTIVO` y `CANCELADO`: no hay pendiente ni confirmado, y el diseño no
  dibuja una confirmación que nadie da.
- **No hay antelación mínima**: `descartar_pasados` corta por hora de inicio, así que
  el turno de las 15:00 se puede reservar 14:59. El diseño no promete otra cosa.

**Mis turnos se parte en próximos y pasados.** `turnos_de_cliente()` ordena por fecha
DESC y mezcla todo: lo primero que se ve hoy es el turno más viejo del historial y el
de mañana queda al final. Además:

- **Cancelar pide confirmación, y en la misma fila**, con las dos consecuencias
  reales: se libera el horario y sale un mail (`notificar_turno_cancelado`). Hoy es
  un botón que hace el POST de una, y cancelado no se revierte.
- El cancelado dice **de qué lado salió** (`cancelado_por`): "lo cancelaste vos"
  contra "lo canceló el prestador".
- **Se va el botón cruzado "Turnos que recibí"**: la agenda del vendedor ahora vive
  en el panel. Son dos cabezas distintas, y así lo dice el docstring de `agenda()`.

**La agenda es un día, no una lista de tarjetas.** Hoy `/turnos/agenda` usa el mismo
macro que "mis turnos", ordenado por fecha DESC. Se elige el día en la semana de
arriba y abajo va ese día completo, **con los huecos dibujados**: son lo que todavía
se puede reservar. La grilla no puede ser de slots fijos porque cada servicio tiene
su duración y todos se cortan del mismo horario de la persona, así que los turnos se
apoyan sobre el rango de atención. **No hay "cumplido" ni "ausente"**: esos estados no
existen y dibujarlos sería inventar una columna.

| Qué | Dónde |
| --- | --- |
| Artboards de turnos | `disenio-turnos/*.dc.html` + `canvas.json` |
| Canvas publicado | https://claude.ai/code/artifact/5566643c-7638-485f-85e7-36cf609cfc55 |

Los cinco artboards estáticos no tienen comportamiento; el de reservar sí: la tira de
días y los horarios se eligen de verdad, para poder probar el paso de confirmación.

### Dos cosas aprendidas en el teléfono

- **Nada se desliza de costado.** La tira de productos de la ficha móvil cortaba
  la tercera tarjeta contra el borde de los 390 px y se leyó como que la pantalla
  se desbordaba. Pasó a grilla de dos columnas + un enlace "Ver los 8". Lo mismo
  con los filtros del catálogo: seis chips en fila no entran, así que son un botón
  "Filtros (2)" que abre una hoja desde abajo.
- Los artboards de teléfono llevan `* { box-sizing: border-box }` y
  `overflow-x: hidden` en la raíz, como red.

### Lo que sigue

En este orden, y por este motivo:

1. ~~**Turnos**~~ — dibujada el 2026-09-06, esperando revisión (arriba, punto 5).
2. ~~**Eventos y ferias**~~ — dibujada el 2026-09-06 (abajo, punto 6). **La nota
   anterior decía "sin tocar" y estaba mal**: `templates/eventos/index.html` y
   `form.html` salieron de la tanda de agosto y están en código; lo que faltaba
   era pasarlas al lenguaje de esta tanda.
3. ~~**Panel administrativo**~~ — dibujada el 2026-09-06 (abajo, punto 7). **La nota
   anterior decía "cinco plantillas viejas" y era medio cierta**: tres ya tenían el
   rediseño de agosto; las que faltaban eran Reportes y Verificaciones.
4. ~~**Las páginas planas y las de error**~~ — dibujadas el 2026-09-06 (abajo,
   punto 8).
5. **Pasar las tandas aprobadas a código.** Es lo único que queda de verdad: ocho
   tandas dibujadas y ninguna en la app.

`disenio-navegacion/`, `disenio-ficha/`, `disenio-productos/`, `disenio-panel/` y
`disenio-turnos/` **todavía no están commiteadas**: quedaron afuera del commit `27d1710` a pedido
propio, mientras Tomás las revisaba.


### 6. Ferias y eventos (dibujada 2026-09-06, a revisar)

| Qué | Dónde |
| --- | --- |
| Artboards | `disenio-eventos/*.dc.html` + `canvas.json` |
| Canvas publicado | https://claude.ai/code/artifact/c24946a2-195e-4b54-80cc-8bf8fa82c5d6 |

Cinco artboards: cartelera y publicar en escritorio, y cartelera, hoja del día y
publicar en teléfono. **El calendario de la cartelera de escritorio funciona**:
navega los meses y al elegir un día filtra la lista de al lado.

Del código se respeta todo lo que ya decidió `models/event.py`: la fecha es `Date`
y la hora va aparte y es opcional, `lugar` es columna propia y nullable (la feria
de una panadería no es en la panadería), no hay borrador, y la lista se agrupa por
mes con `services/eventos.agrupar_por_mes()`.

**Tres campos dibujados que la base NO tiene**, en orden de lo que cuestan:

1. **Entrada libre** — un booleano. Usa el par de "abierto ahora"
   (`#E6F4EC` / `#1F7A4D`): significa lo mismo, un estado bueno y binario.
2. **Tipo de evento** — Feria · Taller · Pop-up · Encuentro. Columna nueva y
   migración chica; lo caro es cerrar la taxonomía, porque después no se cambia sin
   re-etiquetar lo cargado. **Los cuatro van en índigo lavado y se distinguen por el
   ícono, no por el color**, igual que los 13 rubros de servicio: una taxonomía
   nueva no se gana una paleta categórica.
3. **Me interesa / interesados** — no es una etiqueta, es una feature entera: tabla
   usuario × evento, ruta, permiso, y decidir si el dueño ve quiénes son. Los
   números que se ven en las tarjetas son inventados. Si hay que recortar algo de
   los tres, es éste.

**El calendario pasa de ilustración a filtro.** Hoy `partials/_calendario.html`
pinta los días con eventos contra `/api/eventos?mes=AAAA-MM` y ahí termina. Elegir
un día puede ser un parámetro de la URL (`?dia=AAAA-MM-DD`), como los filtros del
catálogo: se comparte, vuelve con el botón de atrás y anda sin JS. **No hace falta
ningún dato nuevo** — el endpoint ya devuelve el mes.

**Dos vacíos distintos, no uno.** "Todavía no hay eventos anunciados" es cierto con
la base vacía y mentira cuando el día elegido no tiene nada; el segundo dice cómo
salir del filtro.


### 7. Panel de administración (dibujada 2026-09-06, a revisar)

| Qué | Dónde |
| --- | --- |
| Artboards | `disenio-admin/*.dc.html` + `canvas.json` |
| Canvas publicado | https://claude.ai/code/artifact/79f57360-70eb-468d-802b-054dfa9bbf44 |

Cinco artboards: Resumen, la cola pendiente, Usuarios, Emprendimientos y la cola en
teléfono.

**De las cinco plantillas, tres ya tenían el rediseño de agosto** (dashboard,
usuarios y emprendimientos: menú lateral, tabla, buscador y paginado reales).
**Reportes y Verificaciones se quedaron afuera**: siguen con `.section__header`, una
tabla pelada, estilos inline y **sin el menú del panel**, aunque el menú les enlaza
— entrás a Reportes y perdés la navegación. Por eso el artboard de la cola es el
central de la tanda: no es pintura, es la pantalla que hoy no existe con la forma
del resto.

- **La cola es una pantalla, no una tabla.** Una verificación se resuelve mirando un
  documento y escribiendo un motivo; hoy eso vive en un `<textarea rows="1">`
  apretado en la columna "Acción". Pasa a ficha por ítem, con el documento en su
  propia caja. El motivo sigue viajando en el MISMO envío que el rechazo, como ya
  decidió el código.
- **Sin foto es un estado, no un hueco.** `foto` es nullable y hoy la celda dice
  "Sin foto" en gris. Ahora el botón de aprobar se apaga —no hay nada que mirar, no
  hay nada que aprobar— y el rechazo trae el motivo ya escrito.
- **Un solo número grande por pantalla.** El Resumen lidera con lo pendiente a 60 px
  y las tres métricas van abajo a 30. **Sin flecha de tendencia ni sparkline**: la
  consulta da el total de hoy y el alta de cada fila, no hay histórico. "+47 en 30
  días" va en tinta apagada porque es un conteo, no un bueno-ni-malo.
- **`tabular-nums` en columnas, cifras proporcionales en los números grandes.** A 30
  y 60 px las tabulares quedan flojas; en una columna de fechas son lo que las
  alinea.
- **El estado nunca se dice sólo con color**: cada pastilla lleva ícono y palabra, y
  la fila entera se tiñe. En veinte filas, un rojo suelto en la cuarta columna se
  pierde.
- Dos cosas que el código ya sabía y el dibujo repite: **banear cierra la sesión
  pero NO oculta los emprendimientos del baneado** (el canvas de agosto decía que sí
  y era falso), y **eliminar enumera qué se lleva la cascada** en vez de decir "no se
  puede deshacer".
- En teléfono el panel **se recorta a la cola**: las tablas de cinco columnas y las
  métricas no entran ni tienen por qué. Acciones apiladas de 44 px, para que
  "Eliminar" no caiga al lado del pulgar que iba a "Marcar resuelto".

De los diseños viejos no están, porque no hay con qué: "Emprendimientos sin
actividad" (`Post` no tiene `updated_at`), "Exportar métricas" y "Exportar CSV".


### 8. Sobre, contacto y errores (dibujada 2026-09-06, a revisar)

| Qué | Dónde |
| --- | --- |
| Artboards | `disenio-paginas/*.dc.html` + `canvas.json` |
| Canvas publicado | https://claude.ai/code/artifact/b25d9e60-64a7-4343-a846-68ae02a96ba1 |

Seis páginas en cinco artboards: Sobre, Contacto, **un molde legal** (se dibujó
Privacidad; Términos es la misma cáscara con otro índice y otro texto), **un molde
de error** (se dibujó el 404) y el 404 en teléfono.

**Tres de las seis tenían un problema que no era de estética:**

1. **`about.html` hablaba del equipo de desarrollo, no del visitante.** Decía que la
   plataforma se hizo "con Flask (Python) y MySQL, siguiendo buenas prácticas de
   diseño y una estética moderna en tonos pastel". Lo de pastel además hace rato que
   es falso. **Reescrita desde el posicionamiento de la guía**: los cinco datos que
   Mercado Libre no tiene, y los cinco salen de una tabla que existe. Se sumó una
   sección **"Lo que IMPULSAR no hace"** —sin pagos, sin envíos, sin protección al
   comprador— porque es la verdad del repo y es el argumento, no una disculpa.
   **No hay ni un número en la página**: cuántos emprendimientos, desde cuándo o
   cuánta gente son datos que no existen y no se inventan.
2. **`contact.html` tenía un emoji** (📧) delante del mail. La guía sólo admite emoji
   si son de la marca. **Sigue siendo un mailto y no un formulario**: la ruta es un
   `render_template` sin lógica y no hay tabla de consultas — un form dibujado que no
   manda nada es peor que un correo honesto. Lo que se agrega son cuatro atajos que
   ya existen (reportar desde la ficha, el chat, publicar, Ajustes), para que la
   casilla no sea el cajón de lo que la app ya resuelve sola.
3. **Privacidad y Términos hacían las listas con `<br>•` adentro de un `<p>`.**
   Parecen viñetas y para un lector de pantalla son un párrafo con puntos medios.
   Pasan a `<ul>`. El texto **no se tocó**, palabra por palabra.

**Un hueco real que queda abierto: ninguna de las dos legales tiene fecha de última
actualización**, así que no se puede saber qué versión aceptó cada usuario. Va
marcado como `[COMPLETAR]` en el artboard porque no es un dato que se pueda inventar.

**El 404 lleva buscador y los siete rubros**; casi siempre se llega desde un
emprendimiento dado de baja o un link viejo pasado por WhatsApp, así que dos botones
sueltos dejan a la persona a mitad de camino. **El 500 NO los lleva**: si el servidor
se cayó, un buscador que tampoco va a andar es una segunda frustración.

Es la única tanda con un solo artboard de teléfono, y es el 404: es la que más se ve
en celular. Las de texto en 390 px son la misma columna más angosta.


---

## Dónde retomamos (2026-09-06)

Las ocho tandas están dibujadas, publicadas y commiteadas. **Ninguna tocó la app**:
lo último que entró a código es el commit `27d1710` (inicio, auth, perfil, ajustes y
servicios).

### Lo único grande que queda: pasar las ocho tandas a código

| Tanda | Carpeta | Canvas |
| --- | --- | --- |
| Navegación global | `disenio-navegacion/` | https://claude.ai/code/artifact/b752a01f-a2be-495c-b0cf-ac660dc65c84 |
| Ficha del emprendimiento | `disenio-ficha/` | https://claude.ai/code/artifact/423b9dbb-2c0d-4eb3-87e1-19bf140d1ace |
| Catálogo de productos | `disenio-productos/` | https://claude.ai/code/artifact/332d05a2-7ac7-4f03-a0fb-de90acf291e9 |
| Panel del vendedor | `disenio-panel/` | https://claude.ai/code/artifact/538a4d0a-52cb-4781-a7e6-717557523761 |
| Turnos | `disenio-turnos/` | https://claude.ai/code/artifact/5566643c-7638-485f-85e7-36cf609cfc55 |
| Ferias y eventos | `disenio-eventos/` | https://claude.ai/code/artifact/c24946a2-195e-4b54-80cc-8bf8fa82c5d6 |
| Panel de administración | `disenio-admin/` | https://claude.ai/code/artifact/79f57360-70eb-468d-802b-054dfa9bbf44 |
| Sobre, contacto y errores | `disenio-paginas/` | https://claude.ai/code/artifact/b25d9e60-64a7-4343-a846-68ae02a96ba1 |

**Empezar por navegación.** Toca `templates/base.html` y
`templates/partials/_menu_cuenta.html` —dos archivos, no cada pantalla— y desbloquea
a todas las demás, porque la barra de tres secciones y Publicar en el menú de la
cuenta ya están decididas y dibujadas en las ocho.

### Pendientes chicos, que salen al paso de eso

- [ ] **Las dos legales no tienen fecha de última actualización.** Sin eso no se
      puede saber qué versión aceptó cada usuario. El artboard lo marca como
      `[COMPLETAR]`: es un dato de Tomás, no se inventa.
- [ ] **La paleta de rubros de la app no es la de la guía** (`styles.css:6199`): el
      mismo rubro tiene dos colores según la pantalla. Son siete pares.
- [ ] **Faltan los estados del inicio**: cargando y sin resultados.
- [ ] **No hay ningún artboard intermedio (~768 px)** en ninguna de las ocho tandas.
      Sabemos cómo cae todo en 1440 y en 390, y nada de lo que hay en el medio —
      que es donde entra una tablet y una ventana a media pantalla.
