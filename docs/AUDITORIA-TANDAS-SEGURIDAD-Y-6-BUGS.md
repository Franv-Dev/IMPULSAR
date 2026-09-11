# Auditoría de las dos tandas (seguridad + los 6 bugs) — 10 de septiembre de 2026

Sobre el working tree sin commitear en `main`: 24 archivos modificados y 7
nuevos. Alcance acotado a esas dos tandas — el barrido general del proyecto ya
se hizo el 10/9 y está en `docs/AUDITORIA-GENERAL-10-9.md`.

Relevamiento, no arreglo: **no se tocó una sola línea de código** de las tandas.

Todo se corrió contra SQLite temporal en el scratchpad y bases MySQL
descartables (`auditoria_largos_tmp`, `auditoria_foto_tmp`,
`auditoria_groupby_tmp`, creadas y dropeadas en el momento). **`impulsar_db`
nunca se tocó.** La suite completa no se volvió a correr acá: la corrió Sesión 1
(1173 passed, 0 failed) y correrla en paralelo fue lo que agotó la RAM antes.

La numeración **H1–H4** es de este documento. **B1–B6** son los seis bugs de la
auditoría general y **S1–S4** los del rate-limit; acá se usan sólo para
referirse a los arreglos que verifican.

---

## Verificado: lo que está bien

Cada punto con el método propio, no repitiendo el número reportado.

### B1 — validación de largos

27 tests recolectados, 27 pasan. Para saber si **discriminan**, se apagó
`validar_largo` con un plugin de pytest que lo parchea en los tres módulos que
lo importan por nombre (`views.eventos`, `views.products`,
`app.servicios.formulario`) — sin tocar ningún archivo del repo:

```
con la validación puesta:   27 passed
con la validación apagada:  17 failed, 10 passed
```

Los 10 que sobreviven son correctos por diseño y no son relleno: los 8 de
«justo en el límite SÍ se guarda» (el lado de no rechazar de más),
`test_los_maximos_son_los_de_las_columnas` (lee `largo_de`, no pasa por las
vistas) y `test_en_mysql_estricto_el_texto_largo_no_entra` (prueba que MySQL
rechaza, no que la app valide).

### B2 — conteo por mes de la cartelera

Reproducido de cero con 16 eventos: la página muestra 9 filas y el encabezado
de septiembre dice «14 eventos» — el total del mes, no el de la página.

Se probó además la combinación que no tenía test, `?dia=`:

| URL | header del mes | filas en la página |
|---|---|---|
| `?dia=2026-09-15` | 3 eventos | 3 |
| `?dia=2026-09-15&libre=1` | 1 evento | 1 |
| `?tipo=feria` | sept 3 / abr 2 | 5 |
| sin filtros | 14 eventos | 9 |

El número siempre corresponde al filtro activo y coincide con lo que se muestra.
Sin inconsistencia. (Pero ver **H2** sobre lo que sostiene este arreglo.)

### B3 — contraste

Con el toggle real de la app, en los dos temas. Los cuatro selectores dan
**13,95:1**. Dos precisiones sobre ese número, para que quede exacto:

- `.rubro--todos` va sobre un **gradiente**, así que su peor punto es el extremo
  claro: **10,30:1**, no 13,95. Sigue muy por encima de AA.
- `.cartelera__cta-texto`, compuesto con su alfa 0.82, da **9,81:1**. El 13,95
  sale de medir el blanco sin componer.
- `.rubro__nombre`, que **hereda** del contenedor y fue el motivo del cuarto
  selector, quedó en 13,95:1.

### B4 — trap de foco del visor

El tab estaba en segundo plano (`visibilityState: "hidden"`), así que las teclas
reales no llegaban al documento. Se ejercitó el handler con la matriz completa:

| caso | previene | foco resultante |
|---|---|---|
| último + Tab | sí | primero |
| primero + Shift+Tab | sí | último |
| medio + Tab | **no** (lo mueve el navegador) | siguiente |
| medio + Shift+Tab | **no** | anterior |
| foco afuera + Tab | sí | primero |
| visor cerrado + Tab | **no** | no se mueve |

Escape cierra, limpia `body.con-visor` y devuelve el foco al disparador exacto
(`ficha-galeria__chica`, el que lo abrió). El caso de una sola foto
(`/productos/19`, un único focusable) también: Tab y Shift+Tab se quedan ahí.

