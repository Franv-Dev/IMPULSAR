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

**Oportunidades tampoco entra en la barra global (2026-09-11).** Misma decisión y
mismo motivo que Productos, un año de aprendizaje después: la nav aprobada son
**tres** ítems, y un cuarto vuelve a montarla sobre el bloque de acciones. En el
teléfono el costo es peor y más concreto: las solapas fijas que `base.html` pinta
arriba del contenido son tres, y una cuarta empieza a pedir scroll horizontal —
que es justo lo que no se hace en móvil.

Oportunidades queda entonces como sección secundaria, al lado de Productos y con
las mismas dos puertas fijas: **el pie** (en la columna de secciones, pegada a
Productos) y **un enlace desde la pantalla de la que es la contracara** — el
catálogo se entra desde Emprendimientos, y Oportunidades desde el buscador de
Servicios, porque pedir un servicio es ofrecerlo dado vuelta.

En la barra queda marcado **"Servicios"** cuando se está en `/oportunidades` o en
la ficha de una, igual que Turnos.

**"Inicio" vuelve a la barra, y el centrado se arregla de raíz (2026-09-15).**
Las dos decisiones de arriba se apoyaban en el mismo dato: la nav iba centrada al
50 % **exacto** y **fuera del flujo** (`position: absolute; left: 50%`), así que no
reservaba espacio y había que garantizárselo a mano con una cuenta que sólo cerraba
con tres ítems; el cuarto movía los dos bordes 40px para afuera y el derecho se
metía encima del bloque de acciones.

Eso ya no es así: la nav es un ítem más de la fila, con `flex: 1`, y centra las
secciones **dentro del aire que le queda** entre el logo y las acciones. Es un
espacio que por definición nadie más ocupa, así que el solapamiento deja de ser
posible sin importar cuántos ítems haya. Medido de 860 a 1920 en las cuatro
secciones, visitante y logueado: nunca menos de 18px de aire a cada lado y cero
scroll horizontal. En la franja 860–1023 los dos gaps (el de la fila y el de las
secciones) se achican a 12 y 18px, que es aire, no contenido.

La barra son entonces **cuatro**: Inicio · Emprendimientos · Servicios · Eventos y
ferias, con la activa subrayada en índigo. Lo que **no** cambia es Productos ni
Oportunidades: el motivo que les queda en pie no es el centrado sino el teléfono
—las solapas fijas arriba del contenido son tres, y una cuarta pide scroll
lateral, que es justo lo que no se hace en móvil. "Inicio" no paga ese costo
porque en teléfono no es una solapa: ya es la primera pestaña de la barra de
abajo. Y en el teléfono cuentan como "Explorar" en la
tabbar, para que las pantallas públicas no dejen las cinco pestañas apagadas. Las
dos pantallas privadas (`/oportunidades/mias` y `/oportunidades/mis-propuestas`)
no marcan nada acá: viven en sus menús, la primera en el de la cuenta (es
actividad propia) y la segunda en el del panel (es trabajo del emprendimiento).

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

### 5. Turnos (dibujada, PASADA A CÓDIGO el 9/9)

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


#### Lo que se decidió al pasarla a código (9/9)

**Un quinto vacío que el canvas no tenía.** El artboard dibuja tres mensajes
para el día sin horarios (cerrado, sin horario cargado, todo tomado). En la
verificación visual apareció el cuarto caso real: el día de HOY, ya empezado y
**sin ninguna reserva**, caía en «todo tomado» y decía «los turnos de ese día ya
están tomados» — mentira, y además manda a buscar un culpable que no existe. Es
`consultas.PASO`, y dice «Por hoy ya no llegás». `descartar_pasados` ya existía
desde 2a; lo que faltaba era decirlo distinto.

**La tira lleva dos parámetros, no uno** (`?desde=` y `?fecha=`). Mover la
semana con las flechas no elige un día, y elegir un día no mueve la semana: con
un solo parámetro, cada click recentraría la tira y los otros seis días se
moverían debajo del dedo.

**Los horarios son radios de un solo formulario.** El canvas lo resuelve con
estado de componente; en la app son `<input type="radio">` y un único submit al
final, así el paso de confirmación existe sin JavaScript. `main.js` solo hace
que el resumen del costado siga al horario elegido.

**Cancelar es un `<details>`**, de los dos lados. Mismo recurso con el que la
barra de filtros del catálogo se pliega en el teléfono: la confirmación no
puede depender de que haya cargado un script, porque cancelar no se revierte.

**Los huecos de la agenda no se cortan en tramos.** El artboard los dibuja como
bloques y así quedaron: cada servicio tiene su duración y todos salen del mismo
horario de la persona, así que un hueco de 13:45 a 16:00 puede recibir un turno
de 45 minutos o uno de 90. Cortarlo obligaría a elegir una duración y mentiría
sobre las otras.

**Tres cosas del canvas quedaron afuera, con motivo:** «Cómo llegar» (no hay más
que `address_street`; armar un link a un mapa externo es una decisión de
producto que nadie tomó), «Dejar una reseña» en el historial (habría que saber
si ya la dejó — otra consulta, otra tanda) y el filtro por emprendimiento de la
agenda (hoy sería un filtro de un solo valor).

**El repaso a 390 px quedó pendiente**: la extensión de Chrome no estaba
conectada. Las media queries están escritas siguiendo las dos reglas de teléfono
de más abajo —siete columnas siempre, nada se desliza de costado— pero no se
miraron con un navegador.

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


### 6. Ferias y eventos (dibujada 2026-09-06, PASADA A CÓDIGO el 9/9)

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



#### Lo que se decidió al pasarla a código (9/9)

**De los tres campos que la base no tenía entran DOS**, decidido con Tomás antes
de escribir la migración (`c7d92f4a1b83`, la única de todo el rediseño):

- **Tipo de evento**: `events.tipo`, `String(20)`, **nullable**. La taxonomía es
  la de acá —Feria · Taller · Pop-up · Encuentro— y queda cerrada: cambiarla
  después obliga a re-etiquetar lo cargado. **Sin «Otros»**, al revés que los
  rubros de emprendimiento: el cajón de sastre desde el día uno garantiza que la
  mitad caiga ahí y que el filtro no sirva. Nullable porque los eventos viejos no
  tienen tipo y no hay de dónde sacarlo — NULL es «no lo dijo», la tarjeta no
  dibuja el chip, y ningún filtro por tipo lo cuenta. El formulario sí lo exige.
- **Entrada libre**: `events.entrada_libre`, `Boolean` NOT NULL, default False.
  La asimetría con el tipo es deliberada: el chip solo aparece en True, así que
  False no afirma nada, mientras que un tipo equivocado sí afirma algo falso.
- **«Me interesa» no entró.** El propio canvas dice que si hay que recortar algo
  de los tres es éste, y por eso se recortó: es una feature entera, no una
  etiqueta.

**El calendario ya filtra.** Los días son enlaces a `?dia=AAAA-MM-DD`. El parcial
tiene dos modos (`data-enlace-dia`): enlace en la cartelera, botón en el home,
donde el panel de al lado se arma en el navegador y recargar para ver tres
eventos sería peor. Con un día elegido, el calendario abre en SU mes.

