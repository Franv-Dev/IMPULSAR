# Auditoría general del proyecto — 10 de septiembre de 2026

Sobre `main` @ `144a188` (el merge del PR #2, las ocho tandas de rediseño ya
adentro). No es la auditoría de una tanda: es un barrido de todo el sitio antes
de que se siga construyendo encima.

**No se arregló nada en esta pasada.** El objetivo era encontrar y listar, con
evidencia real (app corriendo, no lectura de código), para armar después una
tanda de fixes priorizada.

Todo lo que sigue se verificó contra un servidor descartable (SQLite temporal
en el scratchpad, `UPLOAD_FOLDER` redirigido, ruta `/_entrar/<id>` para entrar
como cualquiera). **`impulsar_db` nunca se tocó**; lo único que corrió contra
MySQL real fue una base `auditoria_largos_tmp` creada y dropeada en el momento.

**Suite completa: 1099 passed, 0 failed** (13 m 54 s), corrida en el momento y
no citada de un reporte anterior.

---

## BUGS REALES

### B1 — Largo de campo sin validar en tres tandas → 500 en producción

`views/eventos.py:157` (`_leer_formulario`) · `views/products.py:130`
(`_leer_formulario`) · `app/servicios/formulario.py:20` (`leer_servicio`)

Ninguna de las tres valida el largo antes del INSERT. Sólo hay `maxlength` en
el HTML, que se saltea con `curl` o borrando el atributo desde el inspector.

Contraprueba contra **MySQL 8 real**, cuyo `sql_mode` incluye
`STRICT_TRANS_TABLES`:

```
eventos    -> DataError (1406, "Data too long for column 'titulo' at row 1")
productos  -> DataError (1406, "Data too long for column 'nombre' at row 1")
servicios  -> DataError (1406, "Data too long for column 'titulo' at row 1")
```

En SQLite entra sin chistar (400 caracteres en columnas de 120 y de 300), y por
eso la suite no lo ve. Control del mismo experimento: `/blog/create` **sí**
rechaza con «no puede tener más de…».

Es exactamente el gap que ya había cerrado la tanda de validaciones con
`MAX_TITULO` (`app/blog/reglas.py:21`) y `MAX_USERNAME_LENGTH`
(`services/validation.py:16`), reintroducido en las tandas nuevas. El comentario
de `app/blog/reglas.py:14-20` describe el problema palabra por palabra.

Campos afectados: `Event.titulo` (120), `Event.descripcion` (300),
`Event.lugar` (120), `Product.nombre` (120), `Product.descripcion` (300),
`Service.titulo` (120), `Service.descripcion` (300),
`Service.zona_cobertura` (120).

**Arreglo:** el mismo patrón de `MAX_TITULO` — la constante sale de
`Columna.type.length`, no de un número escrito a mano, y el chequeo va en el
`_leer_formulario` de cada dominio.

### B2 — El conteo por mes de la cartelera muestra un número falso

`templates/eventos/index.html:118` — `{{ mes.eventos|length }}`, alimentado por
`views/eventos.py:88`, que hace `agrupar_por_mes(paginacion.items)`.

Se agrupa la página, no el total, así que el rótulo de un mes muestra el recorte
de esa página. Con 14 eventos en un mismo mes y `POSTS_POR_PAGINA = 9`, el HTML
real devuelve:

```
pagina 1: [('septiembre 2026','3 eventos'), ('octubre 2026','6 eventos')]
pagina 2: [('octubre 2026','7 eventos'), ('noviembre 2026','2 eventos')]
pagina 3: [('noviembre 2026','1 evento'),  ('marzo 2027','8 eventos')]
```

Octubre real son 13, aparece dos veces y ninguno de los dos números es el suyo.
Marzo real son 14 y dice 8.

El docstring de la vista contempla que un mes se parta entre páginas («es lo
mismo que ya pasa con cualquier corte por fecha»), pero el **contador** quedó
afuera de esa decisión. Es el criterio de honestidad de datos del proyecto: un
rótulo de mes que en realidad cuenta una página.

Es la única pantalla con este problema: todas las demás usan
`paginacion.total` (`admin/emprendimientos.html:29`, `products/catalogo.html:265`,
`blog/index.html:219`, etc.), y los contadores del perfil y del panel cuentan
listas completas.

### B3 — Contraste 1.30:1 en tema oscuro: `--color-on-primary` sobre `--color-primary-deep`

