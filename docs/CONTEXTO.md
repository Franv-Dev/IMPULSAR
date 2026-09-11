# IMPULSAR — Contexto para retomar

**Última actualización: 10 de septiembre de 2026.** Perfil público, Cuenta, Turnos, calendario, grilla de rubros, Home, Emprendedor, Gestión, Explorar (radio + reseñas + "Abierto ahora"), "Mis servicios" en el menú de cuenta, reordenar fotos/elegir principal, la tanda de validaciones de backend (precios, horarios, título, contacto, views_count), notificaciones por email (Flask-Mail/Gmail, 3 disparadores), búsqueda en catálogo (productos/servicios disponibles, no solo título/body del post), Mis favoritos (orden por fecha de marcado con desempate, filtro por rubro, orden A-Z), tanda chica de backlog (mensaje de hora inválida, assert→ValueError en reordenar fotos, botón duplicado sacado), y la tanda de rediseño del home (buscador unificado, rubros con ícono SVG en grilla 4×2, tarjetas verticales tipo `.tarjeta`, `/api/posts/` con avg_rating/review_count/author_name): todos CERRADOS Y PUSHEADOS. Y los dos "chips que mienten" de la barra de filtros de `/blog/`, AUDITADOS Y PUSHEADOS los dos: el chip de cercanía (cerrado el 7/9, auditado y pusheado el 8/9 en `00e7132`) y el `<summary>` de la barra de filtros, segundo hallazgo de esa misma tanda (cerrado, auditado y pusheado el 8/9 en `e221f67` + `d3d5739`). Y la unificación de `CAMPOS_DEL_PERFIL`, cerrada el 8/9, auditada y pusheada el mismo día en `e0b7c03` + `7c51f92`. Y **LAS OCHO TANDAS DE REDISEÑO, AUDITADAS JUNTAS Y PUSHEADAS**: **navegación** (8/9), **ficha del emprendimiento**, **catálogo de productos**, **sobre/contacto/errores**, **panel de administración**, **panel del vendedor**, **turnos** y **ferias y eventos** (pasadas a código el 9/9), auditadas de punta a punta el 10/9 en una sola vuelta sobre el conjunto, como decía el plan. **La auditoría encontró tres bugs reales y los tres se arreglaron en la misma vuelta**: el vacío de la cartelera que decía «todavía no hay eventos» con la base llena de eventos vencidos, y dos choques de nombres de clase en el `styles.css` compartido (`.interruptor`, que dejaba el interruptor de horarios gris en los dos estados, y `.resenias`, que le rompía la grilla de dos columnas a «Reseñas recibidas»). Los dos choques son ENTRE tandas, o sea justo lo que auditar de a una no habría encontrado. Detalle completo en «Auditoría de cierre del rediseño». **El rediseño global por secciones está CERRADO.** Lo único pendiente es abrir el PR dev_tomy → main. **El hash del remoto ya no se anota acá**: quedó viejo tres veces seguidas (decía 27d1710, después 4eba082, después `d3d5739`), siempre porque el commit que lo escribía cambiaba el remoto al pushearse — un dato que se invalida solo en el acto de guardarlo. Se consulta con `git ls-remote origin dev_tomy`, que es la fuente real. **1099 tests passed** (corridos completos por la auditoría el 10/9, no heredados de un reporte: 1094 antes de la auditoría + 2 del tercer vacío de la cartelera + 3 guardas de clases compartidas). Sobre el número: la suite medida en limpio el 7/9 daba 873 antes del fix del chip, con `tests/` byte a byte idéntico a 27d1710, así que el 877 que figuraba acá estaba mal anotado (no se borró ningún test); 873 + 3 del chip = 876, + 2 del `<summary>` = 878, + 4 de `CAMPOS_DEL_PERFIL` = 882.

## Qué es