**El día manda sobre «todavía no pasó»**: elegir una fecha del pasado la muestra,
porque el calendario navega meses para atrás y esconder lo vencido dejaría esos
meses vacíos.

**Una pantalla que el canvas no dibuja: `/eventos/mios`.** Es la que le faltaba
al ítem «Eventos y ferias» del menú del panel, que quedó pendiente de la tanda
anterior. Próximos y pasados, editar y borrar; el borrar con el mismo aviso en
`<details>` que cancelar un turno.

**Los cuatro tipos van todos en índigo lavado y se distinguen por el ícono**, tal
como pedía el canvas. En el formulario son un segmentado de cuatro radios, no un
`<select>`.

**El repaso a 390 px quedó pendiente** (la extensión de Chrome no estaba
conectada). En teléfono los filtros envuelven en dos filas en vez de esconderse
detrás del botón «Tipo y entrada» del artboard: hace lo mismo sin agregar una
capa que hay que abrir para ver qué hay.

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

## Navegación pasada a código (2026-09-08)

Primera de las ocho tandas dibujadas que entra a la app. Toca `templates/base.html`
y tres parciales nuevos; ninguna pantalla de contenido se tocó.

### La barra: dos bandas en vez de una fila

| | Antes | Ahora |
| --- | --- | --- |
| Filas | 1 | 2: identidad + secciones + acciones (68 px), y el buscador solo (52 px) |
| Secciones | 4 (Inicio, Emprendimientos, Eventos, Servicios) | 3, centradas, la activa subrayada en índigo |
| Buscador | un campo, y sólo desde 1200 px | dos campos (`q` + `near`) y un botón, en todas las pantallas menos las dos que ya tienen el suyo |
| Favoritos y Mensajes | adentro del menú, a dos clicks | iconos visibles en la barra |
| Publicar | no estaba en la barra (sólo en el pie) | botón lleno arriba del menú de la cuenta |
| Nombre de usuario | en la barra, con tope de 9 rem | sólo el avatar; el nombre está arriba del menú |

**"Inicio" se fue** de las secciones: el logo ya es el inicio.

**Los dos breakpoints viejos se recalcularon.** Con el buscador fuera de la fila 1,
esa fila sólo tiene que albergar logo (~110 px) + secciones (344 px) + acciones. El
caso más ancho sigue siendo el del visitante ("Acceder" + "Crear cuenta" + el
switch, 262 px): con dos gaps de 20 px y los 48 px de padding del container son
804 px. El corte de la vista de teléfono baja de 879 a **859 px**; el de 960 px (a
partir de dónde las secciones se pueden centrar) queda igual porque mide otra cosa.

**El buscador de la barra no se dibuja en el home ni en el listado**: esas dos
pantallas ya abren con su propia banda de búsqueda, y encima más completa (las dos
suman el rubro). Se vio en pantalla antes de decidirlo: quedaban dos buscadores
apilados preguntando lo mismo. Cuál de los dos sobrevive en el listado se decide
cuando toque `disenio-inicio/Resultados`.

### El menú de la cuenta: tres grupos, no una lista de nueve

`partials/_menu_cuenta_desplegable.html`. Mi actividad (Mensajes, Presupuestos, Mis
turnos, Favoritos) · Mi emprendimiento (Mis emprendimientos, Mi catálogo, Mis
servicios, Agenda de turnos, Reseñas recibidas) · y abajo Ajustes y Salir, con el
panel de administración sólo para el admin.

**Mis turnos y Agenda de turnos entran acá por primera vez**: `/turnos/mios` y
`/turnos/agenda` existían desde la tanda de turnos y no estaban en ningún menú.

Ojo que **no es el mismo archivo** que `partials/_menu_cuenta.html`, que es la
columna izquierda de las diez pantallas de cuenta y sigue como estaba.

### El contador que mentía

`/mensajes/notificaciones` **ya devolvía los tres números por separado**
(`unread_messages`, `pending_service_requests`, `unanswered_reviews`) desde la tanda
de servicios; el que los sumaba y pegaba el total al ítem "Mensajes" era el JS. No
hizo falta tocar el backend: cada elemento dice cuál quiere con `data-notif="..."`,
y `main.js` rellena todos los que encuentre. El mismo contador puede estar en varios
lugares a la vez (el sobre de la barra, la pestaña del teléfono, el menú).

Tokens nuevos: `--color-badge-bg: #A85527` y `--color-badge-ink: #FFFFFF`, **iguales
en los dos temas** a propósito, como `--color-primary-deep`: es una marca de alerta
con texto blanco fijo, no una superficie que siga al tema. No es el `#D97544` del
artboard porque el blanco encima de ese da **3.19:1** y el badge es texto chico en
negrita, o sea que necesita 4.5:1; el tono un paso más oscuro da **5.26:1**. El par
suave (presupuestos, reseñas) reusa `--color-warning-bg` / `--color-warning-text`,
que ya estaba verificado.

### El teléfono: se fue la hamburguesa

Cinco pestañas abajo con sesión (Inicio · Explorar · Favoritos · Mensajes · Perfil),
62 px de alto. Publicar **no** entra: es una acción de dueño y vive arriba de la
pantalla Mi cuenta. Nada de botón flotante, que taparía una tarjeta.

Dos cosas que el canvas no había resuelto y se decidieron acá:

- **Qué hace "Explorar".** El artboard dice que agrupa las tres entradas de
  escritorio pero nunca dibujó esa agrupación. Va al listado, y las tres secciones
  reaparecen como una fila de solapas arriba del contenido, sólo en teléfono y sólo
  en esas tres pantallas. Sin scroll lateral y sin pantalla nueva.
- **Qué ve un visitante.** Los dos artboards de teléfono están con sesión iniciada.
  Sin cuenta son tres pestañas (Inicio · Explorar · Entrar) y no cinco: Favoritos y
  Mensajes piden login, así que como pestañas sólo rebotarían.

`/perfil/mi-cuenta` es la pantalla nueva de la pestaña Perfil. Se dibuja igual en
escritorio (columna angosta y centrada): la ruta existe en los dos anchos aunque
sólo la enlace la barra de abajo, porque un link compartido tiene que abrir algo.
Va en `SLUGS_RESERVADOS`, como toda ruta estática bajo `/perfil/`.

### Lo que quedó afuera, a propósito

**La pastilla de zona del top bar del teléfono.** El artboard la dibuja al lado del
logo, pero el propio canvas anota que *"falta cablear que la zona elegida se recuerde
entre pantallas"*: sin esa memoria, la pastilla no tiene nada que decir ni dónde
guardar lo que se elija. La zona se dice en el campo "dónde" del buscador, que sí
manda un `near` real al listado. Cuando exista la memoria de zona, la pastilla entra.

### Un bug de CSS que salió al mirarlo

Los contadores nacen con el atributo `hidden`, pero `hidden` vale menos que
cualquier `display` de una clase propia: con `display: flex` encima se seguían
viendo, y pintaban un punto naranja vacío aunque no hubiera nada. Se agregó
`[hidden] { display: none !important; }` al reseteo. Un test puede afirmar que el
atributo está, no que el CSS lo respete: esto se vio en pantalla, no en la suite.