`static/css/styles.css:16395` (`.cartelera__cta-titulo`) ·
`static/css/styles.css:1321` (`.rubro--todos`) ·
`static/css/styles.css:1343` (`.rubro--todos .rubro__tono`)

`--color-on-primary` es la tinta del **primario**, y el primario cambia con el
tema: `#FFFFFF` en claro (`:45`) y `#16132A` en oscuro (`:169`, porque en oscuro
el primario pasa a ser el lila claro `#9B93FF`). `--color-primary-deep`
(`#2A2068`) **no** cambia — es un color de marca, fijo en los dos temas a
propósito. Pareados dan texto casi negro sobre índigo.

Medido con el toggle real de la app (no forzando `data-theme` desde afuera, que
da falsos positivos):

| Elemento | Texto | Fondo | Ratio |
|---|---|---|---|
| «¿Organizás una feria o un taller?» (`/eventos/`) | `rgb(22,19,42)` | `rgb(42,32,104)` | **1.30:1** |
| «Ver todo / N publicados», la octava ficha de rubros (`/`) | `rgb(22,19,42)` | gradiente `#3E2F94→#2A2068` | **≈1.5:1** |

Los demás bloques de marca del proyecto **no** fallan porque escriben `#fff` a
mano: `.perfil-vender` (`:5489`), `.perfil-panel` (`:5536`), `.bloque-marca`
(`:8035`). El hermano `.cartelera__cta-texto` también (`rgba(255,255,255,.82)`,
con el comentario que dice 10.9:1). Son sólo estos dos los que usan el token.

Ironía útil: el comentario de `styles.css:16382-16384` afirma que usa
`--color-primary-deep` «que vale lo mismo en claro y en oscuro» — cierto del
fondo, falso de la tinta que le puso al lado.

**Arreglo:** `color: #fff` literal en los selectores afectados.

> **Corrección (al aplicarse el fix).** Son **cuatro** selectores, no tres: el
> contenedor `.cartelera__cta` (`styles.css:16389`) tenía el mismo
> `--color-on-primary` que su título, así que tocar sólo el título dejaba el bug
> en todo lo que hereda del bloque. Medido después del arreglo con el toggle
> real: **1.30:1 → 13.95:1**, y 13.95:1 también en claro.
>
> Lección para la próxima: cuando un token de color está mal en un elemento,
> mirar el contenedor del que hereda antes de dar la lista por cerrada. Lo que
> se ve mal es el título; lo que está mal puede ser el bloque.

### B4 — El visor de fotos no es un diálogo: el foco no queda adentro

`app/blog/templates/blog/detail.html:120` · `templates/products/detalle.html:212`
· `static/js/visor.js`

Con el visor abierto, medido en la página real:

```
role: null · aria-modal: null · aria-label: null · body[inert]: false
focusables dentro del visor: 3
focusables detrás, todavía alcanzables con Tab: 54
```

Tabular desde la flecha «siguiente» sale del overlay y recorre la página tapada,
que sigue entera y enfocable. Para un lector de pantalla el visor es un `<div>`
sin nombre ni rol.

Lo que **sí** está bien y no hay que tocar: `Escape` cierra, las flechas mueven,
y el foco vuelve al disparador al cerrar (`visor.js` guarda `disparador`).

**Arreglo:** `role="dialog"` + `aria-modal="true"` + un nombre accesible en el
contenedor, y contener el `Tab` (o marcar el resto `inert` mientras está
abierto).

### B5 — Enlaces de foto sin nombre accesible en las tarjetas de producto

`templates/products/catalogo.html:314` · `templates/products/detalle.html:189` ·
`templates/products/guardados.html:59` · `app/blog/templates/blog/detail.html:260`

El `<a class="producto-tarjeta__foto">` envuelve la foto. Si el producto no
tiene foto queda así:

```html
<a href="/productos/20" class="producto-tarjeta__foto"> </a>
```

Un enlace enfocable, sin texto, sin `aria-label`, sin `<img alt>`. En
`/productos/` eran 4 de 12; en `/blog/1`, 18. Y aunque tenga foto, es un segundo
tab-stop que duplica el enlace del título de la tarjeta.

La tanda de navegación lo resolvió bien en `blog/index.html:290` y
`blog/favorites.html:142`, con `tabindex="-1" aria-hidden="true"`. Las tandas de
catálogo y de ficha no copiaron esa parte.

