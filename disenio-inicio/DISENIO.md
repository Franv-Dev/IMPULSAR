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