---

## Ficha del emprendimiento pasada a código (2026-09-09)

Segunda de las ocho tandas. Reescribe `blog/detail.html` entero (466 líneas) y
suma tres piezas de backend chicas. La navegación de la tanda anterior ya está
puesta, así que la ficha hereda la barra de dos bandas sin tocarla.

### Los siete problemas que el canvas anotó, y qué se hizo con cada uno

| Lo que estaba mal | Ahora |
| --- | --- |
| Las reseñas decían «Usuario #7» | Firman con el nombre, traído en el mismo query (`joinedload`) |
| Las estrellas eran los glifos ★ y ☆, y había un 📍 por servicio | SVG en `partials/_estrellas.html` y en `_icono_nav.html` |
| Las ferias no aparecían nunca | Bloque «Dónde encontrarla», con `Post.eventos` |
| «Abierto ahora» no decía a qué hora cierra | «Abierto ahora · cierra 19:00» |
| Las miniaturas abrían el archivo suelto de `/static/uploads/` | Visor propio, con teclado y foco |
| Ningún estado vacío pensado | Cada hueco explica por qué conviene llenarlo |
| La distancia no se mostraba aunque hay lat/lon | **Sigue sin mostrarse** — ver más abajo |

### Anclas, no pestañas

El pedido evaluaba «Inicio · Productos · Servicios · Reseñas · Información» como
solapas. No van: la mayoría de los emprendimientos tiene dos o tres productos y
ninguna reseña, así que tres de las cuatro abrirían vacías y la ficha parecería
abandonada. Quedó una barra de anclas que se pega arriba al scrollear. Nada se
esconde detrás de un click y la página sigue siendo una sola para buscadores y
para compartir. En teléfono la barra no va: los bloques ya están uno abajo del
otro y una barra pegada come pantalla sin ahorrar scroll.

Las visitas (`views_count`) se mudaron a la barra de dueña, no al lado del
nombre: son un dato del dueño, no algo que ayude a decidir a quien entra.

### Los nueve bloques son una lista plana

El teléfono los quiere en otro orden que el escritorio — **horarios y ferias
ANTES de las reseñas**, porque son lo que decide si conviene ir ahora — y con
dos columnas anidadas ese reordenamiento no se puede hacer con CSS. En el HTML
van los nueve seguidos; en escritorio los dos envoltorios arman la grilla de dos
columnas, y en teléfono se vuelven `display: contents` y cada bloque se acomoda
con su propio `order`. Cada bloque dice su lugar por su propia clase
(`--identidad`, `--ferias`, `--mapa`…), no por en qué envoltorio estaba.

### Lo que se sumó al backend

Tres cosas chicas, todas contra datos que ya existían:

- **`services/horarios.hora_de_cierre()`**, que devuelve el `time` de la ventana
  abierta ahora, o None. `esta_abierto()` pasó a ser `hora_de_cierre(...) is not
  None`: son la misma pregunta y no pueden contestar distinto. Las dos ramas del
  cruce de medianoche viven ahora en un solo lugar. Ninguna respuesta cambia —
  los 39 tests de horarios pasan sin tocarlos.
- **`consultas.ferias_de()`**, que reusa `services.eventos.proximos()`. Ahí ya
  estaba decidido que el corte es por día y no por hora, y que el id desempata al
  final porque la hora es opcional; repetir el `order_by` a mano se comía ese
  desempate.
- **El filtro `hace`** (`services/formatting.tiempo_relativo`): «hace 2
  semanas». Leyendo una reseña lo que importa es si es de esta temporada o de
  hace dos años, no el día; la fecha exacta queda en el `title`.

**`/mensajes/notificaciones` no se tocó** — igual que en la tanda anterior, el
dato ya estaba y lo que faltaba era mostrarlo.

### La ficha recién publicada

Es el estado en el que va a estar TODA ficha nueva, y la app no lo diseñaba: se
veían bloques en blanco y ya. Ahora:

- Una **barra de dueña** arriba de todo dice que estás parada en tu propia ficha,
  con las visitas, «Editar los datos» y «Eliminar». Sin eso los huecos se leen
  como una pantalla rota en vez de como algo que falta cargar.
- **Cada hueco explica por qué conviene llenarlo.** El de la galería no es un
  rectángulo gris con un iconito —eso se lee como carga rota— sino la invitación
  con el motivo.
- **«Completá tu ficha»** son cinco tareas contra campos que existen: nombre y
  descripción, dirección, fotos, horarios, y un producto o un servicio. El aviso
  de abajo es cierto: sin horarios la ficha no entra en el filtro «abierto
  ahora». La caja desaparece sola cuando las cinco están.
- El vacío de reseñas aclara que **no se piden ni se cargan a mano**. Es la duda
  que trae cualquiera que viene de otra plataforma.
- **Productos y servicios son dos bloques distintos.** A la dueña se le muestran
  los dos siempre; a un visitante sólo el que tenga algo adentro, así un
  emprendimiento que es puro servicio no muestra un «Lo que vende» en blanco.

### El teléfono

La barra de contacto va fija abajo: es LA acción de la pantalla y no puede vivir
al final de dos mil píxeles de scroll ni en una columna que ahí no existe. Ocupa
el lugar de la barra de pestañas — la ficha es una pantalla abierta ENCIMA de
Explorar — y `detail.html` apaga las pestañas sobreescribiendo el bloque
`tabbar`. A la dueña no se le dibuja: sus acciones están arriba.

### Lo que quedó afuera, a propósito

**La distancia («a 400 m tuyo»).** Necesita saber dónde está parado quien mira, y
eso todavía no existe: es la misma memoria de zona entre pantallas que la tanda
de navegación dejó anotada como pendiente. Mostrar una distancia sin ese dato
sería inventarla. Entra cuando entre la zona.

**Los botones de compartir y favorito siguen con emoji** (🔗 y ♥/♡). Van contra
la misma regla que las estrellas, pero viven en `partials/` y los usan también
las tarjetas del listado y del inicio, y `share.js` les pisa el `textContent`
para el estado «copiado» — cambiarlos a SVG es su propia tanda chica, no un
arreglo al paso de ésta.

### Un desborde lateral que salió al medirlo

En 390 px la pantalla se deslizaba de costado: `scrollWidth` daba 434. El culpable
era «Entrá para pedir presupuesto» con `white-space: nowrap`, cuyo ancho mínimo
de contenido (410 px) se lo comía el bloque entero —los bloques son items flex por
el `display: contents`— y después el `body`. Se arregló dejándolo envolver y
poniéndole `min-width: 0` a los bloques. Medido de nuevo: 371 px, sin scroll
lateral. Va con la regla que ya estaba: **nada se desliza de costado en móvil.**

## Catálogo de productos pasado a código (2026-09-09)

La tercera tanda que entra a la app, después de navegación y ficha. Es la única
de las ocho que **necesitaba rutas nuevas**: hasta ahora `/productos` era el
panel privado del dueño y un producto sólo se veía incrustado adentro de la
ficha de su emprendimiento, o sea que para encontrarlo había que saber antes
quién lo vende.

### Las URL se dieron vuelta