**Arreglo:** el mismo par de atributos que ya usa `.tarjeta__foto`.

### B6 — `aria-pressed` en `<a>`: el estado del chip no se anuncia

`app/blog/templates/blog/index.html:147` y `:154` ·
`templates/products/catalogo.html:161` y `:171` ·
`app/servicios/templates/servicios/buscar.html:167`

`aria-pressed` sólo es válido en `role="button"`. En un `<a href>` (rol
implícito `link`) es inválido y las tecnologías de asistencia lo ignoran: los
chips «Abierto ahora», «Con reseñas», «Disponibles» y «Solo verificados» se
anuncian igual prendidos que apagados.

Los `aria-pressed` que **sí** están bien (todos sobre `<button>`) y no hay que
tocar: `_favorito_boton.html:6`, `products/mios.html:145`,
`servicios/index.html:164`, `base.html:154`, `auth/_ojo.html:18`,
`profile.html:166`, `products/catalogo.html:333`, `products/guardados.html:76`.

**Arreglo:** copiar lo que ya hace bien la cartelera de eventos —
`aria-current="true"` en el enlace activo (`templates/eventos/index.html:57`,
`:72`, `:86`).

---

## MEJORAS RECOMENDADAS

### M1 — Error de sintaxis en `static/css/styles.css:1690`

`.detalle__lateral #map` quedó sin su bloque de declaraciones (lo comió el
commit `e7b25f9`), y el prelude sin cerrar se traga el `@media (max-width: 879px)`
que viene abajo:

```css
.detalle__lateral #map

@media (max-width: 879px) {
    .detalle { grid-template-columns: minmax(0, 1fr); }
}
```

El navegador lee un selector inválido y descarta la regla entera. Confirmado en
`document.styleSheets`: `.detalle__lateral #map` no existe y sobrevive un solo
`.detalle`, el de escritorio.

**Hoy no rompe nada visible**, porque `.detalle` y `.detalle__lateral` ya no las
usa ningún template — son de las 74 clases muertas. Pero es un error de sintaxis
vivo en el archivo y una mina para el día que alguien reviva esas clases.

Es el **único** problema estructural de las 16.658 líneas: el lint de todo el
archivo devolvió 1.

### M2 — No hay skip link

Ninguna pantalla ofrece «saltar al contenido». Con 51 a 98 elementos enfocables
por página y la barra de navegación repetida en todas, el teclado atraviesa el
header entero en cada carga. Es WCAG 2.4.1.

Lo que sí está bien: landmarks (`header`/`nav`/`main`/`footer`) en todas, un solo
`<h1>` por pantalla, cero `tabindex` positivos.

### M3 — Targets táctiles entre 32 y 44 px

A 390 px de ancho: `.calendario__nav-btn` 34×34, `.calendario__dia` 40×40,
`.theme-toggle` 40×40, `.barra-filtros__buscar` 39 de alto.

Están arriba del piso de 32 px que fijó la auditoría del 29/8, abajo de los 44
que el propio CSS declara como estándar del proyecto (`styles.css:5250`: «es el
piso tocable del proyecto, no una sugerencia»). Hay que decidir cuál de los dos
vale.

### M4 — `escapeHtmlChat` no escapa comillas

`static/js/chat.js:5` escapa `& < >`; `main.js:4` escapa los cinco. Hoy sólo se
usa en contenido de elemento, así que no explota. Es una divergencia que muerde
el día que alguien mueva ese texto a un atributo.

### M5 — `events.tipo` sin CHECK en la base

La taxonomía cerrada de `TiposEvento` se valida sólo en la vista
(`views/eventos.py:180`). `Review.rating` sí tiene su `CheckConstraint`. Un
import o un script pueden meter un quinto tipo que después no filtra por ningún
chip.

---

## COSMÉTICO / BACKLOG

- `.dato__estrella` ★ 1.88:1 en claro y `.migas__sep` › 1.44:1 en oscuro:
  decorativos al lado de un texto que sí se lee.
- `.ficha-galeria__contador`: blanco sobre velo `rgba(10,8,28,.5)` encima de la
  foto, así que el contraste depende de la foto y no tiene piso garantizado.
- El encabezado de la cartelera dice «N fechas anunciadas por los
  emprendimientos» con un tipo filtrado puesto, sin nombrar el filtro. Al lado
  está «Ver todas las fechas», así que no miente del todo.