Plataforma web para dar visibilidad a emprendimientos locales (Mendoza, Argentina). Registro, publicación con foto y ubicación, listado, búsqueda, reseñas. Proyecto académico con intención de escalar a algo real. Repo Franv-Dev/IMPULSAR. main en 008e1d5 (PR #1 mergeado). Rama de trabajo: dev_tomy. Remoto y local sincronizados en 27d1710.

Frentes en curso:

- Calendario del home: CERRADO (Tanda 1 de agenda).
- Turnos: CERRADO por completo (2a + 2b).
- Grilla de rubros en el home: CERRADA y pusheada, y ahora rediseñada de nuevo con íconos SVG en la tanda del 6/9 (ver abajo).
- Cuenta (4 pantallas): CERRADA y pusheada.
- Perfil público: CERRADO y pusheado (427d419).
- Rediseño visual (paleta índigo): **CERRADO** (era el frente grande). Las ocho tandas dibujadas se pasaron a código el 8 y 9/9, se auditaron juntas el 10/9 y están pusheadas; ver sus secciones abajo y «Auditoría de cierre del rediseño». Home, Emprendedor, Gestión y Explorar (radio + reseñas + "Abierto ahora") ya estaban cerrados y pusheados de antes. Home recibió una segunda pasada de rediseño el 6/9 (buscador unificado, rubros con ícono, cards verticales).
- Separación de navegación emprendimientos/servicios: CERRADA Y PUSHEADA (5fdcf44).

**Lo único pendiente: abrir el PR dev_tomy → main.** La condición que lo tenía pospuesto («que el rediseño visual esté razonablemente completo») se cumplió el 10/9 con la auditoría del conjunto aprobada. El PR NO se abrió todavía: se confirma con Tomy antes.

## Stack

Python 3.11+, Flask 3.1, SQLAlchemy 2.0, Flask-Migrate. MySQL 8 local. Sesiones (frontend) + JWT (API). HTML/CSS/JS sin framework, Jinja2. Mapas: MapTiler + MapLibre GL JS pineado a 5.24.0. Tests: pytest sobre SQLite en memoria (PRAGMA foreign_keys=ON activo). CI: GitHub Actions. SO de trabajo: Windows (carpeta local del repo: C:/Users/TOMY/Documents/IMPULSAR). Entrypoint canónico: `wsgi.py` (`flask --app wsgi`) — no `main.py`. Seed: `python -m scripts.seed`. Server de dev de Tomy en http://127.0.0.1:5000 contra impulsar_db. MAPTILER_KEY vacía en .env — tiles en 403, mapa en blanco con solo el marker, hasta que Tomy cargue una key de cloud.maptiler.com. Nota estructural: no existe `app/models.py` único — los modelos están repartidos en `models/user.py`, `models/event.py`, `models/product.py`, `models/message.py`, más los que cuelgan de cada dominio (`app/blog/modelo_post.py`, `app/blog/modelo_reporte.py`, `app/blog/modelo_resenia.py`, `app/servicios/modelo.py`, `app/servicios/modelo_verificacion.py`).

## Cómo veníamos trabajando (histórico, sirve como referencia de método)

Hasta ahora Tomy coordinaba tres terminales de Claude Code en su misma carpeta local del repo, cada una con un rol fijo:

- **Sesión 1** — escribe código de backend/lógica/producto (no diseño visual). Implementa lo que se le pasa en un prompt, corre pytest, prueba contra MySQL real, comitea (un commit por punto), pushea cuando se le pide, nunca se autoaudita.
- **Sesión 2** — solo audita. No escribe código en general, salvo fixes chicos coordinados con Sesión 1 dentro de la misma auditoría cuando hay luz verde explícita para no volver a pedir otra vuelta. Reporta bugs reales vs. mejoras opcionales, sin mezclar gravedad. Arma su propio chequeo independiente al verificar un fix, no reusa el test/harness de quien escribió.
- **Sesión 3** — dedicada al rediseño/mejoras visuales. Escribe templates/CSS, comitea por pieza, nunca se autoaudita.

Reglas que siguen valiendo para cualquiera que trabaje en este repo, sea una persona o una sesión de Claude:

- Nunca `git add -A` ni `git add .` — siempre archivos por nombre explícito. `git status` antes de cualquier commit.
- Verificar push con `git ls-remote` y `git fetch origin dev_tomy && git log --oneline origin/dev_tomy..HEAD` — pushear el propio commit puede arrastrar o dejar afuera commits de otra tanda que ya estaban commiteados localmente.
- Push a origin/dev_tomy solo cuando la revisión sale limpia (o con solo mejoras opcionales, nunca con bugs reales pendientes).
- Tandas grandes/migraciones/permisos/lógica de fechas-horarios: revisión COMPLETA. Cambios chicos y acotados: revisión LIVIANA. La tanda de rediseño del home (6/9) recibió revisión completa por tocar API pública y home entero.
- Una sola vuelta de revisión para cambios chicos/acotados — si encuentra algo bloqueante, se arregla ahí mismo con la suite en verde, sin pedir una segunda pasada de re-chequeo.
- Agrupar cambios de código en tandas semi-grandes, no cambios chicos sueltos — evita gastar tiempo/tokens en el costo fijo de coordinar y revisar cada uno por separado.
- Backlog del modelo/producto se documenta en este doc, sección Backlog pendiente — no como issue de GitHub ni comentario suelto.
- Contraprueba real por sobre solo releer el código o solo afirmar — verificar con datos/casos concretos, no de fe.

## Trabajando en equipo (Tomy + colaborador), a partir de septiembre 2026

Ahora el proyecto lo llevan dos personas — Tomy y un compañero — cada uno con su propio clon del repo, dividiendo backend/frontend por partes y trabajando en momentos separados (no simultáneo sobre el repo). Para que esto funcione sin pisarse:

- **Antes de arrancar a trabajar:** `git pull` de dev_tomy para traer lo último que hizo el otro.
- **Al terminar una tanda:** commitear, actualizar este mismo archivo (`docs/CONTEXTO.md`) con qué se hizo/qué falta, y pushear todo junto — código y documentación en el mismo empujón. Este archivo es la única fuente de verdad compartida entre las dos máquinas: si no se actualiza, el que sigue no sabe dónde quedó el otro.
- Cualquier Claude Code que arranque en este repo debería leer este archivo primero, antes de tocar código, para tener el mismo contexto que las sesiones anteriores.

## Home — rediseño (buscador, rubros con ícono, cards, API) — CERRADO Y PUSHEADO

Contexto: tanda de rediseño visual del home coordinada con Sesión 3 más el cambio de API necesario para mostrarlo. Se pidió revisión COMPLETA (no la liviana de cambios chicos) antes de pushear, por tocar API pública y el home entero.

Cambios: buscador unificado, rubros con ícono SVG en grilla 4×2, tarjetas verticales tipo `.tarjeta` (mismo componente del listado), `/api/posts/` ahora agrega avg_rating, review_count y author_name vía el mismo `query_posts_con_rating()` que ya usaba el listado (outerjoin contra subquery agrupada por post_id, sin query nueva).

Auditoría completa de Sesión 2 (6/9): APROBADA tras aplicar 4 fixes ella misma, en la misma vuelta.

- Performance confirmada, no asumida: 2 consultas fijas medidas con 5/20/40 posts, identity map vaciado entre corridas — sin N+1 ni filas duplicadas; author_name no suma consultas porque author_user es `lazy="joined"`.
- Shape de API aditivo: entran las 3 claves nuevas, no se pierde ninguna existente, paginado igual, favorito sigue sin viajar sin sesión. Único consumidor real es main.js — ni el listado ni el admin leen `/api/posts/`, así que no hay contrato roto en otra parte.
- Grid 4×2 a prueba de ceros: el bucle recorre los 7 `Categorias.ETIQUETAS` con `.get(clave, 0)` más la ficha "Ver todo" = 8 celdas siempre. Un rubro en cero dibuja su ficha normal con "0 activos", no rompe el grid ni deja hueco.
- Contraste verificado en los 7 pares de color: 4.64–5.11:1 en modo claro, 5.68–7.00:1 en oscuro. Blanco al 72% de "Ver todo": 6.15:1.
- Honestidad de datos confirmada: la tarjeta solo muestra avg_rating, review_count y author_name — nada de "abierto ahora", km o barrio inventado, tal como se había dejado afuera a propósito.
- CSS sin residuo de intentos previos descartados: el único comentario que apunta a `redisenio/project/` es correcto — esa carpeta existe local y está en .gitignore, no es un rastro de la paleta equivocada de un intento anterior.

4 fixes aplicados por Sesión 2 dentro de la misma auditoría:

- Tres controles bajo 44px en mobile ("Cerca de mí" a 34px, dos botones sobre la foto a 38×38, "Ver" del pie a 32px) — piso de 44px aplicado solo en la media query de 860px. Verificado en iframe de 390px: los tres a 44/44/44, sin scroll horizontal nuevo.
- La pastilla del rubro vivía dentro de un `<a aria-hidden>` de la foto y no se anunciaba a lectores de pantalla — pasada a ser hermana del link, con z-index para mantener la posición visual.
- Las iniciales del avatar se armaban desde el nombre ya escapado en HTML (`&a`, `&l` con nombres que empiezan con `&`, `<`, `"` o `'`) — corregido para tomar el nombre crudo antes del escape.
- CSS muerto del cambio `.ficha` → `.tarjeta`: se fueron `.ficha` y sus nueve hijos, y `.resultados__grid`. Sobreviven `.ficha__rating` y `.ficha__estrella` porque detail.html los sigue usando.

Todo documentado en `disenio-inicio/DISENIO.md` del repo.

Push (6/9): confirmado. 27d1710 en dev_tomy.

Tests: 877 passed (número corregido — un reporte previo decía 834, desactualizado; se corrió la suite dos veces, verde antes y después de los 4 fixes).

Estado: CERRADO POR COMPLETO.

Nota de proceso: `disenio-navegacion/` quedó deliberadamente fuera de este commit — se estaba escribiendo en paralelo en otra carpeta de diseño, se commitea aparte cuando cierre esa tanda.

## Chip de cercanía que miente — CERRADO (7/9), AUDITADO Y PUSHEADO (8/9)

Item que estaba en Backlog pendiente: el chip de cercanía tenía la misma falla del "chip que miente" ya corregida en el chip de radio. En `app/blog/templates/blog/index.html` el chip "Cerca de {{ cerca_de_actual }}" se pintaba con que `cerca_de_actual` tuviera texto, sin mirar si la dirección se había podido geocodificar. Cuando MapTiler no la resuelve (o no hay `MAPTILER_KEY`), la vista deja `lat` en None, la consulta devuelve el listado entero sin ordenar por cercanía, y el chip aparecía igual con su "×" — ofreciendo sacar un filtro que nunca se aplicó.

Fix, con el mismo criterio que el radio (mirar `ordenado_por_distancia`, no `request.args.lat`, porque las coordenadas de una dirección las resuelve la vista y nunca están en la URL):

- Se nombró la condición una sola vez, `{% set cercania_aplicada = cerca_de_actual and ordenado_por_distancia %}`, en vez de repetirla en los tres lugares que la necesitan.
- `hay_filtros` ahora cuenta `cercania_aplicada` en lugar de `cerca_de_actual` solo.
- El `{% if %}` del chip pasa a mirar `cercania_aplicada`.
- El `{% if %}` que envuelve todo el `<div class="chips">` también, para no dibujar el contenedor vacío cuando "near" es lo único que viaja en la URL.
- NO se tocó el `<input name="near">`: conservar lo tipeado no es un chip que miente, y vaciarlo obligaría a reescribir la dirección después del aviso de que no se pudo ubicar. Hay un test que lo fija.

3 tests nuevos en `tests/test_blog.py`, sección cercanía: `test_una_direccion_que_no_geocodifica_no_pinta_su_chip` (el bug), `test_una_direccion_que_no_geocodifica_conserva_lo_que_se_tipeo` (la guarda del input) y `test_con_la_direccion_geocodificada_el_chip_de_cercania_si_aparece` (la contracara: cuando sí acota, el chip tiene que estar).

Contraprueba hecha, no solo suite en verde: se revirtió el template dejando los tests puestos y el test del bug pasó a rojo mostrando el chip con su `aria-label` renderizado; con el fix vuelve a verde.

Tests: 876 passed. Ojo con el número: la suite medida en limpio en esta máquina antes del cambio daba **873**, no los 877 que decía este documento, con `tests/` byte a byte idéntico a 27d1710. O sea que el 877 estaba mal anotado, no es que se hayan borrado tests. 873 + 3 nuevos = 876.

Hallazgos colaterales, NO arreglados en esta tanda (van a backlog, para no mezclar con el fix pedido):

- La tercera aserción de `test_sin_coordenadas_el_radio_no_pinta_su_chip` estaba muerta: verificaba `class="filtros__limpiar"`, clase que el rediseño renombró a `ficha-filtro--limpiar` en este template (`filtros__limpiar` hoy solo vive en `servicios/buscar.html`, otra pantalla). Pasaba siempre, mirara lo que mirara. ARREGLADO en la auditoría del 8/9, commit aparte: ahora mira `ficha-filtro--limpiar`. Se verificó que la aserción corregida tiene mordida real (`/blog/?q=` sí pinta esa clase, `/blog/?radio=1` no). Barrido hecho sobre los cinco `tests/test_*.py`, cruzando cada clase BEM afirmada contra el template que renderiza la ruta de su test: esta era la única aserción apuntando a una clase vieja del rediseño.
- El `<summary>` de la barra de filtros (`barra-filtros__resumen-detalle`) anunciaba "cerca de {{ cerca_de_actual }}" sin mirar si se geocodificó — la misma clase de mentira que el chip, en otro lugar de la pantalla. ARREGLADO el 8/9, commit aparte: ver la sección "`<summary>` de la barra de filtros que miente" más abajo.

Estado: CERRADO. Auditado por Sesión 2 y pusheado el 8/9.

## `<summary>` de la barra de filtros que miente — CERRADO Y AUDITADO (8/9)

Segundo hallazgo de la tanda del chip de cercanía, que había quedado anotado en Backlog pendiente. En `app/blog/templates/blog/index.html` el `<summary>` de la barra de filtros armaba su texto con `{%- if cerca_de_actual %}` y agregaba "cerca de {dirección}" aunque MapTiler no hubiera resuelto la dirección — la misma mentira del chip, movida al resumen. Pesa más de lo que parece: en teléfono los filtros van adentro de un `<details>` que `main.js` cierra, así que ese resumen es lo único que se ve.

Fix de una línea: ese `{% if %}` pasa a mirar `cercania_aplicada`, la variable que ya existía desde el fix del chip justamente para no repetir la condición. No hubo que moverla — se define en la línea 54, arriba del bloque del `<summary>`; sigue definida una sola vez.

2 tests nuevos en `tests/test_blog.py`, sección cercanía: `test_una_direccion_que_no_geocodifica_no_entra_en_el_resumen` (el bug) y `test_con_la_direccion_geocodificada_el_resumen_si_la_nombra` (la contracara), los dos con el mismo `monkeypatch` sobre `get_coordinates_from_address` que usa el test del chip. Van contra el helper `_resumen_de_filtros()`, que recorta el `barra-filtros__resumen-detalle` en vez de buscar en el HTML entero: el chip también dice "cerca de", así que un `in html` pelado daría verde por el chip aunque el resumen mintiera.

Contraprueba hecha, no solo suite en verde: se revirtió el template dejando los tests puestos y el test del bug pasó a rojo; con el fix vuelve a verde.

Barrido del resto del archivo por si quedaba otro lugar armando texto o clases con `cerca_de_actual` pelado: no queda ninguno. El único uso sin `ordenado_por_distancia` es el `value=` del `<input name="near">` (línea 127), que es deliberado y ya tiene su test (`test_una_direccion_que_no_geocodifica_conserva_lo_que_se_tipeo`).

Estado: CERRADO. Auditado por Sesión 2 y pusheado el 8/9.

## `CAMPOS_DEL_PERFIL` — una sola lista de campos del perfil — CERRADO Y AUDITADO (8/9)

Item que estaba en Backlog pendiente. **El item estaba desactualizado**: nombraba `leer_perfil()`, función que ya no existe — se había partido en `leer_perfil_publico()` y `leer_contacto()` cuando Ajustes se separó en dos pantallas, y las dos ya leían de tuplas compartidas (`CAMPOS_PERFIL_PUBLICO`, `CAMPOS_CONTACTO`) a través de `_leidos()`. O sea que la mitad del trabajo ya estaba hecha y el doc no se había enterado.

Lo que sí seguía duplicado, y es la misma falla que describía el item: `campos_guardados()` (en `app/perfil/formulario.py`) repetía los ocho nombres a mano en un dict literal. Esos ocho son exactamente `CAMPOS_PERFIL_PUBLICO + CAMPOS_CONTACTO`, en ese mismo orden — verificado nombre por nombre, no de vista.

Fix: se agregó `CAMPOS_DEL_PERFIL = CAMPOS_PERFIL_PUBLICO + CAMPOS_CONTACTO` (derivada, no una tercera lista escrita a mano) y `campos_guardados()` pasó a ser un dict por comprensión sobre esa tupla. Va en `formulario.py`, donde ya viven las otras dos constantes y la función: no hace falta módulo neutral ni hay import circular que esquivar.

Lo que NO se unificó, a propósito: el **acceso** al valor. `_leidos()` lee del POST y hace `.strip()`; `campos_guardados()` lee de la base y hace `or ""` para cambiar el None de una columna vacía por el texto vacío que espera el `<input>`. Lo único repetido era la enumeración de nombres; los dos accesos son legítimamente distintos y siguen separados.

Equivalencia comprobada antes de tocar los tests: se corrió la implementación vieja y la nueva sobre el mismo objeto en cuatro casos (todo None, todo `""`, todo con valor, y mezcla con un `0`), comparando el dict entero **y el orden de las claves** — idénticos. El orden importa porque es el orden en que se pintan los `<input>` de Ajustes.

4 tests nuevos en `tests/test_profile.py`, sección "una sola lista de campos del perfil":

- `test_campos_guardados_sigue_a_la_tupla_y_no_a_una_lista_propia` — **el detector**: agrega un campo ficticio a la tupla con `monkeypatch` y exige que aparezca en el dict. Es el único de los cuatro que da rojo si alguien reintroduce la lista a mano.
- `test_la_tupla_del_perfil_es_la_union_de_las_dos_pantallas` — que `CAMPOS_DEL_PERFIL` siga siendo derivada y sin nombres repetidos.
- `test_campos_guardados_devuelve_exactamente_la_tupla_compartida` — las claves y su orden.
- `test_lo_que_leen_las_dos_pantallas_cubre_todos_los_campos_guardados` — el otro lado del mismo olvido: que entre las dos pantallas se lea del POST todo lo que se pinta, ni uno más ni uno menos.

Contraprueba hecha: se revirtió `campos_guardados()` a la lista a mano dejando los tests puestos y el detector pasó a rojo con `KeyError: 'campo_ficticio'`; los otros tres siguieron verdes, que es lo esperado — son guardas, no detectores. El archivo se restauró desde una copia aparte y no con `git checkout`, que en la tanda anterior se llevó puesto el fix junto con la reversión temporal.

Estado: CERRADO. Auditado por Sesión 2 y pusheado el 8/9.

## Navegación — primera de las ocho tandas de rediseño pasada a código (8/9) — CERRADA Y AUDITADA (10/9)

Arranque de "pasar uno por uno los rediseños a código". De las doce carpetas
`disenio-*`, cinco ya estaban en código (inicio, auth, perfil, ajustes y servicios,
commit `27d1710`) y ocho estaban dibujadas y sin tocar la app. Se empezó por
navegación porque es el cromo compartido: toca `base.html` y parciales, no cada
pantalla, y todo lo demás se ve adentro.

Qué entró, en corto (el detalle largo, con las cuentas de contraste y de
breakpoints, está en `disenio-inicio/DISENIO.md`, sección "Navegación pasada a
código"):

- **La barra pasa de una fila a dos bandas**: identidad + tres secciones centradas +
  acciones (68 px), y abajo el buscador solo (`q` + `near` + botón, 52 px). "Inicio"
  se fue de las secciones — el logo ya es el inicio.
- **Favoritos y Mensajes salen del menú** y pasan a ser iconos visibles.
  **"Publicar" sale de la barra** y pasa a ser el botón lleno arriba del menú de la
  cuenta, igual que en teléfono.
- **El menú de la cuenta queda en tres grupos rotulados** en vez de una lista de
  nueve, y suma "Mis turnos" y "Agenda de turnos", que existían como rutas desde la
  tanda de turnos y no estaban en ningún menú.
- **El badge deja de mentir.** `/mensajes/notificaciones` ya devolvía los tres
  números por separado; el que los sumaba era el JS. Ahora cada elemento pide el
  suyo con `data-notif="..."`. **No hizo falta tocar el backend.**
- **Se fue la hamburguesa.** En teléfono hay una barra de cinco pestañas abajo
  (tres sin sesión) y una pantalla nueva, `/perfil/mi-cuenta`, para la pestaña
  Perfil. Ya está en `SLUGS_RESERVADOS`.

Archivos: `templates/base.html`, `templates/partials/_icono_nav.html` (nuevo),
`_menu_cuenta_desplegable.html` (nuevo), `_tabbar.html` (nuevo),
`app/perfil/templates/profile/cuenta.html` (nuevo), `app/perfil/vistas.py`,
`services/slugs.py`, `static/css/styles.css`, `static/js/main.js`,
`tests/test_navegacion.py` (nuevo), `disenio-inicio/DISENIO.md`.

Ojo con `partials/_menu_cuenta.html`: **no se tocó**. Es la columna izquierda de las
diez pantallas de cuenta, otra cosa que el desplegable nuevo.

Tres decisiones que el canvas dejaba abiertas y se cerraron acá, con Tomy:

- **"Explorar" del teléfono** va al listado, y las tres secciones reaparecen como
  solapas arriba del contenido de esas tres pantallas. El artboard decía que
  "Explorar" agrupa las tres pero nunca dibujó la agrupación.
- **Un visitante ve tres pestañas** (Inicio · Explorar · Entrar), no cinco: los dos
  artboards de teléfono están con sesión y Favoritos/Mensajes sólo rebotarían al
  login.
- **La banda del buscador no se dibuja en el home ni en el listado**: las dos ya
  tienen la suya, más completa. Se vio en pantalla que quedaban dos buscadores
  apilados. Cuál sobrevive en el listado se decide en la tanda de Resultados.

Queda afuera a propósito: **la pastilla de zona del top bar del teléfono**. El propio
canvas anota que falta cablear que la zona se recuerde entre pantallas; sin esa
memoria la pastilla no tiene qué decir ni dónde guardar. La zona se dice en el campo
"dónde" del buscador, que sí manda un `near` real.

Un bug encontrado mirándolo en el navegador, no en la suite: los contadores nacen
con `hidden`, pero `hidden` pierde contra cualquier `display` de una clase propia, y
se veía un punto naranja vacío. Se agregó `[hidden] { display: none !important; }`
al reseteo de `styles.css`.

Verificado en pantalla con un servidor descartable (SQLite temporal, **no
impulsar_db**): barra con y sin sesión, menú desplegado, `/perfil/mi-cuenta`, y los
dos anchos de teléfono en iframe de 390 px — sin scroll lateral nuevo.

**Auditada el 10/9** con revisión COMPLETA, como correspondía por tocar el cromo
compartido de todas las pantallas. Verificado en Chrome a 390 y 768 px: las dos
bandas, las tres secciones (sin «Inicio»), los badges separados por `data-notif`
(`unread_messages`, `pending_service_requests`, `unanswered_reviews`, sin sumar),
el `[hidden]` respetado, cinco pestañas con sesión y tres sin ella. Sin hallazgos
propios.

## Ficha del emprendimiento — segunda tanda de rediseño pasada a código (9/9) — CERRADA Y AUDITADA (10/9)

Reescribe `app/blog/templates/blog/detail.html` entero (466 líneas) y suma tres
piezas chicas de backend. El detalle largo está en `disenio-inicio/DISENIO.md`,
sección "Ficha del emprendimiento pasada a código".

Los siete problemas que el canvas había anotado, y qué pasó con cada uno:

- Las reseñas decían **"Usuario #7"** → firman con el nombre. `resenias_de()`
  ahora trae al autor con `joinedload`; hay un test que mide que sigan siendo
  **una sola consulta** con el identity map vaciado.
- Las estrellas eran los glifos **★ y ☆** y había un **📍** por servicio → SVG.
- **Las ferias no aparecían nunca** aunque `Post.eventos` existe desde la tanda
  de eventos → bloque "Dónde encontrarla". `ferias_de()` reusa
  `services.eventos.proximos()` en vez de repetir el `order_by`, que se comía el
  desempate por id.
- **"Abierto ahora" no decía a qué hora cierra** → `hora_de_cierre()` nuevo en
  `services/horarios.py`, y `esta_abierto()` pasó a apoyarse en él (son la misma
  pregunta; ninguna respuesta cambia, los 39 tests de horarios pasan intactos).
- **Las miniaturas abrían el archivo suelto** de `/static/uploads/` en otra
  pestaña → visor propio (`static/js/visor.js`), con teclado y devolución de foco.
- **No había ningún estado vacío pensado** → barra de dueña, "Completá tu ficha"
  de cinco tareas contra campos que existen, y cada hueco explicando por qué
  conviene llenarlo.
- **La distancia sigue sin mostrarse**: necesita saber dónde está parado quien
  mira, que es la misma memoria de zona que dejó pendiente la tanda de
  navegación. Sin ese dato sería inventarla.

Decisiones de forma: **anclas, no pestañas** (con solapas, tres de las cuatro
abrirían vacías en la mayoría de los emprendimientos), y los **nueve bloques como
lista plana** con `display: contents` + `order`, porque el teléfono los quiere en
otro orden que el escritorio (horarios y ferias ANTES de las reseñas).

Archivos: `app/blog/templates/blog/detail.html`, `app/blog/consultas.py`,
`app/blog/vistas.py`, `services/horarios.py`, `services/formatting.py`,
`main.py` (filtro `hace`), `templates/partials/_estrellas.html` (nuevo),
`templates/partials/_icono_nav.html`, `static/js/visor.js` (nuevo),
`static/css/styles.css`, `tests/test_ficha.py` (nuevo, 22 tests),
`tests/test_blog.py` (un texto que cambió), `disenio-inicio/DISENIO.md`.

Barrido de CSS muerto: al reescribir la ficha quedaron sin dueño 20 reglas
(`.detalle__principal`, `.lateral__accion`, `.galeria-grid*`, `.post-detail-card`,
`.back-link`, `.ficha__rating`/`__estrella`…). Se borraron cruzando cada clase
contra todos los templates y JS como token entero, no como substring. Las dos
reglas del formulario de reseña se reapuntaron a `.resenia-propia`, que es su
envoltorio nuevo.

Un desborde lateral encontrado midiendo, no leyendo: en 390 px el `scrollWidth`
daba 434 por el `white-space: nowrap` de "Entrá para pedir presupuesto". Corregido
y vuelto a medir: 371.

**Auditada el 10/9.** Un hallazgo real, de CSS compartido: su `.resenias` le
pisaba la grilla de dos columnas de «Reseñas recibidas». Arreglado renombrando el
wrapper de la ficha a `.resenias-ficha` (ver «Auditoría de cierre», abajo).

## Catálogo de productos — tercera tanda de rediseño pasada a código (9/9) — CERRADA Y AUDITADA (10/9)

La única de las ocho que necesitaba **rutas nuevas**. El detalle largo está en
`disenio-inicio/DISENIO.md`, sección "Catálogo de productos pasado a código".

**Las URL se dieron vuelta.** `/productos/` era el panel privado del dueño y un
producto sólo se veía incrustado en la ficha de su emprendimiento. Ahora:

| Ruta | Endpoint | Quién |
| --- | --- | --- |
| `/productos/` | `products.catalogo` | público |
| `/productos/<id>` | `products.detalle` | público |
| `/productos/<id>/favorito` (POST) | `products.toggle_favorito` | con sesión |
| `/productos/guardados` | `products.guardados` | con sesión |
| `/productos/mios` | `products.mios` (era `products.index`) | el dueño |

**Seis filtros, todos como parámetros de la URL** (se comparte, vuelve con atrás,
anda sin JS): texto sobre `Product.nombre`/`descripcion`, rubro sobre
`Post.category`, precio desde/hasta con el mismo `parsear_precio` del formulario
de carga, disponibles (**encendido por defecto**, se apaga con `?disponibles=0`),
abierto ahora y radio en km. **Cuatro órdenes**: más nuevos, precio ↑, precio ↓ y
cercanía — esta última sólo si hay coordenadas, y ahí pasa a ser el default.

`_distancia_km` y `_abierto_ahora_sql` de `app/blog/consultas.py` **pasaron a ser
públicas** (`distancia_km_sql`, `abierto_ahora_sql`) en vez de copiarse: la copia
se habría olvidado del `CASE` que acota el `ACOS`. El "N productos de M
emprendimientos" es un `COUNT(DISTINCT post_id)` que pasa por el mismo
`_filtrar_catalogo` que la grilla, para que no pueda mentir.

**Tabla nueva: `product_favorites`** (migración `a4c17b8e6d20`). El corazón de las
tarjetas necesitaba dónde guardar y `Favorite` es de emprendimientos. Las dos FK
con `ondelete CASCADE` y nombre explícito, más el `UNIQUE (user_id, product_id)`
que es lo que corta el doble click. Ciclo upgrade → downgrade → upgrade verificado
en SQLite y en una base MySQL descartable, y ahí mismo las dos cascadas y el
UNIQUE con filas reales. **"Mis favoritos" pasó a tener dos solapas**
(Emprendimientos / Productos) en un parcial compartido.

**El chat ya sabe de qué se habla**: `?producto=<id>` en `messages.conversation`
precarga "Hola, quería consultar por «…»". Se exige que el producto sea de ese
emprendimiento — sin el chequeo, un id cualquiera en la URL pondría palabras en
boca del que pregunta.

Productos **no entra en la barra global** (cuatro secciones se montan sobre el
bloque de acciones). Tres puertas: el pie, una ficha en los filtros del listado
que se lleva el texto buscado, y cada producto de la ficha, que dejó de ser un
cartel y pasó a ser un enlace.

Lo que quedó afuera a propósito: la **hoja de filtros que sube desde abajo** en
teléfono (en código es el mismo `<details>` del listado: mismos filtros, misma
URL, sin JS nuevo) y **la distancia en el detalle** (misma memoria de zona que
sigue pendiente desde navegación).

Un desborde lateral encontrado midiendo: en 390 px el `scrollWidth` daba 437 por
el `flex-wrap: nowrap` que el listado le pone a las fichas de filtro. En el
catálogo son seis, con un "Ordenar por" largo, así que **envuelven en vez de
deslizarse** (`.fichas-filtro--catalogo`). Medido de nuevo: 371, y 749 en 768 px.

Archivos: `views/products.py`, `views/messages.py`, `models/product_favorite.py`
(nuevo), `migrations/versions/a4c17b8e6d20_*.py` (nuevo), `app/blog/consultas.py`,
`config.py` (`PRODUCTOS_POR_PAGINA`), `templates/products/catalogo.html` +
`detalle.html` + `guardados.html` (nuevos), `templates/products/index.html` →
`mios.html`, `templates/partials/_solapas_favoritos.html` (nuevo),
`templates/base.html`, `templates/partials/_tabbar.html`,
`templates/messages/conversation.html`, `app/blog/templates/blog/index.html` +
`detail.html` + `favorites.html`, `static/css/styles.css`,
`tests/test_catalogo.py` (nuevo, 40 tests), `tests/test_products.py` y
`tests/test_navegacion.py` (la URL del panel), `disenio-inicio/DISENIO.md`.

De paso salió un botón muerto: **«Cerca de mí» no andaba en ninguna pantalla**.
El JS hacía `boton.closest("form").submit()` y ese botón vive afuera del `<form>`
desde el rediseño de la barra de filtros, así que `closest` daba `null` y el
click moría con un `TypeError`. Ahora manda `latInput.form.submit()`, que es el
form con las coordenadas recién escritas. **Arregla también `/blog/`.**

**Auditada el 10/9**, incluida su migración `a4c17b8e6d20` (reverificada en
SQLite y en MySQL 8 descartables). Sin hallazgos propios.

## Sobre, contacto y errores — cuarta tanda de rediseño pasada a código (9/9) — CERRADA Y AUDITADA (10/9)

La más chica: seis pantallas, **ninguna ruta nueva y ninguna migración**. El
detalle largo está en `disenio-inicio/DISENIO.md`, sección «Sobre, contacto y
errores pasados a código». Tres de las seis tenían un problema que no era de
estética:

- **`about.html` hablaba del equipo de desarrollo**, no del visitante: decía
  «Flask (Python) y MySQL… una estética moderna en tonos pastel» (lo de pastel
  hace rato que es falso). Reescrita desde el posicionamiento de la guía: los
  cinco datos que Mercado Libre no tiene, **y los cinco salen de una tabla que
  existe**. Se suma **«Lo que IMPULSAR no hace»** —sin pagos, sin envíos, sin
  protección al comprador— porque es el argumento, no una disculpa. **Ni un
  número en la página**, y hay un test que lo vigila.
- **`contact.html` tenía un emoji** (📧) delante del mail. Se fue. **Sigue sin
  formulario** a propósito: no hay tabla de consultas ni envío de mail, y un form
  que no manda nada es peor que un `mailto` honesto. Se suman los **cuatro
  atajos** que ya existen (reportar, chat, publicar, Ajustes); los dos que piden
  sesión llevan a entrar cuando no la hay.
- **Privacidad y Términos hacían las listas con `<br>•` adentro de un `<p>`**:
  para un lector de pantalla es un párrafo con puntos medios. Ahora son `<ul>`.
  **El texto no se tocó, palabra por palabra.** Las dos comparten un molde nuevo
  (`templates/legal_base.html`) con índice sticky, enlace cruzado a la otra
  legal, y medida de lectura de 66ch.

**El 404 dejó de ser un cartel**: buscador en la pantalla (manda al listado) y
los siete rubros abajo, con el mismo `.punto-rubro` del catálogo. **El 500 es el
mismo molde sin buscador ni rubros** — si el servidor se cayó, un buscador que
tampoco anda es una segunda frustración; sus botones son reintentar (a
`request.url`) y Contacto.

**La fecha de las legales sigue faltando y ahora tiene lugar**:
`ACTUALIZADA_PRIVACIDAD` y `ACTUALIZADA_TERMINOS` en `views/pages.py`, hoy en
`None`. Mientras lo estén, la pastilla de «Última actualización» no se dibuja: un
`[COMPLETAR]` a la vista del usuario sería peor que no decir nada. **Es un dato
de Tomás.**

Barrido de CSS muerto: diez reglas sin dueño (`.about*`, `.contact*`,
`.legal__text`, `.legal__subtitle` y el bloque entero de `.error-page`).
`.legal` sobrevive con otro significado: era una columna de 720 px y ahora es la
grilla de índice + cuerpo.

Medido en las seis pantallas a 390 y a 768 px: sin scroll lateral.

Archivos: `templates/about.html`, `contact.html`, `privacy.html`, `terms.html`,
`legal_base.html` (nuevo), `errors/404.html`, `errors/500.html`,
`views/pages.py`, `main.py` (el 404 recibe los rubros),
`static/css/styles.css`, `tests/test_paginas.py` (nuevo, 21 tests),
`tests/test_app.py` (el texto del 404), `disenio-inicio/DISENIO.md`.

## Panel de administración — quinta tanda de rediseño pasada a código (9/9) — CERRADA Y AUDITADA (10/9)

Ninguna ruta nueva, ninguna migración. De las cinco plantillas, tres ya tenían el
rediseño de agosto; lo que faltaba era lo que se había quedado afuera. El detalle
largo está en `disenio-inicio/DISENIO.md`, sección «Panel de administración
pasado a código».

**Reportes y Verificaciones no eran pintura pendiente: no existían con la forma
del resto.** Tabla pelada, estilos inline y **sin el menú del panel, aunque el
menú les enlazaba** — entrabas y perdías la navegación. Ahora son una **ficha por
ítem**: la cita del reporte entera (antes cortada por un `max-width: 280px`), el
documento de la verificación en su propia caja, y las acciones abajo.

- **El motivo sigue viajando en el mismo envío que el rechazo** (un solo
  `<form>`): si fuera otra pantalla, el prestador se quedaría sin saber qué
  corregir. Lo decidió el código y se respeta.
- **Sin foto es un estado, no un hueco**: caja punteada, **aprobar deshabilitado**
  y el motivo del rechazo ya escrito. El `disabled` es la pantalla diciendo lo
  obvio, no un permiso — ése vive en `@admin_required`.

**El Resumen y la cola dibujaban el mismo ítem dos veces.** Pasaron a dos
parciales compartidos (`admin/_ficha_reporte.html` y `_ficha_verificacion.html`),
con una sola bandera de diferencia (`compacta`: en el Resumen el documento es un
enlace, en la cola una caja). Eso dejó sin dueño `.admin-item*` y `.admin-aviso`,
que se borraron.

**Un solo número grande por pantalla**: el Resumen lidera con lo pendiente a
60 px y las métricas quedan a 30. Antes era un `<h1>` de texto — la misma
información sin jerarquía. Con las dos colas vacías el número no se dibuja.

**El estado nunca se dice sólo con color**: cada pastilla lleva ícono y palabra y
la fila entera se tiñe. Hay un test que abre cada pastilla y exige un `<svg>`
adentro. De paso, la columna «Rol» mostraba el valor crudo de la base
(«emprendedor») al lado de un filtro que dice «Emprendedores»: las etiquetas
viven ahora en `Roles.ETIQUETAS`. Y `tabular-nums` en columnas con una clase
`.num` — nunca en los números grandes, que a 60 px quedan flojos.

**`.btn--peligro`**: blanca en reposo, roja al acercarse. No es roja desde el
principio porque veinte botones rojos en una tabla convierten el rojo en el color
de fondo del panel.

**En el teléfono el panel se recorta a la cola**: el menú lateral se apaga y
quedan el contador de pendientes y un segmentado de dos. Las acciones van
apiladas y a lo ancho de 44 px, para que «Eliminar» no caiga al lado del pulgar
que iba a «Marcar resuelto». Medido: 371 de `scrollWidth` en las cinco
pantallas, a 390 y a 768.

Quedó afuera, porque no hay con qué: «Emprendimientos sin actividad» (`Post` no
tiene `updated_at`), «Exportar métricas» y «Exportar CSV».

Archivos: `templates/admin/reportes.html`, `verificaciones.html`,
`dashboard.html`, `usuarios.html`, `emprendimientos.html`, `_menu_admin.html`,
`_ficha_reporte.html` y `_ficha_verificacion.html` (nuevos), `views/admin.py`,
`models/user.py` (`Roles.ETIQUETAS`), `templates/partials/_icono_nav.html`
(cinco íconos nuevos), `static/css/styles.css`, `tests/test_admin.py` (18 tests
nuevos), `disenio-inicio/DISENIO.md`.

## Panel del vendedor — sexta tanda de rediseño pasada a código (9/9) — CERRADA Y AUDITADA (10/9)

**Una ruta nueva (`/panel`), un POST nuevo (`/productos/<id>/disponible`),
ninguna migración.** Las seis pantallas del dueño eran seis páginas sueltas:
cuatro compartían `_menu_cuenta.html`, la agenda de turnos no tenía menú
ninguno. Ahora las siete (con la portada nueva) comparten
`partials/_menu_panel.html`, y `_menu_cuenta.html` queda en las de «Mi
actividad» y ajustes — el mismo corte que ya hacía el menú del avatar.

**El panel arranca por lo pendiente, no por los números.** Presupuestos sin
responder, mensajes sin leer, turnos de hoy y reseñas sin contestar, y **solo se
dibuja lo que tiene algo**: con las cuatro en cero la sección entera no aparece.
Los tres primeros conteos vivían escritos a mano adentro de
`/mensajes/notificaciones`; se mudaron a `app/panel/consultas.py` y esa vista
los pide de ahí, así que el criterio de «esto espera respuesta tuya» está en un
solo lugar.

**Los números son los cinco que la base sabe contar** (los de
`estadisticas_de_usuario`). Sin flechitas de variación ni gráficos: la consulta
da el total de hoy y no hay histórico, así que un «+18%» sería inventado.

**El aviso de cada emprendimiento es uno solo**, el primero que aplique (sin
fotos → sin productos ni servicios → sin horarios). El de horarios va último
porque cuelga del USUARIO y no del emprendimiento: con dos emprendimientos
aparece en los dos.

**El catálogo del dueño** (`/productos/mios`, la última pantalla vieja que dejó
la tanda del catálogo) pasa a filas agrupadas por emprendimiento, y **los grupos
se arman desde los emprendimientos y no desde los productos**: el que no cargó
ninguno también aparece, con «Cargar el primero» al lado.

**El interruptor de «sin stock» es el único backend nuevo**: un POST chico,
calcado de `/servicios/<id>/disponible`. Form de un botón y no checkbox con JS,
`aria-pressed` y no `role="switch"`, y el estado dicho además con la palabra al
lado — la opacidad es refuerzo, no el mensaje.

**En el teléfono el panel no lleva menú lateral** (`.panel-menu` se apaga a
879px): ocho ítems arriba de todo dejan el contenido debajo del pliegue. El menú
de esas pantallas es `/perfil/mi-cuenta`, donde se agregó «Mi panel» como
primera ficha; en escritorio, arriba de «Mis emprendimientos» en el menú del
avatar.

Quedó afuera: **«Eventos y ferias» del menú** (no hay pantalla de los eventos
propios — se cargan desde la ficha, y `/eventos` es la cartelera pública; entra
con la tanda de eventos) y el **buscador, filtro, orden y paginado del catálogo
propio** que el artboard dibuja adentro de cada grupo (con el tope de 50 las
filas entran todas: serían cuatro controles con backend propio para filtrar una
lista que ya se ve entera).

Archivos: `app/panel/` (nuevo), `templates/partials/_menu_panel.html` (nuevo),
`templates/products/mios.html`, `_icono_nav.html` (íconos `editar` y
`eliminar`), `_menu_cuenta_desplegable.html`, `profile/cuenta.html`,
`turnos/agenda.html`, `blog/my_posts.html`, `servicios/index.html` y
`solicitudes.html`, `profile/reviews.html`, `views/products.py`,
`views/messages.py`, `app/blog/vistas.py`, `app/servicios/vistas.py`,
`app/turnos/vistas.py`, `app/perfil/vistas.py`, `main.py`,
`static/css/styles.css`, `tests/test_panel.py` (18 tests nuevos),
`tests/test_profile.py`, `disenio-inicio/DISENIO.md`.

## Turnos — séptima tanda de rediseño pasada a código (9/9) — CERRADA Y AUDITADA (10/9)

**Ninguna ruta nueva, ninguna migración, y el único backend nuevo son cuatro
consultas de lectura.** Las tres pantallas (`reservar`, `mios`, `agenda`) se
reescribieron enteras y `turnos/_lista.html` — el macro que compartían mis
turnos y la agenda — se borró: eran dos pantallas distintas usando la misma
fila, y eso era justamente el problema.

**Reservar deja de ser un `<input type="date">` a ciegas.** Antes había que
adivinar qué día tenía lugar, y abajo cada horario era un `<button
type="submit">` adentro de su propio `<form>`: **un click de más ya reservaba**,
y cancelado no se revierte. Ahora:

- una **tira de siete días** que dice de antemano cuántos horarios le quedan a
  cada uno (`consultas.semana_de_slots`, dos consultas para la semana entera:
  los horarios de la persona y las horas tomadas del rango);
- **los ocupados se dibujan apagados** en vez de desaparecer. Una grilla con
  cuatro horas sueltas y sin explicación se lee como que el negocio casi no
  atiende. Los horarios son `<input type="radio">` de UN formulario y el submit
  es uno solo, al final;
- **los seis vacíos de `slots_disponibles()` son cinco mensajes distintos**
  (`SIN_TURNOS`, `CERRADO`, `SIN_HORARIO`, `COMPLETO`, `PASO`). El quinto salió
  de la verificación visual: el día de hoy, ya empezado y sin ninguna reserva,
  decía «los turnos de ese día ya están tomados», que es mentira. `PASO` y
  `COMPLETO` no son lo mismo y no se dicen igual.

**Los días son enlaces GET, no botones.** Elegir un día no reserva nada, así que
la URL de un día queda compartible y el botón de atrás funciona. Viajan dos
parámetros y no uno (`?desde=` la tira, `?fecha=` el día elegido): con uno solo,
cada click en un día recentraría la tira y los otros seis se moverían debajo del
dedo.

**Mis turnos se parte en próximos y pasados.** `turnos_de_cliente()` ordena por
fecha DESC y mezclaba todo: lo primero que se veía era el turno más viejo del
historial. El corte va en la vista y no en la consulta porque necesita saber qué
día es hoy en Argentina, que es un dato del request. Y es por FECHA, no por
hora: el turno de hoy a las 09:00 sigue en «Próximos» a las 11:00.

**Cancelar pide confirmación, y en la misma fila**, con las dos consecuencias
reales escritas (se libera el horario, sale un mail). Es un `<details>`, no
JavaScript. **Se fue el botón «Turnos que recibí»**: la agenda vive en el panel
desde la tanda anterior.

**La agenda es un día, no una lista de tarjetas**, y **los huecos se dibujan**:
son lo que todavía se puede reservar, o sea la mitad de la información de una
agenda. `reglas.huecos_entre` los calcula sobre el rango de atención y NO los
corta en tramos, porque cada servicio tiene su duración y todos salen del mismo
horario de la persona: un hueco de 13:45 a 16:00 puede recibir un turno de 45
minutos o uno de 90. Los cancelados del día van abajo y aparte — su horario ya
volvió a los huecos de arriba, pero el vendedor tiene que verlos. **No hay
«cumplido» ni «ausente»**: esos estados no existen y dibujarlos sería inventar
una columna.

**Sin JavaScript las tres pantallas funcionan.** Lo único que agrega `main.js`
es que el resumen del costado de reservar siga al horario elegido; el radio se
marca, el botón envía y la vista rechaza con «Elegí un horario de la lista» si
no se eligió ninguno.

Quedó afuera, y no es descuido: **«Cómo llegar»** (no hay más que
`address_street`, y armar un link a un mapa externo es una decisión de producto
que nadie tomó), **«Dejar una reseña» en el historial** (habría que saber si ya
la dejó, y eso es otra consulta y otra tanda), y **el filtro por emprendimiento
de la agenda** que dibuja el artboard (los chips «Los dos emprendimientos» /
uno / otro): entra cuando haya alguien con dos emprendimientos y servicios en
los dos, hoy sería un filtro de un solo valor.

Verificado con el servidor descartable en 5050 (SQLite temporal, nunca
`impulsar_db`): las tres pantallas con sesión, el día lleno, el día cerrado, el
día ya pasado y el día con huecos intercalados entre dos turnos. **El repaso a
390 px quedó sin hacer**: la extensión de Chrome no está conectada en esta
máquina. Las media queries están escritas (siete columnas siempre, nada se
desliza de costado, la hora de la fila pasa a renglón propio) pero no se
miraron con un navegador — va a la auditoría.

**Auditada el 10/9.** El repaso a 390 px que había quedado sin hacer está hecho:
sin desborde lateral en las tres pantallas, a 390 y a 768 px. Sin hallazgos
propios.

Archivos: `app/turnos/vistas.py`, `consultas.py`, `reglas.py`,
`templates/turnos/reservar.html`, `mios.html` y `agenda.html` (los tres
reescritos), `_lista.html` (borrado), `main.py` (filtro `hora`),
`static/css/styles.css` (sección «TURNOS»), `static/js/main.js`,
`tests/test_turnos.py` (35 tests nuevos, 4 adaptados),
`disenio-inicio/DISENIO.md`.

## Ferias y eventos — octava y última tanda de rediseño pasada a código (9/9) — CERRADA Y AUDITADA (10/9)

**La única tanda del rediseño con migración: `c7d92f4a1b83`**, dos columnas en
`events`. El resto de las ocho no tocó el modelo.

**Se decidió con Tomás cuáles de los tres campos dibujados entraban.** El canvas
pedía tres que la base no tenía; entran dos y queda uno:

- **`tipo`** — Feria · Taller · Pop-up · Encuentro (`TiposEvento`). **NULLABLE y
  sin `server_default`**, igual que `lugar` en `f3c81a25b7d0`: los eventos ya
  cargados no tienen tipo y no hay de dónde sacarlo. Ponerles «feria» a todos
  etiquetaría de mentira lo que quizá era un taller. NULL es «no lo dijo»: la
  tarjeta no dibuja el chip y ningún filtro por tipo lo cuenta. El formulario sí
  lo exige para los nuevos, así que el NULL se agota solo. **No hay «Otros»**, al
  revés que `Categorias`: ofrecer el cajón de sastre desde el día uno garantiza
  que la mitad caiga ahí y que el filtro deje de servir.
- **`entrada_libre`** — `Boolean`, NOT NULL, `server_default "0"`. **La asimetría
  con `tipo` es deliberada**: el chip solo se dibuja en True, así que False no
  afirma nada, mientras que marcarle entrada libre a un taller pago prometería
  gratis lo que se cobra.
- **«Me interesa» NO entró**, y lo dice el propio canvas: no es una etiqueta, es
  una feature entera (tabla usuario × evento, ruta, permiso, y decidir si el
  dueño ve quiénes son). Sigue en backlog, no maquetada en falso.

Índice sobre `tipo` porque la cartelera filtra por ahí; sobre `entrada_libre` no,
que a un booleano de dos valores ningún plan de consulta le saca provecho.

**El calendario pasa de ilustración a filtro.** Pintaba los días con eventos
contra `/api/eventos?mes=` y ahí terminaba: los puntitos no hacían nada. Ahora
cada día es un **enlace a `?dia=AAAA-MM-DD`**, así la cartelera filtrada se
comparte, vuelve con el botón de atrás y el filtro anda sin JS (el calendario en
sí sigue siendo JS: sin él no hay calendario, igual que antes). El parcial tiene
dos modos, con `data-enlace-dia`: en el home el día sigue siendo un botón que
filtra el panel de al lado sin recargar, que ahí es lo correcto. Con un día
elegido el calendario **abre en SU mes** y no en el actual.

**El día manda sobre «todavía no pasó».** Elegir una fecha muestra ese día
aunque ya haya pasado: el calendario navega meses para atrás, y esconder lo
vencido dejaría esos meses vacíos. Sin día elegido, la cartelera es lo que viene.

**Dos vacíos distintos, no uno.** «Todavía no hay eventos anunciados» es cierto
con la base vacía y mentira cuando el día elegido no tiene nada; el segundo dice
cómo salir del filtro y trae el botón para hacerlo.

**Una pantalla nueva: `/eventos/mios`**, que es la que le faltaba al ítem
«Eventos y ferias» del menú del panel — por eso quedó afuera de la tanda del
panel del vendedor. Hasta ahora un evento se cargaba y se editaba desde la ficha
de cada emprendimiento, y `/eventos` es la cartelera pública de todos: quien
tiene tres emprendimientos no tenía ningún lado donde ver sus fechas juntas.
Próximos y pasados, como «mis turnos»; los pasados no se borran solos (la
cartelera pública sí los esconde). Borrar pide confirmación con el mismo
`<details>` de la tanda de turnos. Las tres vueltas del ABM (alta, edición,
borrado) ahora van ahí y no al perfil.

**Un solo llamado a publicar en la cartelera.** Había un botón al lado del
título además del bloque del costado: con el «Publicar» de la barra, la misma
acción aparecía tres veces en una pantalla. Queda el del costado, que es el
único que además dice por qué (es gratis y no hay comisión), y pasa a ser el
bloque índigo profundo del canvas.

**Los cuatro tipos se distinguen por el ÍCONO, no por el color** — los cuatro en
índigo lavado, igual que los 13 rubros de servicio. Con cuatro colores más, el
chip de tipo competiría con el verde de «entrada libre», que sí tiene que saltar
porque cambia la decisión de ir. El tipo en el formulario es un segmentado de
cuatro radios y no un `<select>`: desplegar una lista para elegir entre cuatro
opciones fijas es un paso de más.

**La migración se verificó aislada**, no solo bajando desde head: se cargaron
dos eventos con el esquema anterior, se aplicó el paso solo, y se comparó fila
por fila antes y después (en SQLite `batch_alter_table` RECREA la tabla, o sea
que copia). Ida y vuelta, con `foreign_key_check` limpio. Nota de método: hay
que correrla con `FLASK_ENV=development`, no `testing` — `TestingConfig` fija
`sqlite:///:memory:` a mano, así que con `testing` Alembic imprime que aplicó
todo sobre una base que se evapora y el archivo queda vacío, en silencio.

Verificado con el servidor descartable en 5050: la cartelera entera, filtrada
por tipo, el vacío del filtro, «mis eventos» y el formulario. **El repaso a
390 px quedó sin hacer**, igual que en turnos: la extensión de Chrome no está
conectada en esta máquina. Las media queries están escritas (los chips
envuelven, el segmentado pasa a dos columnas, las acciones ocupan el ancho) pero
no se miraron con un navegador — va a la auditoría.

Quedó afuera además: el artboard de teléfono mete los filtros en una hoja detrás
de un botón «Tipo y entrada»; acá envuelven en dos filas, que hace lo mismo sin
agregar una capa que hay que abrir para ver qué hay.

**Auditada el 10/9**, y su migración `c7d92f4a1b83` reproducida de cero por la
auditoría en bases descartables de SQLite y de MySQL 8 (ver «Auditoría de
cierre»). Un hallazgo real: el vacío «Todavía no hay eventos anunciados» también
salía con la base NO vacía y todo vencido. Arreglado con un tercer vacío. El
repaso a 390 px, que había quedado sin hacer, está hecho.

Archivos: `models/event.py` (`TiposEvento`, dos columnas, `tipo_label`),
`migrations/versions/c7d92f4a1b83_...py` (nueva), `views/eventos.py`,
`services/eventos.py` (`tipo_valido`, `del_dia`, `filtrar`),
`app/panel/consultas.py` (contador de eventos),
`templates/eventos/index.html` y `form.html`, `templates/eventos/mios.html`
(nueva), `templates/partials/_menu_panel.html` (el octavo ítem),
`_calendario.html` (modo enlace), `_icono_nav.html` (cinco íconos nuevos),
`static/js/calendario.js`, `static/css/styles.css` (sección «FERIAS Y EVENTOS»),
`tests/test_eventos.py` (35 tests nuevos, 10 adaptados), `tests/test_panel.py`,
`disenio-inicio/DISENIO.md`.

## Auditoría de cierre del rediseño (las ocho tandas juntas) — HECHA 10/9, APROBADA

Auditoría COMPLETA de punta a punta sobre las ocho tandas juntas, la que pedía el
plan de abajo, hecha antes del push y antes de abrir el PR. **Tres hallazgos
reales, los tres arreglados en la misma vuelta** (coordinados con la otra sesión,
que verificó los renames por su cuenta).

### La migración `c7d92f4a1b83`, reproducida de cero por la auditoría

No se confió en el resultado reportado: se rehízo la verificación entera en bases
descartables propias, **en SQLite y también en MySQL 8 real** (base
`auditoria_cierre_tmp`, creada y dropeada por el script, con `impulsar_db`
comprobada intacta al final). Vale la pena hacer las dos porque esta migración se
comporta distinto en cada motor: en SQLite `batch_alter_table` RECREA la tabla y
copia las filas, en MySQL sale un `ALTER` normal — probar sólo en SQLite deja sin
probar el camino que corre en producción.

Verificado, todo verde:

- Dos eventos cargados con el esquema anterior (`a4c17b8e6d20`), el paso aplicado
  aislado, y comparación **fila por fila por nombre de columna** (no por
  posición: el batch reordena). Intactas las 8 columnas viejas, y el conteo de
  filas de las 17 tablas idéntico.
- **`tipo` es nullable de verdad**: `IS_NULLABLE=YES`, sin default, `VARCHAR(20)`,
  y un `INSERT` sin tipo entra. Los eventos preexistentes quedaron en `(NULL, 0)`.
- `entrada_libre` NOT NULL con default `0`, y MySQL **rechaza** un NULL explícito.
- `ix_events_tipo` existe y va sobre `tipo`; **no** hay índice sobre
  `entrada_libre`, como se había decidido.
- La FK `post_id → posts` sobrevive idéntica con su `ON DELETE CASCADE`.
- **`downgrade` desde head y vuelta a `upgrade`** (no sólo el upgrade): sin perder
  ninguna fila ni ningún dato de las columnas viejas, el índice se va y vuelve, la
  FK queda igual. Se probó también con `tipo` y `entrada_libre` YA cargados: lo
  que se pierde en el downgrade es sólo el contenido de las dos columnas
  dropeadas, que es lo esperado.
- `foreign_key_check` limpio en SQLite (verificado por la auditoría, no reportado)
  y `PRAGMA foreign_keys` en ON en todo momento. Sin `_alembic_tmp_*` colgada.
- **Sin drift contra el ORM**: `compare_metadata()` no encuentra ninguna
  diferencia entre el esquema migrado y los modelos.
- La cadena entera `base → head` (34 pasos) y `head → base` corren limpias en
  SQLite.

### Hallazgo 1 — el vacío de la cartelera mentía con todo vencido (ARREGLADO)

`/eventos/` tenía dos vacíos y le faltaba uno. Sin ningún filtro puesto y con la
base **no** vacía pero **todos los eventos ya vencidos**, `proximos()` volvía
vacío, `filtrando` era `False` y la pantalla decía «Todavía no hay eventos
anunciados» — mentira, hubo eventos y ya pasaron. Peor: el calendario del costado
les sigue pintando el puntito, así que **la pantalla se contradecía sola**. Y no
es un caso raro: los eventos pasados no se borran nunca (la cartelera pública sólo
los esconde), así que es el estado normal de una cartelera en temporada baja.

Arreglado con un tercer vacío: `views/eventos.py` pasa `hay_eventos` (un `EXISTS`
que **sólo se consulta con la página vacía y sin filtros**, para no agregarle una
consulta a cada carga) y la plantilla ramifica en tres. Con todo vencido dice «No
hay fechas próximas» y manda a navegar el calendario para atrás, que es donde esos
eventos están. Dos tests nuevos en `tests/test_eventos.py`.

### Hallazgo 2 — `.interruptor`: el interruptor de horarios quedó gris en los dos estados (ARREGLADO)

El primero de dos choques de nombres en el `styles.css` compartido, y el más
grave porque **rompía una pantalla ya pusheada**. El interruptor de «sin stock»
del panel del vendedor tomó las mismas clases que el de los horarios de Cuenta
(`.interruptor`, `__pista`, `__texto`) y, al ir después en el archivo, le pisaba
cuatro propiedades. Medido en Chrome, no leído:

- la pastilla pasaba de 44×26 a **38×22** (abajo del piso de 44 px que fijó la
  auditoría del 6/9), y la bolita del bloque viejo es un `::after` de 20 px en
  `left: 21px` = 41 px, o sea **se desbordaba** de una pista de 38;
- el fondo pasaba de `--color-primary-boton` a `--color-border`, que es **justo el
  valor que el bloque viejo le pone al estado `:checked`**: los dos estados
  quedaban del mismo gris `rgb(226,230,238)` y **el color dejaba de decir si el
  día estaba abierto o cerrado**;
- el texto perdía el verde de `--color-success-text` y quedaba gris en los dos
  estados.

Arreglado renombrando **lo nuevo** (`.interruptor-stock*` en el bloque, en la
media query de 768 px y en los cuatro usos de `templates/products/mios.html`), no
lo viejo: lo viejo ya está pusheado y mirado. Verificado después: horarios vuelve
a 44×26 con índigo/verde en abierto y gris/muted en cerrado, y el de stock
conserva su propio dibujo.

**No** era cierto que horarios perdiera además su alineación a la derecha: el
`margin-left: auto` vive sólo en el bloque viejo y el nuevo no declara ninguno, así
que nunca hubo choque ahí (medido: resolvía a 216 px). Se verificó también el
riesgo simétrico —que `products/mios.html` perdiera algo que venía heredando sin
chocar— y no aplica: el flex item de la fila es el `<form>`, no el botón.

### Hallazgo 3 — `.resenias`: dos listas distintas con el mismo nombre (ARREGLADO)

La lista plana de reseñas de la ficha tomó el nombre de la grilla de dos columnas
de «Reseñas recibidas». Hacía daño **en las dos direcciones**:

- el `display: flex` de la ficha le ganaba al `display: grid` de la otra, y el
  `<aside class="resenias__resumen">` se apilaba abajo a todo el ancho en vez de
  ir en su columna de 300 px (medido a 1440 px, donde el grid sí tiene que
  aplicar: a 768 apilan las dos por la media query de 1100 y el bug no se ve);
- y la ficha heredaba de la grilla un `align-items: start` que ahí no va: las
  reseñas no se estiraban y cada una quedaba del ancho de su texto (medido: 477 px
  y 301 px), así que **el `border-bottom` que las separa cortaba a lo largo
  distinto en cada una y terminaba en el aire**.

Arreglado renombrando el wrapper de la ficha a `.resenias-ficha`. Verificado a
1440 px: «Reseñas recibidas» vuelve al grid `748px 300px` con el resumen al lado,
y las reseñas de la ficha se estiran a 618 px las dos, con un separador prolijo.

### El repaso a 390 px que había quedado sin hacer

Turnos y eventos habían quedado con las media queries escritas pero sin mirar en
un navegador. Hecho ahora con Playwright y Chrome real (`setViewportSize`, o sea
`innerWidth` de verdad 390, no un iframe): **29 pantallas × 2 anchos = 58
mediciones, cero desborde lateral**. `document.scrollWidth` da exactamente 390 y
768 en todas. Incluye home, listado, ficha, cartelera (con filtro y con día),
mis eventos, formulario, catálogo, detalle, mis productos, guardados, panel, las
cinco de admin, mis turnos, agenda, reservar, mi cuenta, reseñas, horarios, las
cuatro legales/institucionales y el 404.

La `.admin-table` mide 655 px a 390, pero va dentro de `.admin-table-wrapper` con
`overflow-x: auto` y la página no se desliza: es el patrón sancionado para tablas,
no un hallazgo.

### El calendario con enlaces `?dia=`, verificado en navegador

- Modo enlace en la cartelera: los días con eventos son `<a href="?dia=...">`.
- **Ida y vuelta con el botón de atrás**: atrás vuelve a `/eventos/` sin filtro y
  con la lista completa; adelante vuelve al día filtrado. Las dos direcciones.
- **Enlace compartible**: pegando en frío `?dia=` de un día del mes siguiente, el
  calendario abre en **su** mes («Octubre 2026») con el día marcado
  (`aria-current="date"`), no en el mes actual.
- El día ya elegido enlaza sin `?dia=`, así que volver a tocarlo suelta el filtro.
- Con `?tipo=taller` puesto, el día viaja como `?tipo=taller&dia=...`: elegir una
  fecha **no** suelta el tipo.
- **El modo «botón» del home no se rompió**: ahí los días son `<button>` sin
  `href`, tocarlos filtra el panel de al lado sin recargar (la URL sigue en `/`),
  el panel dice «Domingo 13 de septiembre» con su «Ver todo el mes», y volver a
  tocar suelta.

### Los dos estados vacíos y `/eventos/mios`

- «Todavía no hay eventos anunciados» ya sale **sólo** con la base realmente
  vacía (ver hallazgo 1); con filtros que no matchean sale «Nada con esos
  filtros», que explica cómo soltarlos y trae «Ver todas las fechas».
- Un evento **sin tipo** aparece en «Todos», no dibuja chip y **no entra en
  ninguno de los cuatro filtros por tipo** (probado con un evento con `tipo=NULL`,
  los cuatro filtros uno por uno). Un `?tipo=` inventado se ignora.
- `/eventos/mios` resuelve el permiso **server-side**: `@login_required` más el
  join `Post.author == g.user.id`. Sin sesión rebota al login; con la sesión de
  otro usuario no se ve ni un evento ajeno; editar o borrar un evento de otro
  rebota y **no** borra la fila.
- **El menú del panel tiene sus 8 ítems** y los 8 responden 200 para el dueño y
  302 al login sin sesión: Inicio del panel, Emprendimientos, Catálogo,
  Servicios, Presupuestos, Agenda de turnos, Eventos y ferias, Reseñas recibidas.
  Ningún ítem anterior se rompió al agregar el octavo.

### Navegación y ficha: nada de las seis tandas nuevas las pisó

La navegación quedó intacta: dos bandas, tres secciones (sin «Inicio», que es el
logo), Favoritos y Mensajes como iconos, «Publicar» fuera de la barra, los badges
pidiendo **cada uno su número** por `data-notif` (`unread_messages`,
`pending_service_requests`, `unanswered_reviews` — no sumados), el
`[hidden] { display: none !important }` haciendo efecto, cinco pestañas abajo con
sesión y tres sin ella (Inicio · Explorar · Entrar). La ficha también: nueve
bloques, estrellas en SVG, reseñas firmadas con nombre (ningún «Usuario #7»),
«Dónde encontrarla» presente, productos como enlaces. Lo único que sí las pisó fue
el `.resenias` del hallazgo 3, ya arreglado.

### Barrido del CSS compartido

Las ocho tandas escriben en un solo `styles.css` de ~16.700 líneas donde, a igual
especificidad, gana el que va más abajo. Se cruzó cada selector del nivel de
arriba consigo mismo buscando declaraciones contradictorias, y cada clase contra
todos los templates y el JS **como token entero**:

- **25 selectores** con declaraciones contradictorias. Dos eran los hallazgos 2 y
  3; quedan **21**, y son de dos clases inofensivas: diferencias de redondeo
  (`0.66rem` vs `0.65625rem`) y **pisadas deliberadas por orden de archivo**.
- **84 clases sin ningún uso**; se borraron las **10 que estas tandas dejaron sin
  dueño** (85 líneas), todas de la vieja `MI CATALOGO`: `.catalogo__grupo*`,
  `.catalogo__conteo*`, `.producto__img`, `.producto--sin-stock`,
  `.producto__sello`, `.producto__cuerpo` y `.producto__desc`. Se confirmó contra
  la versión commiteada de `products/index.html` que las usaba antes de que la
  tanda del panel la reescribiera como `mios.html` con `.fila-prod*`. Quedan 74,
  todas preexistentes y ajenas a estas tandas.

**Lección de método, y casi una macana: un bloque duplicado NO es
necesariamente borrable.** El análisis de choques sólo ve las propiedades que se
contradicen; las que no chocan **cascadean y se suman**. Por eso la sección vieja
de `MI CATALOGO` parecía muerta y no lo está:

- `.producto` le sigue aportando a `templates/products/detalle.html` el borde, el
  radio, el fondo y el `overflow: hidden`, que el bloque nuevo **no** redeclara;
- `.catalogo__vacio` vive ahí dentro, es su **única** declaración y la usan cuatro
  pantallas (`products/mios.html`, `panel/inicio.html`, `admin/usuarios.html` y
  `admin/emprendimientos.html`), tres de ellas de las tandas nuevas.

Lo mismo vale para la `.cartelera__cta` de agosto: **no es CSS muerto**. 7 de las
14 clases de esa sección son la única declaración de clases vivas, o sea la tanda
de eventos construyó **encima** de la de agosto y le pisa 6 selectores por orden
de archivo. Se deja como está, documentado. Y vale también para renombrar, no sólo
para borrar: fue justamente lo que pasó con el `align-items` del hallazgo 3.

Tres guardas nuevas en `tests/test_css_compartido.py` para que los dos choques no
vuelvan sin que nadie se entere: el HTML no cambia cuando se pisan las clases, así
que la suite no los veía.

### Lo que la auditoría NO encontró

Sin hallazgos propios en catálogo, páginas (sobre/contacto/legales/errores),
admin, panel del vendedor ni turnos, más allá de lo compartido de arriba.

Archivos que tocó la auditoría: `views/eventos.py`, `templates/eventos/index.html`,
`templates/products/mios.html`, `app/blog/templates/blog/detail.html`,
`static/css/styles.css`, `tests/test_eventos.py` (2 tests nuevos),
`tests/test_ficha.py` (3 recortes reapuntados a `.resenias-ficha`),
`tests/test_css_compartido.py` (nuevo, 3 tests), `disenio-inicio/DISENIO.md`.

## Plan de las tandas de rediseño — DECIDIDO 9/9, CUMPLIDO 10/9

**Primero se implementan las ocho tandas; recién después vienen las auditorías y
lo que falte agregar.** Ninguna se auditó ni se pusheó de a una: las ocho
—navegación, ficha, catálogo, páginas, admin, panel del vendedor, turnos y
eventos— se cerraron y se dejaron sin auditar a propósito hasta tenerlas todas.

**AL 9/9 ESTÁN LAS OCHO y AL 10/9 LA AUDITORÍA DEL CONJUNTO ESTÁ HECHA Y
APROBADA** (ver «Auditoría de cierre del rediseño», arriba): tres hallazgos
reales, los tres arreglados en la misma vuelta. **El plan se cumplió entero.** Lo
que sigue es abrir el PR dev_tomy → main, que se confirma con Tomy aparte.

**El método se validó solo:** dos de los tres hallazgos fueron choques de nombres
de clase ENTRE tandas (`.interruptor` y `.resenias`), que es exactamente lo que
auditar de a una no habría encontrado — cada tanda por separado se veía bien, el
daño aparecía recién con las dos puestas.

**Por qué:** auditar de a una obliga a volver a cargar el contexto de cada tanda
dos veces, y varias comparten piezas (la barra, las fichas de filtro, los
parciales, el CSS) — un arreglo hecho en la auditoría de una se pisa con la
siguiente. Con las ocho puestas, la auditoría se hace una vez sobre el conjunto y
ahí también se decide qué falta implementar o agregar.

**Cómo aplicarlo:** al cerrar cada tanda, dejar anotado en `DISENIO.md` y acá lo
que quedó afuera y por qué, sin abrir la auditoría. La lista de pendientes chicos
vive al final de `DISENIO.md`, sección "Dónde retomamos".

## Escaneo de seguridad (DAST) — HECHO 10/9, SIN CRÍTICOS

Escaneo dinámico completo contra la app corriendo, no auditoría de código a secas. **Nunca se tocó `impulsar_db`**: se levantó un servidor DESCARTABLE en el puerto 5050 con `create_app("development")` pero con `DATABASE_URL` apuntando a un SQLite temporal en el scratchpad, `UPLOAD_FOLDER`/`PRIVATE_UPLOAD_FOLDER` redirigidos ahí también, sembrado con `scripts.seed.cargar()` (8 usuarios, 10 posts, 4 servicios, 3 solicitudes) y una ruta `/_entrar?uid=N` para probar como cada usuario. Guarda dura: `assert` de que la URI es el sqlite temporal antes de arrancar. El 5000 real nunca respondió durante toda la corrida (000), `git status` quedó limpio (sólo se trabajó en el scratchpad), el servidor descartable se apagó por PID al terminar. CSRF se desactivó SÓLO en el harness (para postear formularios con curl y llegar a los handlers); en la app real está activo (`csrf.init_app` global, exento sólo en las 3 rutas de API que se autentican por header). Seis frentes, cada uno con request/response real:

- **SQL injection — NO vulnerable.** Payloads clásicos (`' OR 1=1--`, `'; DROP TABLE users;--`, `UNION SELECT password`) en `q`, `category`, `page`, `tipo`, `dia`, `mes` de `/blog/`, `/api/posts/`, `/eventos/`, `/api/eventos/`, `/servicios/buscar`: todos tratados como texto literal (HTTP 200, 0 resultados; `q=pan` sí matchea). Tabla `users` intacta tras los DROP (8 filas, 16 tablas). Confirmado en código: cero SQL crudo, cero interpolación de strings — todo ORM parametrizado (`.ilike(patrón)`, `== columna`), y los comodines de LIKE se escapan (`_escapar_like`).
- **XSS reflejado y persistente — NO vulnerable.** Inyecté `<script>`, `<img onerror>`, `[x](javascript:alert)` en bio, título/cuerpo de post y campos de búsqueda; todo sale escapado (`&lt;script&gt;`). No hay un solo `|safe`, `autoescape false` ni `Markup(` en templates fuera de `render_biography`, que escapa PRIMERO y sólo linkea `http(s)://` (bloquea `javascript:` sin lista negra). El único HTML crudo de la app está bien blindado.
- **Fuerza bruta en login — SIN PROTECCIÓN (importante).** 25 logins fallidos seguidos contra `/auth/login` = 25×HTTP 200 con el mismo mensaje, sin lockout, sin rate-limit, sin CAPTCHA, y la clave correcta entró (302) al intento 26. El único freno es el costo del hash (~0.3 s/intento). Mismo hueco en `/auth/api/login`. **Es uno de los dos hallazgos accionables.**
- **IDOR — NO vulnerable en ningún dominio con edición.** Cruzando usuarios reales del seed: Lucia intentando editar/borrar post y servicio de Diego → rechazo (redirect a «mis-emprendimientos», fila intacta); Nicolas viendo la solicitud y la foto privada de Camila/Bruno → 403; Lucia (emprendedora ajena) viendo/respondiendo solicitudes de Diego → 403; Diego editando producto/evento de Lucia → rechazo; Lucia leyendo el chat de Diego → 403 (participante y dueño 200, tercero 403); Bruno cancelando un turno de Nicolas → rechazo, turno intacto. Guardado consistente por `es_el_autor`/`es_parte_del_turno`/`_solicitud_visible` en la vista, no en el template.
- **Subida de archivos maliciosos — NO vulnerable.** PHP renombrado a `.jpg` → rechazado por `Pillow.verify()` («no parece una imagen válida»); bomba de descompresión 8000×8000 (64 Mpx) → rechazada por el tope de píxeles (50 Mpx); nombre `../../../../evil.png` → `secure_filename` lo dejó dentro de uploads como `05fe1657_evil_9260.png`, nada escapó; polyglot PNG+PHP → el re-encode de Pillow borró el `<?php` (0 ocurrencias en el archivo guardado). Además uuid en el nombre y carpeta privada fuera de `static/`.
- **Headers de seguridad — FALTAN TODOS (importante).** Ninguna respuesta, en ningún entorno, trae `Content-Security-Policy`, `X-Frame-Options`, `X-Content-Type-Options` ni `Referrer-Policy` (no hay `after_request` ni Talisman en el proyecto). El header `Server:` filtra versión de Werkzeug/Python (cosmético). Las cookies sí tienen `HttpOnly`; `Secure`/`SameSite` sólo en prod (correcto). **Es el otro hallazgo accionable:** expone a clickjacking y MIME-sniffing, y deja al XSS sin defensa en profundidad.
- **Endpoints lentos / sin límite — NO encontrado.** Todos los listados paginan; `/api/posts/` capea `per_page` a 50 (`?per_page=999999`→50, negativo/0→1); la búsqueda se resuelve en la BD, no en Python. Barrido de tiempos: todo <15 ms salvo `/productos/` en el primer hit frío (103 ms → 14 ms estable, pagina con `joinedload` sin N+1). La «lentitud» que preocupa no viene de una query sin límite en estos endpoints.

**Resultado: cero críticos.** Dos hallazgos IMPORTANTES para una tanda de fixes con Sesión 1 — (1) login sin rate-limit/lockout (frontend y API), (2) headers de seguridad ausentes (CSP, X-Frame-Options, X-Content-Type-Options, Referrer-Policy). Todo lo demás (inyección, XSS, IDOR, uploads, queries sin límite) resistió el escaneo. No se arregló nada en esta pasada, sólo se reportó.

## Tanda de seguridad — los dos hallazgos del DAST, CERRADOS 10/9

Los dos accionables del escaneo de arriba, arreglados y verificados contra un servidor real (descartable, SQLite temporal en el scratchpad; **`impulsar_db` nunca se tocó**, con `assert` de la URI antes de arrancar).

**1. Fuerza bruta en el login — CERRADO.** `services/rate_limit.py`, hecho a mano y no con Flask-Limiter, decidido así porque Flask-Limiter cuenta *requests* por ventana y lo que hace falta es contar *fallos consecutivos*: con un `@limit("6/10minutes")` el sexto login del día se rechaza aunque los cinco anteriores hayan estado bien, que molesta al usuario legítimo sin frenar más al atacante. Se puede forzar con `deduct_when=`, pero lo que queda de la librería después de eso es un contador con ventana, que es justamente lo que hay en el módulo; y el proyecto pinea hasta las dependencias indirectas (Flask-Limiter arrastra `limits` y `deprecated`). Dos límites en paralelo, los dos en `config.py`: **por cuenta** 5 fallos → 10 min (el ataque de siempre, muchas claves contra una persona) y **por IP** 20 fallos → 10 min (el rociado, una clave común contra muchas cuentas, que nunca llena el contador de ninguna; flojo a propósito para no dejar afuera a una oficina con NAT en el quinto intento). Entrar bien limpia el contador de la cuenta pero **no el de la IP**: si lo limpiara, a un atacante con cuenta propia le alcanzaría con entrar cada veinte intentos para que el límite por IP no existiera. La clave de IP la comparten las dos rutas, así que gastar el cupo en `/auth/login` no deja fresco a `/auth/api/login`. El chequeo va **antes** de buscar en la base y de verificar el hash: al bloqueado el intento no le cuesta ni una consulta. Los dos devuelven 429 con `Retry-After` y el mismo cartel, que no dice cuál de los dos límites saltó ni si el usuario existe. Una cuenta suspendida que reintenta con la clave **correcta** no suma fallos (no hay nada que adivinar, y contarla la dejaría bloqueada además de suspendida); con la clave **mal** sí suma, y esa mitad es de las que salió de la auditoría: el chequeo de baneo va después del de contraseña, así que una suspendida con la clave mal cae en «la contraseña es incorrecta», y si el perdón mirara `is_banned` en vez de la credencial, una cuenta baneada conocida serviría para probar claves sin gastar el contador de la IP.

Verificado contra el servidor real: `/auth/login` da 200 en los intentos 1 a 5 y **429 en el 6**, y ahí la clave correcta también se rechaza (el intento 26 del escaneo ya no entra); `/auth/api/login` igual, 401 hasta el quinto y 429 en el sexto.

**LIMITACIÓN CONOCIDA, ANOTADA EN EL MÓDULO:** el contador es un diccionario en memoria del proceso. Con varios workers cada uno lleva el suyo y el límite efectivo se multiplica por la cantidad de workers. Sigue cortando la fuerza bruta (que necesita miles de intentos, no veinte), pero el día que el deploy tenga más de un worker lo que se cambia es ese módulo y nada más, que es la única puerta.

**2. Cabeceras de seguridad — CERRADO.** `services/seguridad.py` + un `after_request` en `main.py`, a mano y no con Flask-Talisman: Talisman además fuerza HTTPS, reescribe cookies y mete HSTS, y esas decisiones ya están tomadas en otro lado (cookies en `config.py`, HTTPS en el proxy del deploy), así que vendría a pelear con lo que hay; y la parte que cuesta —enumerar los orígenes del mapa y las tipografías— se escribe a mano igual. Salen en **toda** respuesta, páginas de error y `static/` incluidos: `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY` (DENY y no SAMEORIGIN: no hay un solo `<iframe>` en los templates, chequeado), `Referrer-Policy: strict-origin-when-cross-origin` y una CSP con `frame-ancestors 'none'`, `form-action 'self'`, `base-uri 'self'` y `object-src 'none'`.

La CSP es **por nonce y no con `'unsafe-inline'`** en `script-src`, que es la decisión que le da sentido: con `'unsafe-inline'` un `<script>` inyectado se ejecuta igual y la política no defiende de nada. Los tres scripts escritos en el HTML (el que elige el tema en `base.html` y los dos que arman el mapa) llevan `nonce="{{ csp_nonce() }}"`, y los cuatro `<select onchange="this.form.submit()">` pasaron a `data-autoenviar` con un listener delegado en `main.js`, porque un nonce no alcanza para un atributo `onXXX`. El nonce se genera en un `before_request` y **no** perezosamente: `g` cuelga del contexto de *aplicación*, así que con uno empujado desde afuera sobrevive de un request al siguiente, y un nonce repetido es tanto como no tener nonce. `style-src` sí conserva `'unsafe-inline'`, y es la concesión de esta política: hay una docena de `style=""` en los templates y maplibre inyecta estilos propios en runtime.

Verificado con Chrome real contra el servidor descartable, **cero violaciones de CSP** en home, listado, ficha con mapa, eventos, catálogo, detalle de producto, login, perfil, panel, favoritos y el chat. Además, a mano en la consola: el worker desde `blob:` se crea, un tile de `api.maptiler.com` carga, la hoja de Google Fonts carga, el `<script>` con nonce ejecuta (el tema se aplica) y el bloque `<script type="application/json">` del chat se sigue parseando. El mapa no llega a dibujarse en esta máquina porque `MAPTILER_KEY` está vacía en el `.env` (403 con `key=`) — es previo y ajeno a la CSP: que la request salga y le contesten 403 es justamente la prueba de que `connect-src` la deja pasar.

**`PROXY_FIX_X_FOR` HAY QUE PONERLO EN EL DEPLOY.** Es lo que salió de auditar el límite por IP: publicada detrás de nginx o de un Render, `request.remote_addr` es la del proxy y la misma para todos, con lo cual el límite por IP se convierte en un límite **global** y veinte fallos de cualquiera dejan a todo el mundo diez minutos afuera. `PROXY_FIX_X_FOR` (cuántos proxies hay adelante) prende `ProxyFix` y hace que se lea la dirección real. Arranca en **cero a propósito**: sin proxy adelante, creerle a `X-Forwarded-For` es peor que ignorarlo, porque lo escribe el cliente y se inventa una dirección por intento. Hay un test para cada una de las dos mitades.

**Lo que NO se hizo, y por qué:**

- **El header `Server` sigue delatando versión.** Se intentó pisarlo con un `"Server": "Impulsar"` en las cabeceras fijas y **no funciona**: esa línea la escribe el servidor HTTP, no Flask, y el de desarrollo la manda siempre — la respuesta salía con dos `Server:`, la que delata primero. Peor que antes, así que se sacó. Es de la capa que habla HTTP: `server_tokens off` en nginx o el flag del WSGI que se use. El escaneo ya lo había marcado como cosmético.
- **`'unsafe-inline'` en `style-src`.** Sale recién cuando se saquen los ~12 `style=""` de los templates, y aun así maplibre inyecta los suyos. Tanda aparte.
- **El registro (`/auth/register`) no tiene límite.** El pedido era el login; el alta masiva de cuentas es otro problema y otra tanda.

Tests: `tests/test_rate_limit.py` (19) y `tests/test_seguridad.py` (13). Los dos de este último que miran los *templates* y no una respuesta son los que importan a futuro: con una CSP por nonce, un `<script>` sin nonce no rompe ningún test de vista (la página responde 200 igual), simplemente deja de ejecutarse en el navegador, y ese silencio es lo que cortan. La fixture autouse `limite_de_login_limpio` de `conftest.py` vacía el contador entre tests: sin ella los fallos de uno se le suman al siguiente y el resultado depende del orden.

## Tanda de fixes de la auditoría general — LOS 6 BUGS, CERRADOS 10/9

Los seis bugs reales de `docs/AUDITORIA-GENERAL-10-9.md` (Sesión 2, sobre `main` @ `144a188`). Cada uno verificado donde el bug vivía: los de backend contra MySQL real, los de CSS y accesibilidad contra Chrome real y el toggle de tema de la app.

**B1 — Largos sin validar → 500 en MySQL. CERRADO.** Las tres puertas (`views/eventos.py`, `views/products.py`, `app/servicios/formulario.py`) validan ahora las 8 columnas: `Event.titulo/descripcion/lugar`, `Product.nombre/descripcion`, `Service.titulo/descripcion/zona_cobertura`. Los máximos salen de la columna con `largo_de(Columna)` y el chequeo es `validar_largo()`, los dos nuevos en `services/validation.py`: se puso ahí y no repetido en cada dominio porque el mensaje tiene que ser el mismo en los tres, y el comentario que explica por qué hace falta también. Es el patrón de `MAX_TITULO` (`app/blog/reglas.py`) llevado a función porque ahora lo usan cuatro dominios.

**EL TEST DISCRIMINA, Y ESTÁ PROBADO QUE DISCRIMINA.** `tests/test_largos.py` tiene dos mitades: 18 casos en SQLite (el formulario contesta y no guarda) y 9 contra **MySQL real en modo estricto**, en base descartable `impulsar_test_largos`. La fixture se saltea sola si no hay servidor **y también si el `sql_mode` no es estricto**, porque sin modo estricto MySQL trunca en silencio y el test pasaría sin probar nada. Contraprueba hecha: desactivando la validación de eventos fallan los 3 de MySQL **y** los 3 de SQLite; restaurada, los 27 pasan. El `sql_mode` de esta máquina se verificó en el momento: `ONLY_FULL_GROUP_BY,STRICT_TRANS_TABLES,...`.

**B2 — Conteo por mes falso. CERRADO.** `total_por_mes(query)` (nuevo, en `services/eventos.py`) hace un COUNT agrupado sobre la consulta **filtrada y sin el LIMIT**, y `agrupar_por_mes(eventos, totales)` lo usa para el rótulo. La LISTA de cada grupo sigue siendo la de la página (un mes partido se recorre en dos pantallas, que es lo que ya pasa con cualquier corte por fecha); lo que cambia es el número de al lado. El escenario exacto de la auditoría está como test: 14 eventos en octubre con 9 por página daban 6 y 7 en páginas distintas, ahora dicen 14 las dos.

**El `order_by(None)` de esa función no es decorativo y está medido.** La consulta llega ordenada por fecha, hora e id, y esas columnas no están en el GROUP BY: contra MySQL 8 real, sin sacar el orden es `OperationalError 1055 ("Expression #1 of ORDER BY clause is not in GROUP BY clause")`, porque `ONLY_FULL_GROUP_BY` viene prendido de fábrica. SQLite lo acepta sin decir nada — o sea que B2 mal arreglado era otro 500 que sólo aparecía en producción. Se probó a propósito con y sin, en una base descartable.

**B3 — Contraste 1.30:1 en oscuro. CERRADO.** `#fff` literal en `.cartelera__cta`, `.cartelera__cta-titulo`, `.rubro--todos` y `.rubro--todos .rubro__tono`. Son **cuatro** y no los tres del informe: el contenedor `.cartelera__cta` tenía el mismo `--color-on-primary` que su título, y arreglar sólo el título dejaba el bug en todo lo que hereda de él. Medido con el toggle real de la app, no forzando `data-theme`: **1.30:1 → 13.95:1**, y 13.95:1 también en claro. El comentario viejo decía que `--color-primary-deep` «vale lo mismo en claro y en oscuro» — cierto del fondo, falso de la tinta; ahora lo aclara.

**B4 — El visor no era un diálogo. CERRADO.** `role="dialog"` + `aria-modal="true"` + `aria-label` en los dos visores, y trap de foco en `static/js/visor.js`. Medido en la página real con el visor abierto: **0 escapes en 12 Tab y en 6 Shift+Tab**, y con el foco puesto afuera a mano el siguiente Tab lo trae de vuelta adentro. Lo que ya andaba sigue andando: Escape cierra y el foco vuelve al disparador (verificado, no asumido). Se eligió trap y no `inert` porque el trap no depende del soporte de `inert`, y `aria-modal` ya cubre la mitad que le toca al lector de pantalla.

**B5 — Enlaces de foto sin nombre accesible. CERRADO, con una corrección al arreglo propuesto.** Los cuatro enlaces llevan `tabindex="-1" aria-hidden="true"`, como `.tarjeta__foto` de Explorar. **Pero el cartel de «Sin stock» vivía adentro de ese enlace**, y es el único lugar de la tarjeta que dice que no hay stock: aplicar el par de atributos tal cual lo habría dejado mudo para un lector de pantalla, cambiando un bug de accesibilidad por otro. Así que el cartel salió afuera del `<a>` en las tres plantillas que lo tienen. Se mantiene en el mismo lugar visual porque `.producto-tarjeta` ya era `position: relative`; `.producto-ficha` **no** lo era y se le agregó. Verificado en pantalla: los carteles quedan a 10px/10px y 9px/9px de la esquina de su foto (exactamente lo que pide el CSS), visibles, dentro del recuadro y fuera de cualquier `aria-hidden`; y 0 enlaces de foto en el recorrido del Tab.

**B6 — `aria-pressed` en `<a>`. CERRADO.** Los cinco chips pasaron a `aria-current="true"` sólo cuando están activos, como ya hace la cartelera de eventos. Los 8 `aria-pressed` restantes se verificaron uno por uno con un parser: los 8 están sobre `<button>`, ninguno sobre `<a>`.

### Lo que salió de la auditoría de la tanda de seguridad (Sesión 2), arreglado acá

Cuatro hallazgos sobre el rate-limit del login, que todavía no estaba pusheado. Los tres primeros eran agujeros reales del contador:

- **La clave de cuenta salía del texto que mandaba el cliente.** El formulario manda username y la API email, así que la misma persona tenía DOS contadores y alternando las puertas entraban 10 contraseñas erradas en vez de 5 (Sesión 2 lo midió: primer 429 en el intento 11). Y `.lower()` no pliega tildes mientras que la collation de MySQL sí, así que cada variante con o sin tilde regalaba otros cinco.
- **El arreglo cuenta en DOS claves de cuenta a la vez**, no en una: por id del usuario (la misma venga del formulario o de la API) y por texto normalizado con `normalizar_username` (cubre al usuario que no existe, y no depende de la collation — en SQLite el `filter_by` es exacto y no encontraría la variante con tilde). Alcanza con que cualquiera esté bloqueada. Se busca primero al usuario y después se chequea: lo caro, el hash, sigue estando después del chequeo.
- **`bloqueo <= ventana` ahora la sostiene la función** (`ventana = max(ventana, bloqueo)`) y no la convención de config: con una ventana más corta, `_podar` tiraba los fallos antes de que la espera terminara y el bloqueo se levantaba solo (medido: bloqueo=60, ventana=1, decía 60 s y 1,2 s después 0).
- **`PROXY_FIX_X_FOR` ya no puede tumbar el arranque.** Se lee al importar `config`, así que un valor mal escrito en el deploy era un `ValueError` sin contexto en vez de un default; ahora cae en 0, que es el valor seguro.

### Backlog que dejó esta tanda (no bloqueante, para decidir)

- **El login por formulario enumera usuarios.** Contesta «El usuario es incorrecto» vs «La contraseña es incorrecta», así que una sola request dice si un username existe. `api_login` ya lo hace bien («credenciales inválidas» para los dos casos). **No se tocó porque cambia el mensaje que ve todo el mundo** y esa es una decisión de producto, no de implementación: el mensaje específico es más amable con quien se equivocó de usuario. Lo decide Tomy.
- **`/auth/api/register` no tiene ningún freno**, está exenta de CSRF y hace un `generate_password_hash` por request: mandando un username nuevo cada vez se gasta CPU sin límite. Es el mismo agujero que se acaba de cerrar en el login, en el endpoint de al lado. Queda para su propia tanda.
- **La CSP permite todo `https://unpkg.com`** en `script-src`, y ahí publica cualquiera. Los dos tags de maplibre ya están pineados a 5.24.0, así que `integrity` + `crossorigin="anonymous"` lo cerraría en dos líneas.
- **La CSP no tiene `report-uri` ni `report-to`**: en producción, una violación en un navegador o un flujo que no se probó a mano no la ve nadie.
- **`worker-src blob:` no incluye `'self'`**: hoy sólo lo usa maplibre, pero un worker propio en el futuro se caería sin aviso.
- **M1 del informe**: `.detalle__lateral #map` (`styles.css:1690`) quedó sin bloque de declaraciones y se traga el `@media` de abajo. Hoy no rompe nada visible porque esas clases ya no las usa ningún template, pero es un error de sintaxis vivo.

## H1 y H2 de la auditoría de las dos tandas — CERRADOS 10/9

Los dos primeros hallazgos de `docs/AUDITORIA-TANDAS-SEGURIDAD-Y-6-BUGS.md` (Sesión 2, sobre el diff de la tanda de seguridad + la de los 6 bugs). H3 y H4 quedaron sin tocar en esta pasada, ver abajo.

**H1 — El nombre de archivo generado se pasaba de la columna. CERRADO.** `services/uploads.py` armaba `uuid[:8] + "_" + secure_filename(original)` sin recortar nunca: 9 caracteres fijos más el original, contra las **siete** columnas `String(100)` que lo guardan (`User.avatar`, `User.cover_image`, `Post.image`, `PostImage.filename`, `Product.foto`, `ServiceRequest.foto`, `VerificationRequest.foto`). Reproducido: un nombre de 100 caracteres perfectamente legal da **109**. En MySQL estricto eso es `DataError 1406` — un 500 para el usuario; en SQLite entra igual y quedan 109 caracteres en una columna de 100.

Es la misma clase que B1 pero sobre **el único campo de texto que el usuario no tipea**, y por eso se le escapó a la tanda de largos: buscar formularios no lo encontraba. Se arregla en un solo lugar (`_nombre_unico()`), que cubre las 8 llamadas a `save_post_image`.

**Lo que se recorta es la base, nunca la extensión.** Cortar por el final se lleva el `.png`, y de la extensión dependen `allowed_file()` y el Content-Type que adivina el navegador al servir el archivo: un recorte ciego convierte una foto válida en un archivo sin tipo. El uuid tampoco se toca — es lo que hace único al nombre, así que dos subidas del mismo archivo largo siguen sin pisarse (hay test).

`MAX_NOMBRE_ARCHIVO = 100` se escribe a mano y no se lee de las columnas, por lo mismo que `MAX_EMAIL_LENGTH` en `services/validation.py`: `config.py` importa `services/uploads.py`, así que importar los modelos desde ahí sería un import circular. Lo que lo ata es `test_el_tope_coincide_con_las_columnas`, que recorre las siete una por una y dice cuál se despegó.

Contraprueba de que los tests discriminan: desactivando el recorte fallan 4 (el nombre largo, los tres nombres raros del parametrize); con el recorte puesto pasan los 23 de `test_uploads.py`.

**H2 — La cartelera no tenía ningún test contra MySQL. CERRADO.** El `order_by(None)` de `total_por_mes` estaba bien y verificado a mano, pero **nada impedía que alguien lo sacara**: `tests/test_cartelera_conteo.py` corría entero en SQLite, y ése es el único lugar donde ese fallo existe. Sesión 2 lo midió parcheando la función y corriendo la suite de eventos: **124 passed** con un 500 de producción adentro.

Ahora hay dos tests contra MySQL real en base descartable `impulsar_test_cartelera`: uno sobre `total_por_mes` con la consulta real de la vista (ordenada por fecha, hora e id, que es lo que dispara el 1055) y otro sobre la pantalla entera, que es la que devolvía el 500. La fixture se saltea si no hay servidor **y también si falta `ONLY_FULL_GROUP_BY`**, porque sin ese modo MySQL acepta el GROUP BY flojo igual que SQLite y el test no probaría nada — el mismo criterio que la fixture de `test_largos.py` con `STRICT_TRANS_TABLES`.

Reproducido el escenario completo: sacando el `order_by(None)`, SQLite sigue dando **124 passed** y los dos tests nuevos de MySQL fallan con `OperationalError 1055`. Restaurado, los 11 de la cartelera pasan.

**Regla que queda de H2, y vale más allá de estos tests:** todo lo que genere SQL agregado (GROUP BY, HAVING, funciones de ventana) necesita al menos un test contra MySQL descartable. Es el tercer caso de la misma familia que el proyecto ya tenía anotada (CHECK que sale como `OperationalError`, `DateTime` sin microsegundos): diferencias MySQL/SQLite que la suite en SQLite tapa enteras. Que el *arreglo* de B2 fuera otro 500 de producción es el mejor argumento para la regla.

### H3 y H4 — no se tocaron en esta pasada

Tomy pidió arrancar por H1 y H2. Los otros dos quedan pendientes, con lo que reportó Sesión 2:

- **H3 — Un quinto `--color-on-primary`, en `.cartelera__cta-boton`** (`styles.css:16426-16429`, más el `:hover` en `:16432`). Está como `background-color` y no como `color`, por eso no apareció buscando la tinta. En oscuro el botón queda `rgb(22,19,42)` sobre el panel `rgb(42,32,104)`: **1,30:1 de superficie contra el panel**, el mismo ratio que se le sacó al título, con borde transparente. El texto del botón no falla (8,84:1 contra su propio fondo), así que un medidor de contraste de TEXTO no lo ve: lo que falla es el borde del control, **WCAG 1.4.11**. Y el comentario de arriba dice «acá el botón primario índigo desaparecería» — en oscuro deja de ser blanco y desaparece igual. Sesión 2 cruzó los 22 usos del token en el archivo: los otros 21 están sobre `--color-primary`, que es el uso correcto. Es el único que queda.
- **H4 — `largo_de()` sobre una columna `Text` devuelve `None`** (`services/validation.py`), y `validar_largo` con ese tope tira `TypeError`. Hoy no muerde porque los 8 campos validados son `String`, pero el docstring invita a usarlo en cualquier columna de texto y `ServiceRequest.descripcion` es `Text` a propósito. Un `assert` lo convierte en error de arranque en vez de 500 en el primer POST.

### Precisiones de Sesión 2 sobre los números de B3

El 13,95:1 vale para el contenedor, el título y `.rubro__nombre`. Dos matices: `.rubro--todos` va sobre un **gradiente**, así que su peor punto es el extremo claro y da **10,30:1** (sigue muy por encima de AA), y `.cartelera__cta-texto` compuesto con su alfa da **9,81:1**.

### Una de método: medir responsive ya no se puede con iframe

`frame-ancestors 'none'` rompió el truco de medir anchos con un `<iframe src=...>`: `contentDocument` viene `null`. **No es un bug, es el efecto buscado de la cabecera.** El reemplazo es `srcdoc` más un `<base>` inyectado. Cualquier verificación de anchos futura tiene que ir por ahí.

## Identidad visual — paleta índigo, VIGENTE

#3E2F94 primario, más tokens de hover/dark/soft del handoff de Design. Nota de accesibilidad: `color-mix()` sobre el primario puede fallar contraste en un tema — usar token propio fijo (`--color-primary-deep: #2A2068`, 13.9:1 en los dos temas) para bloques de marca.

## Backlog pendiente

- Recordatorio de turno próximo — PAUSADO, tiene costo/infraestructura. Investigación ya hecha: el modelo Turno tiene todo lo necesario, el problema es el disparo (no hay scheduler interno) — opción más barata es un endpoint protegido por secreto disparado por cron externo. Retomar cuando se confirme un disparador externo gratis.
- `%`/`_` como comodín de LIKE en el buscador — preexistente, heredado por las ramas nuevas de búsqueda en catálogo sin empeorarlo.
- `/api/posts/?q=` usa un criterio de búsqueda distinto al de `/blog/` — su propio `Post.title.ilike | Post.body.ilike`, sin pasar por `buscar_posts()`, no encuentra por catálogo. Inconsistencia real entre el listado HTML y la API.
- Decidir si SERVER_NAME faltante en ProductionConfig debería ser fatal (como SECRET_KEY) en vez de solo loguear un warning.
- Categoría inválida por URL a mano (`?category=no-existe`) en favoritos muestra el mensaje equivocado — cosmético.
- Orden A-Z de favoritos no pliega acentos igual en SQLite que en MySQL — puede ordenar distinto entre tests y producción.
- Banner de anuncios pagos/planes ("PLAN IMPULSO") NO adoptado: feature de cero (modelos Plan+Anuncio+Pago, pasarela de pago real, moderación, panel de anunciante, legales). Épica aparte.
- Verificación real de emprendimiento (hoy solo existe a nivel de un tipo de servicio puntual, no del emprendimiento entero).
- Mensajería directa entre perfiles sin post asociado — descartada a propósito por ahora, mensajería normal ya existe completa.
- Fusión de navegación Productos/Servicios/Solicitudes en tabs — se optó por el fix mínimo de navegación, sigue en backlog como posible frente propio si se quiere fusionar de verdad.
- CSV export de usuarios, "Exportar métricas", audit log de quién baneó a quién en el panel de administración — backlog.
- MapLibre — upgrade a v6: requiere `type="module"` + `.mjs`. No urge, 5.24.0 es estable.
- `flask db downgrade base` en MySQL corta en `8f3c1d02b7a4` con «Cannot drop index 'uq_review_post_user': needed in a foreign key constraint» — PREEXISTENTE y ajeno a las tandas de rediseño, encontrado por la auditoría del 10/9 al bajar la cadena entera contra MySQL 8 real. En SQLite la cadena baja y sube completa sin problema. No bloquea nada: nadie baja a `base` en producción, y `downgrade` de un paso funciona bien. Para arreglarlo hay que dropear la FK antes del índice en ese downgrade, como ya hacen `b8f5c2e41a97` y `a4c17b8e6d20`.
- La sección vieja de `MI CATALOGO` en `styles.css` no se puede retirar aunque su pantalla ya no exista: `.producto` le aporta a `products/detalle.html` propiedades que el bloque nuevo no redeclara, y `.catalogo__vacio` es su única declaración y la usan cuatro pantallas. Si alguna vez se quiere limpiar de verdad, primero hay que mudar `.catalogo__vacio` a la sección de componentes compartidos y completar el bloque nuevo de `.producto`. Mismo caso, más entrelazado, con la `.cartelera__cta` de agosto.
- 21 selectores de `styles.css` siguen declarados dos veces con alguna propiedad contradictoria, todos inofensivos hoy (diferencias de redondeo, o pisadas deliberadas por orden de archivo). Son deuda de forma, no bugs: el riesgo es que mover una sección cambie quién gana.
- 74 clases de `styles.css` no las usa ningún template ni el JS, todas preexistentes a las ocho tandas (`.hero__*`, `.search__*`, `.filtros__*`, `.post-rating*`…). Barrido pendiente, sin apuro.
- Resto de mejoras opcionales menores (redacción de commits, docstrings, casos edge cosméticos) — no bloquean nada, se toman si hay tiempo en una tanda relacionada.

## Gotchas

- Push fantasma — verificar siempre con `git ls-remote`.
- Pushear el propio commit puede arrastrar (o dejar afuera) commits de otra tarea/tanda que ya estaban commiteados localmente — antes de aprobar un push, preguntar explícitamente por el rango completo. Chequeo confiable: `git fetch origin dev_tomy && git log --oneline origin/dev_tomy..HEAD`.
- Los tests pueden mentir con verde silencioso — verificar el fix con un método independiente del test nuevo.
- Contraprueba real > releer el código / > solo afirmar.
- Un número de tests reportado puede estar desactualizado si pasó tiempo/otras tandas entre el reporte y el push (confirmado: 834 reportado vs. 877 real el 6/9) — quien pushea/revisa debería correrla de nuevo en el momento, no confiar en el último número mencionado.
- `db.session.delete()` con cascade puede tapar un bug real de FK.
- En Windows, dos procesos pueden bindear el puerto 5000 sin error.
- Un EXISTS correlacionado filtra ANTES de paginar sin producto cartesiano; `lazy="selectin"`/`selectinload` cargan la relación DESPUÉS de traer la página — importante si se necesita que `paginacion.total` sea exacto con un filtro nuevo.
- `ImageOps.exif_transpose(imagen, in_place=True)` devuelve None.
- Pillow no corta decompression bombs por default.
- `send_from_directory` protege path traversal; `send_file` con ruta armada a mano NO.
- Un chequeo de permiso se resuelve en la vista, nunca acepta el bool desde request.
- `class="a" class="b"` es ignorado en silencio por el navegador.
- HTML no permite IDs duplicados — getElementById resuelve al primero en orden de documento.
- Un UNIQUE centinela previene doble-reserva del MISMO recurso exacto, no el solapamiento cruzado entre recursos relacionados.
- Bajo MySQL/InnoDB REPEATABLE READ, un lock adquirido después de una lectura ordinaria no garantiza datos frescos.
- Enfoque UI-first: `<fieldset disabled>`/disabled real (no solo gris) para controles sin backend. Cuando el dato no existe ni parcialmente en el modelo, se omite del todo — aplica también a features enteras y retroactivamente a lo ya publicado.
- Un chip de filtro que se muestra aplicado tiene que corresponder a un filtro que realmente se aplicó — mismo espíritu que la honestidad de datos, aplicado a la UI de estado del filtro.
- Un nombre de clase de CSS es un recurso COMPARTIDO entre tandas: reusarlo no da error ni rompe ningún test (el HTML no cambia), le cambia el dibujo a una pantalla que nadie volvió a mirar. Buscar el nombre en `styles.css` antes de bautizar un componente, y si hay choque renombrar lo NUEVO, no lo pusheado.
- Un bloque de CSS duplicado NO es necesariamente borrable ni renombrable sin consecuencias: un análisis de choques sólo ve las propiedades que se contradicen, y las que no chocan cascadean y se suman. Antes de borrar o renombrar, cruzar cada clase contra todos los templates y el JS como token entero, y mirar qué propiedades NO redeclara el bloque que se queda.
- Un estado vacío puede mentir de más de una forma: «no hay nada» y «no hay nada que matchee tu filtro» son dos, y «hubo y ya pasó» es una tercera que se disfraza de la primera cuando la consulta filtra por fecha. Contar los vacíos por cada motivo distinto, no por cada pantalla.
- `grid-template-columns: repeat(auto-fit, minmax(Npx, 1fr))` con un mínimo fijo causa scroll horizontal cuando el contenedor es más angosto que N — usar `minmax(min(Npx, 100%), 1fr)`.
- `db.paginate()` de Flask-SQLAlchemy 3.1 devuelve escalares, no filas — si la query original seleccionaba una tupla, paginar rompe el desempaquetado.
- Un CDN sin versión pineada puede empezar a resolver a una major nueva que dejó de publicar el formato que el `<script>` pedía — fix: pinear versión exacta en la URL del CDN.

## Identidad de Impulsar

Vigente: índigo (~#3E2F94) como paleta principal, en migración progresiva pantalla por pantalla vía el rediseño UI-first. El violeta #665DF1 va quedando solo en las partes que todavía no tuvieron su pasada completa del rediseño. Principio de marca sin cambios: profesional, moderna, elegante, empresarial, sin ser seria/aburrida, colores claros, diseños limpios, poco texto.

## Documentos relacionados

- `docs/AUDITORIA-VISUAL-29-8.md` — auditoría visual general del 29/8 sobre lo cerrado hasta esa fecha (hallazgos de contraste, targets táctiles, consistencia contra mockups de Design).