| Antes | Ahora | Quién |
| --- | --- | --- |
| `/productos/` → panel del dueño | `/productos/` → **catálogo público** | cualquiera |
| — | `/productos/<id>` → **detalle del producto** | cualquiera |
| — | `/productos/<id>/favorito` (POST) | con sesión |
| — | `/productos/guardados` | con sesión |
| `/productos/` | `/productos/mios` → panel del dueño | el dueño |

La URL corta se la queda la pública porque es la única que alguien linkea o
comparte. El endpoint del panel dejó de llamarse `products.index` y pasó a
`products.mios`; los doce `url_for` que lo nombraban están actualizados, y
`templates/products/index.html` es ahora `mios.html`.

### Los seis filtros, y por qué esos

Todos viajan como parámetros de la URL, no como un formulario que se postea: la
búsqueda se comparte, vuelve con el botón de atrás y funciona sin JavaScript.
Es el mismo criterio que ya usan el listado y la búsqueda de servicios.

- **Texto** — mira `Product.nombre` y `Product.descripcion`, no el
  emprendimiento: el que busca «dulce de leche» acá está buscando la cosa. Para
  encontrar el negocio está el listado, que además ya mira adentro del catálogo.
- **Rubro** — `Post.category`. `Product` no tiene categoría propia, y por eso el
  punto de color de cada tarjeta es el del rubro del negocio.
- **Precio desde/hasta** — `Product.precio` es `Numeric(10,2)`, así que el rango
  es exacto. Lo lee **el mismo `parsear_precio` del formulario de carga**, o sea
  que «1.500,50» y «1500.50» se entienden igual en los dos lados. Un precio mal
  escrito no acota nada pero el texto crudo vuelve al campo, para que no se
  vacíe solo mientras alguien escribe.
- **Disponibles** — viene **encendido**, y por eso lo que viaja en la URL es el
  apagado (`?disponibles=0`), al revés que los checkboxes de sí/no del listado.
  Un catálogo que arranca mostrando lo que no hay hace perder tiempo.
- **Abierto ahora** — el mismo `abierto_ahora_sql` del listado, sobre los
  horarios del emprendedor.
- **Radio en km** — el mismo `distancia_km_sql`, y sólo se dibuja si hay
  coordenadas: sin ellas la consulta lo ignora, y ofrecer un filtro que no hace
  nada es peor que no tenerlo. Los radios son los tres de `reglas.RADIOS_KM`.

Las dos funciones del listado que hacían falta (`_distancia_km` y
`_abierto_ahora_sql`) **pasaron a ser públicas** (`distancia_km_sql`,
`abierto_ahora_sql`) en vez de copiarse: la copia se habría olvidado del `CASE`
que acota el `ACOS`, que es justamente el detalle que costó encontrar.

**El orden** son cuatro: más nuevos (el default), precio de menor a mayor, de
mayor a menor, y cercanía — esta última sólo aparece cuando hay coordenadas. Si
la ubicación se pudo resolver, el default pasa a ser cercanía: quien se tomó el
trabajo de decir dónde está quiere lo de al lado primero, y el control queda
marcado en lo que se aplicó, así que no es un orden secreto.

**«18 productos de 11 emprendimientos»** es un `COUNT(DISTINCT post_id)` que
pasa por el mismo `_filtrar_catalogo` que la grilla. Escrito dos veces, el
número miente en cuanto alguien toque un filtro — es el problema que servicios
ya había resuelto con su `_filtrar_busqueda`.

### El detalle contesta dos preguntas

Qué es (foto, precio, disponible, descripción) y **quién lo vende** (rubro,
puntaje, abierto ahora, el emprendimiento). La segunda pesa tanto como la
primera: sin pagos ni protección al comprador, lo que decide es la confianza en
la persona.

- **Una sola foto**, con «Ampliar». `Product.foto` es una columna, no una
  galería: no hay miniaturas que dibujar y fingirlas sería mentir sobre el
  modelo. El botón abre **el mismo visor de la ficha** (`static/js/visor.js`),
  que funciona igual con una foto sola: sin flechas ni contador, porque no hay
  nada que recorrer.
- **No hay «Comprar»**, ni cuotas, ni envío, ni «más vendido». La acción es
  **«Consultar por este producto»**, y termina en el chat interno.
- **«Más de este emprendimiento»** sale de `Product.post_id`, y el «Ver los N
  productos» sale del mismo `metricas_de_posts` que ya trae el promedio y la
  cantidad de reseñas: una consulta para los tres datos.
- **Las migas de pan** son la única pantalla que las tiene, y por un motivo: se
  llega desde cuatro lados (el catálogo, un rubro, la ficha, un link
  compartido). En 390 px se esconde la última, que es la más larga y la única
  que no lleva a ningún lado.

### El chat que ya sabe de qué se habla

`?producto=<id>` en `messages.conversation` deja el campo con «Hola, quería
consultar por «...».» ya escrito. Es la diferencia entre un chat en blanco
—donde el que pregunta tiene que volver a explicar por cuál de los catorce
frascos escribe— y uno donde el dueño ya sabe de qué se trata.

**Se exige que el producto sea de ese emprendimiento.** Sin ese chequeo, un id
cualquiera en la URL escribiría en el campo el nombre de un producto ajeno, que
es una forma barata de poner palabras en boca del que pregunta. Si no coincide
no se precarga nada, que es lo mismo que entrar por «Enviar un mensaje». Y es
sólo un valor inicial: se borra y se escribe otra cosa.

### Favoritos de productos: tabla nueva

El corazón de las tarjetas necesitaba dónde guardar. `Favorite` es de
emprendimientos, así que va **`product_favorites`**, tabla propia
(`models/product_favorite.py`, migración `a4c17b8e6d20`): un favorito de negocio
y uno de producto se guardan igual pero se miran distinto, y meterlos en la
misma tabla con un `post_id` o un `product_id` nullable obligaría a un CHECK de
«uno u otro» y a que cada consulta se acuerde de cuál está buscando.

Las dos FK con `ondelete="CASCADE"` y nombre explícito desde el vamos, y el
`UNIQUE (user_id, product_id)` que es lo que de verdad corta el doble click —el
`SELECT` de «¿ya lo tiene?» y el `INSERT` no son atómicos. Verificado el ciclo
upgrade → downgrade → upgrade en SQLite y en una base MySQL descartable, y ahí
mismo que las dos cascadas y el UNIQUE hacen lo que dicen.

**«Mis favoritos» pasó a tener dos solapas**, Emprendimientos y Productos, en un
parcial compartido (`partials/_solapas_favoritos.html`): separadas, entrar a una
sería quedarse sin salida hacia la otra.

### Cómo se entra al catálogo

**Productos no entra en la barra global**, como ya estaba decidido: con cuatro
secciones la nav, que va centrada al 50 % exacto, se monta encima del bloque de
acciones. Quedan tres puertas:

- El pie, columna «Explorar».
- Una ficha en la barra de filtros del listado, **que se lleva el texto
  buscado**: quien escribió «dulce de leche» y no encontró el negocio va a
  encontrar la cosa.
- Cada producto de la ficha del emprendimiento, que dejó de ser un cartel y
  pasó a ser un enlace a su detalle.