- `.buscador-nav:focus-within` marca la barra entera y no el campo: «Qué buscás»
  y «Dónde» se ven igual enfocados.

---

## Frentes que dieron limpio (y cómo se comprobó)

**CSS entre tandas — sin un cuarto choque.** Se cruzó cada selector de las
16.658 líneas consigo mismo: **22 con alguna propiedad contradictoria**. Se
revisaron uno por uno y ninguno es un choque tipo `.interruptor` / `.resenias`:
son los 21 ya documentados (diferencias de redondeo, y pisadas deliberadas por
orden de archivo — `.cartelera__cta`, `.catalogo__grilla`, `.producto*`) más
`.interruptor-boton`, que resultó ser un refinamiento adyacente dentro de su
propia sección, con un solo template usándolo
(`app/servicios/templates/servicios/index.html:163`).

*Límite del método, dicho a propósito:* esto ve **nombres de clase idénticos**,
que es la forma que tuvieron los tres hallazgos de la auditoría de cierre. No ve
un descendiente de una tanda alcanzando el markup de otra.

**Sin N+1 nuevo.** Se contaron las consultas SQL de 15 pantallas y se volvieron
a contar después de multiplicar filas (15 eventos + 15 productos + 15 servicios,
y después 9 emprendimientos nuevos con hijos). Delta **0 en todas**: home 3,
`/blog/` 4, ficha 12, panel 23, agenda 12, admin 14, perfil 13, constantes.
`/servicios/` subió 1 y se quedó ahí en las tres rondas, o sea que no escala.
Con `expunge_all()` antes de cada medición, para que el identity map no diera un
falso negativo.

**Sin XSS.** Se inyectó `<img src=x onerror=…>` y `"><svg/onload=…>` por bio,
ubicación, título/descripción/lugar de evento, producto y reseña, y se parseó el
DOM resultante de 8 pantallas buscando handlers `on*` y `javascript:` reales:
**0 hallazgos**. `render_biography` escapa primero y linkea sólo `https?://`.
(Ojo al método: buscar el payload como texto en el HTML da falsos positivos —
aparece escapado. Hay que parsear.)

**Sin path traversal.** `../../../evil.png`, `..\..\evil2.png`,
`/etc/passwd.png` y `....//evil3.png` aterrizan todos dentro de uploads
(`cc5a8c46_evil.png`, `704cb85a_etc_passwd.png`); 0 archivos escapados.
`/static/uploads/../../config.py` → 404. Las fotos privadas → 403 al tercero.

**Permisos server-side.** Las 11 rutas de `views/admin.py` llevan
`@admin_required`; el resto resuelve dueño o parte en la vista
(`_evento_propio`, `_servicio_propio`, `_solicitud_visible`, `_turno_visible`).
Ningún panel de dueño o de admin se esconde sólo con CSS.

**CSRF.** Ningún `<form method="post">` sin `csrf_token`. Exenciones: sólo
`posts_api` (que es GET) y las dos rutas JWT.

**IDs duplicados, `alt` faltantes, inputs sin label, botones sin nombre:** 0 en
las 21 pantallas barridas.

---

## Notas de método (para la próxima)

- **El tema oscuro se cambia con el botón de la app o con
  `localStorage['impulsar-tema']='dark'` ANTES de cargar la página.** Forzar
  `data-theme` sobre un documento ya pintado da falsos positivos: en la primera
  pasada dio tres «hallazgos» de contraste en la navbar y la paginación que al
  medirlos de nuevo con el toggle real estaban en 9:1 y 6:1.
- Un medidor de contraste que sube por el DOM buscando el primer fondo opaco
  **miente sobre velos y gradientes**. Los dos casos de esta auditoría
  (`.ficha-galeria__contador` sobre `rgba(...,.5)`, y `.rubro--todos` sobre un
  gradiente) hubo que mirarlos a mano.
- Para probar el largo de columna hay que ir a MySQL: SQLite acepta cualquier
  cosa y tapa la clase entera de bugs.

## Documentos relacionados

- `docs/CONTEXTO.md` — estado del proyecto y backlog.
- `docs/AUDITORIA-VISUAL-29-8.md` — auditoría visual del 29/8; de ahí sale el
  criterio de targets táctiles («44 px, o 32 px como piso») que M3 discute.
