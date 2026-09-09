# IMPULSAR — Contexto para retomar

**Última actualización: 8 de septiembre de 2026.** Perfil público, Cuenta, Turnos, calendario, grilla de rubros, Home, Emprendedor, Gestión, Explorar (radio + reseñas + "Abierto ahora"), "Mis servicios" en el menú de cuenta, reordenar fotos/elegir principal, la tanda de validaciones de backend (precios, horarios, título, contacto, views_count), notificaciones por email (Flask-Mail/Gmail, 3 disparadores), búsqueda en catálogo (productos/servicios disponibles, no solo título/body del post), Mis favoritos (orden por fecha de marcado con desempate, filtro por rubro, orden A-Z), tanda chica de backlog (mensaje de hora inválida, assert→ValueError en reordenar fotos, botón duplicado sacado), y la tanda de rediseño del home (buscador unificado, rubros con ícono SVG en grilla 4×2, tarjetas verticales tipo `.tarjeta`, `/api/posts/` con avg_rating/review_count/author_name): todos CERRADOS Y PUSHEADOS. Y los dos "chips que mienten" de la barra de filtros de `/blog/`, AUDITADOS Y PUSHEADOS los dos: el chip de cercanía (cerrado el 7/9, auditado y pusheado el 8/9 en `00e7132`) y el `<summary>` de la barra de filtros, segundo hallazgo de esa misma tanda (cerrado, auditado y pusheado el 8/9 en `e221f67` + `d3d5739`). Lo único SIN PUSHEAR hoy es la unificación de `CAMPOS_DEL_PERFIL`, cerrada el 8/9 y esperando la auditoría de Sesión 2. dev_tomy remoto en `90ae52b` (verificado con `git ls-remote` el 8/9). Ojo con este dato, que ya quedó viejo dos veces: decía 27d1710, después 4eba082, y en el medio se pushearon `e63586e`, `258fb0a`, `4eba082` (docs y canvas), `00e7132`, `16bc7c6`, `e221f67`, `d3d5739` y `90ae52b`. Verificarlo con `git ls-remote origin dev_tomy` antes de citarlo, no copiarlo de acá. 882 tests passed. Sobre el número: la suite medida en limpio el 7/9 daba 873 antes del fix del chip, con `tests/` byte a byte idéntico a 27d1710, así que el 877 que figuraba acá estaba mal anotado (no se borró ningún test); 873 + 3 del chip = 876, + 2 del `<summary>` = 878, + 4 de `CAMPOS_DEL_PERFIL` = 882.

## Qué es

Plataforma web para dar visibilidad a emprendimientos locales (Mendoza, Argentina). Registro, publicación con foto y ubicación, listado, búsqueda, reseñas. Proyecto académico con intención de escalar a algo real. Repo Franv-Dev/IMPULSAR. main en 008e1d5 (PR #1 mergeado). Rama de trabajo: dev_tomy. Remoto y local sincronizados en 27d1710.

Frentes en curso:

- Calendario del home: CERRADO (Tanda 1 de agenda).
- Turnos: CERRADO por completo (2a + 2b).
- Grilla de rubros en el home: CERRADA y pusheada, y ahora rediseñada de nuevo con íconos SVG en la tanda del 6/9 (ver abajo).
- Cuenta (4 pantallas): CERRADA y pusheada.
- Perfil público: CERRADO y pusheado (427d419).
- Rediseño visual (paleta índigo): VIGENTE, UI-first. Home, Emprendedor, Gestión y Explorar (radio + reseñas + "Abierto ahora") CERRADOS Y PUSHEADOS. Home recibió una segunda pasada de rediseño el 6/9 (buscador unificado, rubros con ícono, cards verticales).
- Separación de navegación emprendimientos/servicios: CERRADA Y PUSHEADA (5fdcf44).

Pendiente, deliberadamente pospuesto: abrir el PR dev_tomy → main — se retoma después de que el rediseño visual esté razonablemente completo.

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

## `CAMPOS_DEL_PERFIL` — una sola lista de campos del perfil — CERRADO (8/9), PENDIENTE DE AUDITORÍA

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

Estado: fix y tests listos, sin pushear. Falta la auditoría de Sesión 2.

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
- `grid-template-columns: repeat(auto-fit, minmax(Npx, 1fr))` con un mínimo fijo causa scroll horizontal cuando el contenedor es más angosto que N — usar `minmax(min(Npx, 100%), 1fr)`.
- `db.paginate()` de Flask-SQLAlchemy 3.1 devuelve escalares, no filas — si la query original seleccionaba una tupla, paginar rompe el desempaquetado.
- Un CDN sin versión pineada puede empezar a resolver a una major nueva que dejó de publicar el formato que el `<script>` pedía — fix: pinear versión exacta en la URL del CDN.

## Identidad de Impulsar

Vigente: índigo (~#3E2F94) como paleta principal, en migración progresiva pantalla por pantalla vía el rediseño UI-first. El violeta #665DF1 va quedando solo en las partes que todavía no tuvieron su pasada completa del rediseño. Principio de marca sin cambios: profesional, moderna, elegante, empresarial, sin ser seria/aburrida, colores claros, diseños limpios, poco texto.

## Documentos relacionados

- `docs/AUDITORIA-VISUAL-29-8.md` — auditoría visual general del 29/8 sobre lo cerrado hasta esa fecha (hallazgos de contraste, targets táctiles, consistencia contra mockups de Design).