En las tres pantallas del catálogo la barra marca **«Emprendimientos»**, que es
de donde se viene, y la pestaña de teléfono marca **«Explorar»**.

### Lo que quedó afuera, a propósito

**La hoja de filtros que sube desde abajo en teléfono.** El artboard móvil la
dibuja como dos botones —«Filtros (2)» y el orden— que abren una hoja. En código
son el mismo `<details>` que ya usa el listado, que `main.js` cierra en
pantallas chicas: mismos seis filtros, misma URL, sin JavaScript nuevo. La hoja
es una tanda propia y, si se hace, se hace para las dos pantallas a la vez —
tener dos formas distintas de abrir los mismos filtros sería peor que la que hay.

**La distancia en el detalle.** Igual que en la ficha: necesita la memoria de
zona entre pantallas, que todavía no existe. En la grilla sí se muestra, porque
ahí la ubicación la acaba de escribir el visitante en el buscador.

**El precio como tweak/rango con slider.** El canvas lo dibuja como dos
pastillas «desde $ / hasta $»; en código son dos campos de la misma barra de
filtros. Es la misma pregunta y ahorra una barra distinta para lo mismo.

### Nada se desliza de costado

La grilla es de cuatro columnas en escritorio, tres hasta 960 px y **dos en
teléfono** — nunca una tira que se desliza. El precio va arriba del nombre en
cada tarjeta justamente para eso: en dos columnas es el dato que hace comparar,
y en una sola habría que hacer memoria.

### Un botón muerto que salió al paso

**«Cerca de mí» no funcionaba en ninguna de las dos pantallas.** El JS hacía
`boton.closest("form").submit()`, y desde el rediseño de la barra de filtros ese
botón vive en la fila de fichas, **afuera del `<form>`**: `closest` daba `null` y
el click moría con un `TypeError` sin buscar nada. Se cambió por
`latInput.form.submit()` — el form que tiene que viajar es el que lleva las
coordenadas que el botón acaba de escribir, no el que casualmente lo envuelva.
Verificado en el navegador con la geolocalización simulada: manda
`barra-filtros__form` con la latitud ya puesta. **Arregla también el listado de
emprendimientos**, donde estaba igual de muerto.

## Sobre, contacto y errores pasados a código (2026-09-09)

La cuarta tanda, y la más chica: seis pantallas, ninguna ruta nueva, ninguna
migración. Lo que cambió no fue sólo la paleta — tres de las seis tenían un
problema que no era de estética.

### 1. «Sobre» hablaba del equipo de desarrollo, no del visitante

Decía que la plataforma «fue desarrollada por un equipo académico utilizando
**Flask (Python)** y **MySQL**, siguiendo buenas prácticas de diseño y una
estética moderna en tonos pastel». Tres datos que no le sirven a nadie que entre
a buscar un emprendimiento, y el último además hace rato que es falso: la paleta
es el índigo del logo.

En su lugar va **el posicionamiento que la guía ya decidió**: los cinco datos que
Mercado Libre no tiene, y **los cinco salen de una tabla que existe** — horarios,
`latitude`/`longitude`, el autor con antigüedad y reseñas, los eventos, y el chat
interno. Ninguno es una promesa a futuro. La sexta tarjeta es la única de marca y
es la que pide algo (publicar); va última porque es la acción, no un argumento.

**«Lo que IMPULSAR no hace»** entra como sección propia: sin pagos, sin envíos,
sin protección al comprador. Es la verdad del repo y es el argumento, no una
disculpa — decirlo acá es lo que evita que alguien se sienta estafado a mitad del
chat, y es también por qué la ficha muestra tan adelante quién vende. La cruz de
cada punto va en gris y no en rojo: no son errores.

**No hay ni un número en la página.** Cuántos emprendimientos, desde cuándo o
cuánta gente son datos que no existen y no se inventan; hay un test que lo
vigila, porque es exactamente el tipo de cosa que alguien agrega de memoria.

### 2. Contacto tenía un emoji, y sigue sin formulario

El mail estaba escrito como «📧 impulsARmdz@gmail.com». La guía sólo admite emoji
si son de la marca, y ahí era decoración: queda un ícono de trazo, como el resto.

**Sigue siendo un `mailto` y no un formulario**, a propósito: la ruta es un
`render_template` sin lógica y no hay tabla de consultas ni envío de mail. Un
formulario dibujado que en realidad no manda nada es peor que un correo honesto.
El canvas dibujaba el mail como texto con un botón «Copiar»; en código es **el
enlace `mailto` entero**, que ya abre el cliente de correo en cualquier
dispositivo y no necesita JavaScript para funcionar.

Lo que se agrega son **cuatro atajos, y los cuatro existen hoy**: reportar desde
la ficha, escribirle al emprendimiento por el chat, publicar, y Ajustes. Sin
ellos la casilla se vuelve el cajón donde caen «este emprendimiento es trucho» y
«quiero cambiar mi mail», que la app ya resuelve sola y más rápido. Los dos que
piden sesión llevan a entrar cuando no la hay, en vez de a una URL que va a
rebotar igual.

### 3. Las legales hacían las listas con `<br>•` adentro de un `<p>`

Se ven como viñetas y para un lector de pantalla son **un párrafo con puntos
medios en el medio**. Ahora son `<ul>` de verdad, con la viñeta dibujada aparte
para poder alinearla con la primera línea de los textos que envuelven.

**El texto no se tocó, palabra por palabra.** Lo que se suma es el índice al
costado (`sticky`, con las secciones de esa página y el enlace cruzado a la
otra legal) y la medida de lectura de **66ch**, lo único en toda la app con línea
larga de verdad: son las dos únicas pantallas que se leen de corrido.

Las dos comparten un molde, `templates/legal_base.html`, con cuatro bloques
(`legal_titulo`, `legal_bajada`, `legal_indice`, `legal_cuerpo`): son la misma
cáscara, y por eso el canvas dibujó una sola. Los `<h3>` pasaron a `<h2>` con
`id`, que es lo que le da destino al índice; hay un test que verifica que ningún
ítem del índice apunte a un ancla que no existe.

**La fecha sigue siendo un hueco real.** Ninguna de las dos tiene «última
actualización», así que no se puede saber qué versión aceptó cada usuario. En
código son dos constantes en `views/pages.py` (`ACTUALIZADA_PRIVACIDAD`,
`ACTUALIZADA_TERMINOS`) **en `None`**: mientras lo estén, la pastilla no se
dibuja. Un `[COMPLETAR]` a la vista del usuario sería peor que no decir nada, y
la fecha es un dato de Tomás. Cuando se carguen, la pastilla aparece sola.

### 4. Un 404 no es un cartel, es una bifurcación

Casi siempre se llega desde un emprendimiento dado de baja o un link viejo pasado
por WhatsApp: la persona venía a buscar algo concreto, y dos botones sueltos
—que es lo que había, centrados en una tarjetita de 480 px— la dejan a mitad de
camino. Ahora **el buscador entra a la pantalla** (manda al listado, que es donde
la búsqueda vive) y **los siete rubros van abajo**, con el mismo `.punto-rubro`
que estrenó el catálogo: un rubro no cambia de color según la pantalla.