Nota: el filtro `offsetParent !== null` de `focosDelVisor()` parecía riesgoso
porque `.visor` es `position: fixed` y ahí `offsetParent` es `null` — pero
`.visor__cerrar` y `.visor__flecha` son `absolute` **dentro** del fixed, así que
su `offsetParent` es el propio visor. Devuelve los 3. Falsa alarma, verificada.

### B5 — el cartel «Sin stock» fuera del enlace

Medido: catálogo **10/10 px** desde la esquina de su foto, ficha **9/9 px**,
fuera de `aria-hidden`, anclados a la tarjeta, encima de la foto — también en
las tarjetas **sin** foto. A **386 px** siguen en 10/10 y `elementFromPoint`
sobre el centro del cartel devuelve el cartel, no el enlace.

Y no hay breakpoint donde se descoloque: de las 4 reglas de
`.producto-tarjeta*`/`.producto-ficha*` que viven dentro de un `@media`, ninguna
toca `position`, `z-index`, `overflow` ni `inset` — sólo `font-size` y
`padding` de `__cuerpo`.

### B6 — `aria-pressed`

Los 8 `aria-pressed` que quedan en los templates están todos sobre `<button>`,
que es uso válido. `tests/test_follows.py:102` sigue afirmando
`aria-pressed="false"`, pero sobre el botón de seguir — también válido.

### S1 / S2 / S4 — rate limit

Se repitió el ataque original contra el código de ahora:

```
alternando /auth/login y /auth/api/login   -> primer 429 en el intento 6  (antes: 11)
alternando Panadería / panaderia / PANADERIA -> primer 429 en el intento 6
usuario que no existe                      -> primer 429 en el intento 6
solo el formulario (control)               -> primer 429 en el intento 6
```

Tras 4 fallos + 1 acierto queda `{'login:ip:127.0.0.1': 4}`: limpia las dos
claves de cuenta, conserva la de IP.

### Nonce de la CSP

Tres respuestas seguidas a `/`: tres nonces distintos, y en cada una el de la
cabecera coincide con el del `<script>` inline.

---

## Hallazgos nuevos

### H1 — El nombre de archivo generado no se valida, y va a una columna de 100

**`services/uploads.py:166`**

```python
filename = f"{uuid.uuid4().hex[:8]}_{secure_filename(file.filename)}"
```

El uuid suma 9 caracteres y el nombre original no se recorta nunca. Un nombre de
archivo de **100 caracteres** —legal, nada rebuscado, del estilo
`Bolson semanal chico - foto del producto para el catalogo de la huerta - septiembre 2026 - final.png`—
produce 109 y no entra en la columna.

Contra **MySQL 8 real en modo estricto**:

```
DataError (1406, "Data too long for column 'foto' at row 1")
```

Contra SQLite: `HTTP 302`, y la fila queda con **109 caracteres en una columna
de 100**. Ningún test sube un nombre largo.

Es exactamente la clase de B1, sobre el único campo de texto que la tanda no
podía ver buscando formularios: no se tipea, se deriva del archivo que el
usuario elige. Afecta **7 columnas** de `String(100)` —`Product.foto`,
`User.avatar`, `User.cover_image`, `PostImage.filename`, `Post.image`,
`ServiceRequest.foto`, `VerificacionServicio.foto`— por las 8 llamadas a
`save_post_image`: `views/products.py:732,787`,
`app/blog/vistas.py:111,319,392`, `app/perfil/vistas.py:329,343`,
`app/servicios/vistas.py:406,628`.

**Arreglo:** recortar la base en `save_post_image` dejando la extensión, de modo
que `uuid + "_" + nombre` entre siempre. Un solo lugar cubre las ocho llamadas.

### H2 — El `order_by(None)` de B2 no tiene ninguna red que lo sostenga

**`tests/test_cartelera_conteo.py`** (ausencia) · **`services/eventos.py:142`**

`test_largos.py` prueba contra MySQL real (9 de sus 27 casos).
`test_cartelera_conteo.py` **no tiene un solo test contra MySQL**, y el
`order_by(None)` existe únicamente por un fallo que sólo ocurre ahí.

Comprobado por los dos lados. Contra MySQL 8, sacándolo:

```
OperationalError (1055, "Expression #1 of ORDER BY clause is not in
GROUP BY clause and contains nonaggregated column...")
```

Y parcheando `total_por_mes` a la versión sin `order_by(None)`, sobre SQLite:

```
tests/test_cartelera_conteo.py + tests/test_eventos.py  ->  124 passed
```

La suite entera se queda verde ante un 500 de producción. El arreglo es
correcto; lo que falta es el test que impida que alguien lo saque.

**Arreglo:** un test de `total_por_mes` contra MySQL, con el mismo andamiaje
que ya usa `test_largos.py` (`app_en_mysql`, base descartable, se saltea sola si
el `sql_mode` no es estricto).

### H3 — Quedó un quinto `--color-on-primary` sobre fondo de marca

**`static/css/styles.css:16426-16429`** y su `:hover` en **`:16432`**

```css
.cartelera__cta-boton {
    background-color: var(--color-on-primary);   /* #FFFFFF claro → #16132A oscuro */
    color: var(--color-primary-hover);
}
```

Es el mismo token con el mismo problema, **en el mismo bloque que se arregló**,
pero usado como `background-color` en vez de como `color` — por eso no apareció
al buscar el `color`.

Medido en oscuro con el toggle real: el botón queda `rgb(22,19,42)` sobre el
panel `rgb(42,32,104)`. **Superficie del botón contra el panel: 1,30:1**, con
borde transparente. El mismo 1,30:1 que el fix le sacó al título.

El **texto** no falla (8,84:1 contra su propio fondo), así que no lo agarra un
medidor de contraste de texto. Lo que falla es el **borde del control**: WCAG
1.4.11 pide 3:1. El comentario que está justo arriba dice «Blanco sobre el
índigo: acá el botón primario índigo desaparecería» — en oscuro deja de ser
blanco y desaparece igual. El `:hover` tiene lo mismo: `--color-primary-soft` es
`#2E2950` en oscuro.

Es el **único** caso que queda: se cruzaron los 22 usos de
`var(--color-on-primary)` del archivo y los otros 21 están sobre
`--color-primary`, que sí sigue al tema — uso correcto del token.

**Arreglo:** `background-color: #fff` y `color: var(--color-primary-deep)` (o el
índigo fijo), igual que hacen los demás bloques de marca.

### H4 — `largo_de()` sobre una columna `Text` devuelve `None` y revienta al validar

**`services/validation.py:74`**

```
largo_de(ServiceRequest.descripcion)            ->  None
validar_largo('x'*10, None, 'La descripción')   ->  TypeError: '>' not supported
                                                    between instances of 'int' and 'NoneType'
```

Hoy no muerde: los 8 campos validados son `String`. Pero el docstring de
`largo_de` invita a usarlo en cualquier columna de texto, y hay una `Text` a
mano en el mismo dominio (`ServiceRequest.descripcion`, que es `Text` a
propósito). El día que alguien la sume, el error no aparece al importar sino en
el primer POST, como 500.

**Arreglo:** un `assert` (o un `raise` explicativo) en `largo_de` cuando la
columna no tiene `length`. Convierte un 500 en un error de arranque.

---

## Nota de método

**`frame-ancestors 'none'` rompió el truco del iframe** que se venía usando para
medir a 390 px: con `src`, `contentDocument` viene `null`. El reemplazo que
funciona es `srcdoc`, que no lleva cabecera CSP propia, con un `<base>`
inyectado para que el CSS y el JS relativos resuelvan:

```js
const html = await fetch(ruta).then(r => r.text());
iframe.srcdoc = html.replace('<head>', '<head><base href="' + location.origin + '/">');
```

No es un problema de la tanda —es el efecto buscado de la cabecera— pero
cualquier verificación responsive futura tiene que ir por ahí.

## Fuera de alcance, sin acción

- `.calendario__weekdays` (Lu/Ma/Mi…) está `aria-hidden` y lo dibuja
  `calendario.js`, que no está en este diff. Preexistente.
- El resto de los `aria-hidden` con texto que marcó el barrido automático
  (`.evento__fecha`, `.ficha-feria__fecha`, `.tarjeta__avatar`) son falsos
  positivos: el dato completo está al lado y visible
  (`.ficha-feria__detalle` lleva la fecha larga, la tarjeta lleva el nombre del
  autor). Ninguno silencia información única.