**El 500 es el mismo molde con otro texto y SIN buscador ni rubros**: si el
servidor se cayó, ofrecer un buscador que tampoco va a andar es una segunda
frustración. Sus dos botones son reintentar (a `request.url`, la URL que falló) y
Contacto — no «ver emprendimientos», que es justo lo que puede estar roto.

En 390 px los dos botones van apilados y a lo ancho (uno al lado del otro quedan
en 165 px y «Ver todos los emprendimientos» no entra sin cortarse), el buscador
se apila igual, y los rubros van en **grilla de dos columnas** — nunca una tira
que se desliza de costado. Medido: 371 de `scrollWidth` en las seis pantallas, a
390 y a 768.

### Lo que quedó afuera, a propósito

**El botón «Copiar» del mail.** Necesita JavaScript para hacer algo, y el enlace
`mailto` ya resuelve el caso real. Si algún día se agrega, va con el mismo
criterio que el resto: dibujado escondido y encendido por el JS, para que sin él
no quede un botón que no responde.

**Las páginas de texto en teléfono no tienen artboard propio** y no hacía falta:
son la misma columna más angosta. El único artboard de teléfono de la tanda es el
404, que es la que más se ve en celular.

### Barrido de CSS muerto

Al reescribir las seis quedaron sin dueño diez reglas: `.about`, `.about__text`,
`.contact`, `.contact__text`, `.contact__info`, `.contact__email` (+ `:hover`),
`.legal__text`, `.legal__subtitle` y el bloque entero de `.error-page` con sus
cuatro hijas. Se borraron cruzando cada clase contra todos los templates y el JS
como token entero. `.legal` sobrevive con el mismo nombre pero es otra cosa: era
una columna de 720 px y ahora es la grilla de índice + cuerpo.

## Panel de administración pasado a código (2026-09-09)

La quinta tanda. **Ninguna ruta nueva, ninguna migración**: de las cinco
plantillas, tres ya tenían el rediseño de agosto y lo que faltaba era lo que se
había quedado afuera.

### Reportes y Verificaciones no eran «pintura pendiente»: no existían con la forma del resto

Las dos seguían con `.section__header`, una tabla pelada, estilos inline
(`style="font-size:0.8rem"`) y —lo grave— **sin el menú del panel, aunque el
menú les enlazaba**: entrabas a Reportes y perdías la navegación, con un
«← Volver al panel» suelto como única salida. Por eso el artboard de la cola era
el central de la tanda.

**La cola es una pantalla, no una tabla.** Una verificación se resuelve mirando
un documento y escribiendo un motivo, y eso no entra en una celda de una fila de
seis columnas — donde vivía, en un `<textarea rows="1" style="min-width:180px">`
apretado en la columna «Acción». Ahora es una ficha por ítem: la cita del reporte
entera (antes cortada por un `max-width: 280px`), el documento en su propia caja,
y las acciones abajo separadas por una línea.

**El motivo sigue viajando en el mismo envío que el rechazo** — un solo `<form>`
con el campo y el botón. Si fuera otra pantalla, el prestador se quedaría sin
saber qué corregir cada vez que el admin tiene apuro. Eso ya lo había decidido el
código (`admin.rechazar_verificacion`) y se respeta.

**Sin foto es un estado, no un hueco.** `foto` es nullable y la celda decía «Sin
foto» en gris, con el botón de aprobar al lado invitando a poner un sello sobre
nada. Ahora la caja del documento va con borde punteado, **aprobar se apaga** y
el motivo del rechazo **viene escrito** («Falta la foto de la matrícula.»), que
es la única salida sensata. El `disabled` es la pantalla diciendo lo obvio, no un
permiso: el permiso vive en `@admin_required`, y la ruta no lo rechaza porque un
admin podría tener el documento por otro lado.

### El Resumen y la cola dibujaban el mismo ítem dos veces

Eran dos copias del mismo marcado, con las mismas dos acciones escritas en dos
archivos. Pasaron a **dos parciales compartidos**,
`admin/_ficha_reporte.html` y `admin/_ficha_verificacion.html`. Lo único que
cambia entre las dos pantallas es una bandera, `compacta`: en el Resumen el
documento es un enlace en la línea de datos y en la cola tiene su propia caja —
la cola es donde se decide, el Resumen sólo avisa que existe.

Eso dejó sin dueño `.admin-item*` (nueve reglas) y `.admin-aviso`, que se
borraron.

### Un solo número grande por pantalla

El Resumen lidera con **lo pendiente a 60 px** y las tres métricas quedan abajo a
30: si compiten en tamaño, la pantalla deja de tener un titular y pasa a ser un
tablero de cifras sueltas. Antes era un `<h1>` de texto («Hoy hay 5 cosas para
revisar»), que es la misma información sin jerarquía.

**Con las dos colas vacías el número no se dibuja**: un cero a 60 px ocuparía
media pantalla para decir que no hay nada que hacer.

Sigue **sin flecha de tendencia y sin sparkline**, y no por pereza: la consulta
da el total de hoy y la fecha de alta de cada fila, no hay histórico contra el
que comparar. «+47 en 30 días» es lo que se puede sostener.

### El estado nunca se dice sólo con color

Cada pastilla lleva **ícono y palabra** (Activo con tilde, Baneado con cruz, «1
reporte sin resolver» con el triángulo) y **la fila entera se tiñe**, no sólo una
celda: en veinte filas, un rojo suelto en la cuarta columna se pierde — y para
quien no distingue rojo de verde, no dice nada. Hay un test que abre cada
pastilla y exige que adentro haya un `<svg>`.

De paso, la columna «Rol» mostraba **el valor crudo de la base** («emprendedor»,
en minúscula) al lado de un filtro que dice «Emprendedores». Las etiquetas viven
ahora en `Roles.ETIQUETAS`, al lado de los valores, igual que las de `Categorias`.

**`tabular-nums` en columnas** (fechas, vistas, reseñas, conteos de los chips)
con una clase `.num`, para que aliñen verticalmente. Los números grandes sueltos
—el del Resumen, los totales de las métricas— van con las cifras proporcionales:
a 30 y 60 px las tabulares quedan flojas.

**`.btn--peligro`**, la acción destructiva: blanca en reposo y roja al acercarse.
No es roja desde el principio a propósito — en una tabla de veinte filas, veinte
botones rojos convierten el rojo en el color de fondo del panel y deja de avisar
de nada.

### En el teléfono el panel se recorta a la cola

Las tablas de cinco columnas y las métricas no entran ni tienen por qué: al
celular se viene a resolver algo urgente. El menú lateral se apaga y en su lugar
quedan **el contador de pendientes y un segmentado de dos** (Reportes y
Verificaciones). Los dos viven en el mismo `_menu_admin.html` para que ninguna
pantalla del panel se olvide de una.

Usuarios y Emprendimientos siguen accesibles por URL: su tabla scrollea dentro de
su propia caja (`.admin-table-wrapper`), no la página. Medido: 371 de
`scrollWidth` en las cinco pantallas, a 390 y a 768.

**Las acciones van apiladas y a lo ancho, de 44 px**, así «Eliminar» no cae nunca
justo al lado del pulgar que iba a «Marcar resuelto».

### Lo que quedó afuera, a propósito

**«Emprendimientos sin actividad»**: `Post` no tiene `updated_at` y habría que
elegir qué es «actividad» (¿su último evento? ¿su último producto? ¿su última
reseña?). Sería una métrica inventada.

**«Exportar métricas» y «Exportar CSV»**: no hay exportación de nada en el
proyecto.

**El menú lateral no se convierte en un cajón desplegable en teléfono.** El
diseño dice que ahí el panel *es* la cola, no que el menú se esconda: agregarlo
sería devolver a la pantalla chica justo lo que la tanda decidió sacarle.

---

## Panel del vendedor pasado a código (2026-09-09)

La sexta tanda. **Una ruta nueva (`/panel`), un POST nuevo
(`/productos/<id>/disponible`), ninguna migración.**

### Seis pantallas sueltas pasan a ser una sección

«Mis emprendimientos», «Mi catálogo», «Mis servicios», «Presupuestos», la agenda
de turnos y las reseñas recibidas eran seis páginas que solo se tocaban desde el
menú de la cuenta, cada una con su forma: cuatro compartían `_menu_cuenta.html`,
la agenda no tenía ningún menú y era un `.section__header` suelto. Ahora las
siete (con la portada nueva) comparten `partials/_menu_panel.html`: rótulo «Mi
emprendimiento», ícono por ítem y el número de lo que hay cargado.

**`_menu_cuenta.html` no se borró: se repartió.** Queda en las pantallas de «Mi
actividad» y de ajustes (mensajes, favoritos, guardados, editar perfil,
contacto, horarios). Es el mismo corte que ya hacía el menú del avatar desde la
tanda de navegación: lo que me pasa a mí, y lo que administro.

**El contador en cero no se dibuja.** Un «0» al lado de Catálogo no dice nada
que la pantalla no diga mejor, y pinta de pendiente lo que no lo es. Los dos que
sí son pendientes (presupuestos y reseñas sin responder) van en la pastilla
naranja; el resto, en gris.

**No está «Eventos y ferias», que el artboard dibuja**: hoy no hay pantalla de
los eventos propios — un `Event` se carga y se edita desde la ficha de su
emprendimiento, y `/eventos` es la cartelera pública de todos. El ítem entra con
la tanda de eventos, que es la que hace esa pantalla.

### El panel arranca por lo que hay que hacer, no por los números

«Lo que te está esperando» va primero: presupuestos sin responder, mensajes sin
leer, turnos de hoy y reseñas sin contestar. **Solo se dibuja lo que tiene algo
pendiente**, y con las cuatro en cero la sección entera no aparece: una fila que
dice «0 presupuestos» es ruido.

Los tres primeros conteos ya existían escritos a mano adentro de
`/mensajes/notificaciones` (el badge de la barra). Se mudaron a
`app/panel/consultas.py` y esa vista los pide de ahí: el criterio de «esto
espera una respuesta tuya» se define una sola vez.

El turno de hoy se muestra con su servicio, su hora y quién lo sacó, y no como
un número: la fila tiene que servir para saber qué es sin entrar a la agenda.
Los cancelados no cuentan.

### Los números son los cinco que la base sabe contar

Salen tal cual de `perfil.consultas.estadisticas_de_usuario`: suma de
`views_count`, favoritos, promedio y cantidad de reseñas, y seguidores.

**Sin flechitas de variación y sin gráficos.** El canvas del perfil dibujaba
«+18%» y «+9»: no hay con qué calcularlos, porque la consulta da el total de hoy
y no existe histórico. Por lo mismo no hay sparklines ni «visitas por semana».
Si alguna vez se guarda una foto diaria de esas métricas, ahí entra el gráfico.

### Cada emprendimiento dice qué le falta, y uno solo

`_aviso_de()` devuelve el primero que aplique: sin fotos, sin productos ni
servicios, o sin horarios. No los tres apilados — casi siempre vienen juntos (el
emprendimiento recién creado no tiene nada) y tres avisos en una fila la
convierten en un reto. El de los horarios va último aunque sea el más caro de
arreglar: cuelga del **usuario** y no del emprendimiento, así que con dos
emprendimientos aparece en los dos, y decirlo primero taparía lo que sí es de
ese emprendimiento.

### El catálogo del dueño: filas, y el interruptor de «sin stock»

`/productos/mios` era la última pantalla vieja que había dejado la tanda del
catálogo. Ahora es una caja por emprendimiento con sus productos en filas
(foto, nombre, precio, estado y las dos acciones).

**Los grupos se arman desde los emprendimientos y no desde los productos**: el
que no cargó ninguno también aparece, en su caja chica con «Cargar el primero»
al lado. Antes se recorrían los productos y un emprendimiento vacío no existía
en la pantalla.

**El interruptor de «sin stock» es el único backend nuevo de la tanda**: un POST
chico, igual al que ya se había hecho para `/servicios/<id>/disponible`. Hasta
ahora apagar un producto obligaba a abrir el formulario de cinco campos,
releerlos y volver a guardarlos, con el riesgo de pisar algo de paso. Es un
`<form>` de un botón y no un checkbox con JavaScript, por el mismo criterio que
los filtros del catálogo: tiene que andar sin JS. Lleva `aria-pressed` y no
`role="switch"`: para un lector de pantalla es un botón que está apretado o no.
Y el estado se dice además con la palabra al lado («Disponible» / «Sin stock»):
la opacidad de la fila es refuerzo, no el mensaje.

**Del diseño NO están el buscador del catálogo propio, el filtro «Todos», el
orden «Nombre (A-Z)» ni el «Mostrando 5 de 14 · Ver todos»**, que el artboard
dibuja adentro de cada grupo. Con el tope de 50 por emprendimiento las filas
entran todas: serían cuatro controles con backend propio para filtrar una lista
que ya se ve entera.

### En el teléfono el panel no lleva menú lateral

`.panel-menu` se apaga a 879px, como dice la nota del artboard móvil: ocho ítems
arriba de todo dejan el contenido debajo del pliegue. El menú de esas mismas
pantallas es `/perfil/mi-cuenta`, que es adonde va la pestaña Perfil de la barra
de abajo — y ahí se agregó «Mi panel» como primera ficha, a lo ancho. En
escritorio la entrada equivalente está en el menú del avatar, arriba de «Mis
emprendimientos».

Las filas del catálogo se apilan a 768px con sus 44px de alto, para que
«Eliminar» no caiga al lado del pulgar que iba al interruptor.

### Archivos

`app/panel/` (nuevo: `__init__.py`, `consultas.py`, `vistas.py`,
`templates/panel/inicio.html`), `templates/partials/_menu_panel.html` (nuevo),
`templates/products/mios.html`, `templates/partials/_icono_nav.html` (dos íconos
nuevos: `editar` y `eliminar`), `templates/partials/_menu_cuenta_desplegable.html`,
`app/perfil/templates/profile/cuenta.html`, `app/turnos/templates/turnos/agenda.html`,
`app/blog/templates/blog/my_posts.html`,
`app/servicios/templates/servicios/index.html` y `solicitudes.html`,
`app/perfil/templates/profile/reviews.html`, `views/products.py`,
`views/messages.py`, `app/blog/vistas.py`, `app/servicios/vistas.py`,
`app/turnos/vistas.py`, `app/perfil/vistas.py`, `main.py`,
`static/css/styles.css`, `tests/test_panel.py` (18 tests nuevos),
`tests/test_profile.py`, `disenio-inicio/DISENIO.md`.

## Un nombre de clase es un recurso compartido (2026-09-10, de la auditoría de cierre)

Regla que salió de la auditoría del conjunto, después de encontrar el mismo bug
dos veces en las ocho tandas: **antes de bautizar un componente, buscar el nombre
en `styles.css`**. Las ocho tandas escriben en un solo archivo de ~16.700 líneas
donde, a igual especificidad, gana el que va más abajo. Reusar un nombre no da
un error ni rompe ningún test: le cambia el dibujo a una pantalla que nadie
volvió a mirar, y el HTML de esa pantalla sigue igual, así que la suite pasa.

Los dos casos, los dos con la tanda nueva pisando a una pantalla ya pusheada:

- **`.interruptor`** — el interruptor de «sin stock» del panel del vendedor tomó
  las mismas clases que el de los horarios de Cuenta. Le dejaba la pastilla en
  38×22 en vez de 44×26 (abajo del piso de 44 px que fijó la auditoría del 6/9) y
  le cambiaba el fondo a `--color-border`, que es **justo el valor que el bloque
  viejo le pone al estado `:checked`**: el interruptor de horarios terminaba gris
  en los DOS estados y el color dejaba de decir si el día estaba abierto. Ahora
  el del panel es `.interruptor-stock*`.
- **`.resenias`** — la lista plana de reseñas de la ficha tomó el nombre de la
  grilla de dos columnas de «Reseñas recibidas». Su `display: flex` le ganaba al
  `display: grid`, y el resumen del costado se apilaba abajo a todo el ancho en
  vez de ir en su columna de 300 px. Ahora la de la ficha es `.resenias-ficha`.

**Se renombra siempre lo NUEVO, nunca lo viejo**: lo viejo ya está pusheado y
mirado, así que el riesgo se queda del lado de lo que todavía no salió.

Y un corolario para el barrido de CSS muerto: **un bloque duplicado no es
necesariamente borrable**. El análisis de choques sólo ve las propiedades que se
contradicen; las que no chocan cascadean y se suman. La sección vieja de «MI
CATALOGO» parecía muerta y no lo estaba: `.producto` le sigue aportando a
`products/detalle.html` el borde, el radio, el fondo y el `overflow` que el
bloque nuevo no redeclara, y `.catalogo__vacio` vive ahí dentro y es su única
declaración, usada por cuatro pantallas. Se borraron sólo las diez reglas que no
le quedaron a nadie, cruzando cada clase contra todos los templates y el JS como
token entero. Hay tres guardas de esto en `tests/test_css_compartido.py`.

## Dónde retomamos (2026-09-06)

Las ocho tandas están dibujadas, publicadas y commiteadas, y al 9/9 **las ocho
están pasadas a código**: navegación, ficha del emprendimiento, catálogo de
productos, sobre/contacto/errores, el panel de administración, el panel del
vendedor, turnos y ferias y eventos (cada una con su sección más arriba). Antes
de eso, en `27d1710`, ya habían entrado inicio, auth, perfil, ajustes y
servicios.

### Lo único grande que queda: pasar las ocho tandas a código

| Tanda | Carpeta | Canvas |
| --- | --- | --- |
| ~~Navegación global~~ **PASADA A CÓDIGO el 8/9** | `disenio-navegacion/` | https://claude.ai/code/artifact/b752a01f-a2be-495c-b0cf-ac660dc65c84 |
| ~~Ficha del emprendimiento~~ **PASADA A CÓDIGO el 9/9** | `disenio-ficha/` | https://claude.ai/code/artifact/423b9dbb-2c0d-4eb3-87e1-19bf140d1ace |
| ~~Catálogo de productos~~ **PASADA A CÓDIGO el 9/9** | `disenio-productos/` | https://claude.ai/code/artifact/332d05a2-7ac7-4f03-a0fb-de90acf291e9 |
| ~~Panel del vendedor~~ **PASADA A CÓDIGO el 9/9** | `disenio-panel/` | https://claude.ai/code/artifact/538a4d0a-52cb-4781-a7e6-717557523761 |
| ~~Turnos~~ **PASADA A CÓDIGO el 9/9** | `disenio-turnos/` | https://claude.ai/code/artifact/5566643c-7638-485f-85e7-36cf609cfc55 |
| ~~Ferias y eventos~~ **PASADA A CÓDIGO el 9/9** | `disenio-eventos/` | https://claude.ai/code/artifact/c24946a2-195e-4b54-80cc-8bf8fa82c5d6 |
| ~~Panel de administración~~ **PASADA A CÓDIGO el 9/9** | `disenio-admin/` | https://claude.ai/code/artifact/79f57360-70eb-468d-802b-054dfa9bbf44 |
| ~~Sobre, contacto y errores~~ **PASADA A CÓDIGO el 9/9** | `disenio-paginas/` | https://claude.ai/code/artifact/b25d9e60-64a7-4343-a846-68ae02a96ba1 |

**LAS OCHO ESTÁN HECHAS** (ver sus secciones más arriba). Se empezó por
navegación porque toca `templates/base.html` y
`templates/partials/_menu_cuenta.html` —dos archivos, no cada pantalla— y
desbloquea a todas las demás, porque la barra de tres secciones y Publicar en el
menú de la cuenta ya están decididas y dibujadas en las ocho. Se terminó por
eventos, que era la única con migración.

**Lo que sigue es la auditoría del conjunto**, una sola vez sobre las ocho: es
lo que se decidió el 9/9 para no cargar el contexto de cada tanda dos veces y
para no pisar en una lo arreglado en otra (varias comparten la barra, las fichas
de filtro, los parciales y el CSS). Ahí también se decide qué falta agregar.
Recién después se pushea, y después de eso se abre el PR dev_tomy → main.

**Dos cosas para la auditoría, anotadas al cerrar sus tandas:** el repaso a
390 px de turnos y de eventos quedó sin hacer —la extensión de Chrome no estaba
conectada— y las media queries de las dos están escritas pero no miradas en un
navegador.

### Pendientes chicos, que salen al paso de eso

- [ ] **Las dos legales no tienen fecha de última actualización.** Sin eso no se
      puede saber qué versión aceptó cada usuario. Es un dato de Tomás, no se
      inventa. **Ya está el lugar**: `ACTUALIZADA_PRIVACIDAD` y
      `ACTUALIZADA_TERMINOS` en `views/pages.py`, hoy en `None`; con el texto
      cargado ("14 de agosto de 2026") la pastilla aparece sola.
- [ ] **La paleta de rubros de la app no es la de la guía** (`styles.css:6199`): el
      mismo rubro tiene dos colores según la pantalla. Son siete pares.
- [ ] **Faltan los estados del inicio**: cargando y sin resultados.
- [ ] **No hay ningún artboard intermedio (~768 px)** en ninguna de las ocho tandas.
      Sabemos cómo cae todo en 1440 y en 390, y nada de lo que hay en el medio —
      que es donde entra una tablet y una ventana a media pantalla.
