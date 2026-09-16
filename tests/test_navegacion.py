"""Tests de la navegación: la barra, el menú de la cuenta y la barra de abajo.

Van todos contra el HTML renderizado, que es donde vive el rediseño de
`disenio-navegacion/`. Los que miran clases BEM las cruzan contra el template
que las escribe (`templates/base.html` y sus parciales), no contra una clase
recordada de una versión anterior: eso ya dejó una aserción muerta antes (la de
`filtros__limpiar` en test_blog.py).
"""

import re
from html.parser import HTMLParser


class _Recorte(HTMLParser):
    """Devuelve el trozo de HTML del primer elemento con la clase pedida.

    Con html.parser y no con regex porque los recortes que hacen falta son
    anidados -- el menu de la cuenta vive DENTRO del <header>, y varias
    afirmaciones son sobre lo que la barra ya no tiene. Un recorte por indices
    de string se pasa de largo y el test da verde por el lugar equivocado.
    """

    def __init__(self, clase):
        super().__init__(convert_charrefs=False)
        self.clase = clase
        self.profundidad = 0
        self.dentro = False
        self.piezas = []
        self.resultado = None

    def _anotar(self, texto):
        if self.dentro:
            self.piezas.append(texto)

    def handle_starttag(self, tag, attrs):
        clases = dict(attrs).get("class", "").split()
        if not self.dentro and self.clase in clases:
            self.dentro = True
            self.profundidad = 0
        if self.dentro:
            self.piezas.append(self.get_starttag_text())
            if tag not in ("img", "br", "input", "hr", "meta", "link", "path",
                           "circle", "rect"):
                self.profundidad += 1

    def handle_startendtag(self, tag, attrs):
        self._anotar(self.get_starttag_text())

    def handle_endtag(self, tag):
        if not self.dentro:
            return
        self.piezas.append(f"</{tag}>")
        self.profundidad -= 1
        if self.profundidad <= 0 and self.resultado is None:
            self.resultado = "".join(self.piezas)
            self.dentro = False

    def handle_data(self, data):
        self._anotar(data)

    def handle_entityref(self, name):
        self._anotar(f"&{name};")

    def handle_charref(self, name):
        self._anotar(f"&#{name};")

    def handle_comment(self, data):
        self._anotar(f"<!--{data}-->")


def _recortar(html, clase):
    parser = _Recorte(clase)
    parser.feed(html)
    parser.close()
    assert parser.resultado is not None, f"no se encontro ningun .{clase}"
    return parser.resultado


def _html(respuesta):
    return respuesta.get_data(as_text=True)


def _barra_de_arriba(html):
    """El <header class="navbar"> SIN el menu que cuelga del avatar.

    El menu se saca a proposito: "Publicar" y los contadores de presupuestos y
    resenias siguen existiendo en la pagina, pero adentro del menu. Sin sacarlo,
    las afirmaciones sobre lo que la barra ya no tiene darian verde por el lugar
    equivocado.
    """
    barra = _recortar(html, "navbar")
    if 'class="menu-cuenta"' in barra:
        barra = barra.replace(_menu_de_la_cuenta(html), "")
    return barra


def _menu_de_la_cuenta(html):
    return _recortar(html, "menu-cuenta")


def _barra_de_abajo(html):
    return _recortar(html, "tabbar")


def _secciones(html):
    return _recortar(html, "navbar__secciones")


# --- las secciones de la barra


def test_la_barra_tiene_las_cuatro_secciones_con_inicio_primero(client):
    """"Inicio" volvio a las secciones (2026-09-15).

    Habia salido porque un cuarto item montaba la nav, centrada al 50 % exacto
    y fuera del flujo, encima del bloque de acciones. La nav volvio al flujo y
    se centra en el hueco que le queda, asi que el cuarto item ya entra.
    """
    secciones = _secciones(_html(client.get("/blog/")))

    etiquetas = [t.strip() for t in re.findall(r">([^<>]+)<", secciones) if t.strip()]
    assert etiquetas == [
        "Inicio",
        "Emprendimientos",
        "Servicios",
        "Eventos y ferias",
    ]


def test_inicio_se_marca_activa_en_el_home(client):
    """El mismo trato que las otras tres: subrayada y con aria-current."""
    secciones = _secciones(_html(client.get("/")))

    activa = re.search(
        r'<a href="/"[^>]*class="navbar__seccion navbar__seccion--activa"[^>]*'
        r'aria-current="page"',
        secciones,
        re.S,
    )
    assert activa, '"Inicio" tendria que estar marcada activa en el home'


def test_la_seccion_de_la_pantalla_en_la_que_estoy_se_marca_activa(client):
    barra = _barra_de_arriba(_html(client.get("/eventos/")))

    activa = re.search(
        r'<a href="/eventos/"[^>]*class="navbar__seccion navbar__seccion--activa"[^>]*'
        r'aria-current="page"',
        barra,
        re.S,
    )
    assert activa, "la sección de eventos tendría que estar marcada activa"


def test_publicar_no_esta_en_la_barra_pero_si_en_el_menu_de_la_cuenta(
    client, crear_usuario, login
):
    """Era el único botón lleno de la barra y se repetía en cada pantalla."""
    login(crear_usuario().id)
    html = _html(client.get("/blog/"))

    assert "Publicar un emprendimiento" not in _barra_de_arriba(html)
    assert "Publicar un emprendimiento" in _menu_de_la_cuenta(html)


def test_el_buscador_tiene_su_propia_banda_con_los_dos_campos(client):
    barra = _barra_de_arriba(_html(client.get("/servicios/buscar")))

    assert 'class="navbar__banda"' in barra
    assert 'name="q"' in barra
    assert 'name="near"' in barra


def test_no_hay_dos_buscadores_apilados(client):
    """El home y el listado ya tienen el suyo, y mas completo (suman el rubro).

    Dibujar ahi tambien la banda de la barra deja dos buscadores uno arriba del
    otro preguntando lo mismo. Se vio en pantalla antes de que existiera este
    test.
    """
    for ruta, propio in (("/", "buscador__form"), ("/blog/", "barra-filtros")):
        html = _html(client.get(ruta))
        assert 'class="navbar__banda"' not in _barra_de_arriba(html), ruta
        assert propio in html, ruta


def test_el_buscador_de_la_barra_conserva_lo_que_se_busco(client):
    """Los valores salen de la URL del listado, que es a donde manda el form."""
    barra = _barra_de_arriba(_html(client.get("/servicios/buscar?q=pan")))

    assert 'name="q"' in barra
    assert 'value=""' in barra  # otra pantalla: no arrastra lo tipeado en ella


# --- el menú de la cuenta


def test_sin_sesion_no_hay_menu_de_la_cuenta(client):
    barra = _barra_de_arriba(_html(client.get("/blog/")))

    assert 'class="menu-cuenta"' not in barra
    assert "Acceder" in barra
    assert "Crear cuenta" in barra


def test_el_menu_de_la_cuenta_trae_los_tres_grupos(client, crear_usuario, login):
    """Tres grupos rotulados, no una lista de nueve."""
    login(crear_usuario().id)
    menu = _menu_de_la_cuenta(_html(client.get("/blog/")))

    assert "Mi actividad" in menu
    assert "Mi emprendimiento" in menu


def test_el_menu_de_la_cuenta_incluye_los_turnos(client, crear_usuario, login):
    """`/turnos/mios` y `/turnos/agenda` existían y no estaban en ningún menú."""
    login(crear_usuario().id)
    menu = _menu_de_la_cuenta(_html(client.get("/blog/")))

    assert 'href="/turnos/mios"' in menu
    assert 'href="/turnos/agenda"' in menu


def test_el_panel_de_admin_solo_le_aparece_al_admin(
    client, crear_usuario, login
):
    from models.user import Roles

    login(crear_usuario(username="comun").id)
    assert "Panel de administración" not in _menu_de_la_cuenta(_html(client.get("/blog/")))

    login(crear_usuario(username="jefa", rol=Roles.ADMIN).id)
    assert "Panel de administración" in _menu_de_la_cuenta(_html(client.get("/blog/")))


# --- los contadores, cada uno en su item


def test_el_sobre_de_la_barra_solo_cuenta_los_mensajes_sin_leer(
    client, crear_usuario, login
):
    """El badge de antes sumaba mensajes + reseñas + presupuestos en un número
    pegado a "Mensajes": eso era lo que lo hacía mentir."""
    login(crear_usuario().id)
    barra = _barra_de_arriba(_html(client.get("/blog/")))

    contadores = re.findall(r'data-notif="([a-z_]+)"', barra)
    assert contadores == ["unread_messages"]


def test_cada_contador_del_menu_va_en_su_item(client, crear_usuario, login):
    login(crear_usuario().id)
    menu = _menu_de_la_cuenta(_html(client.get("/blog/")))

    assert set(re.findall(r'data-notif="([a-z_]+)"', menu)) == {
        "unread_messages",
        "pending_service_requests",
        "unanswered_reviews",
    }


def test_los_contadores_nacen_ocultos(client, crear_usuario, login):
    """Los rellena main.js con /mensajes/notificaciones; sin JS no se ve un 0."""
    login(crear_usuario().id)
    html = _html(client.get("/blog/"))

    for etiqueta in re.findall(r"<span[^>]*data-notif=[^>]*>", html):
        assert "hidden" in etiqueta


def test_las_tres_claves_del_endpoint_son_las_que_pide_el_html(
    client, crear_usuario, login
):
    """La contraprueba de que los `data-notif` no apuntan a claves inventadas:
    se cruzan contra lo que el endpoint devuelve de verdad."""
    login(crear_usuario().id)
    html = _html(client.get("/blog/"))
    datos = client.get("/mensajes/notificaciones").get_json()

    pedidas = set(re.findall(r'data-notif="([a-z_]+)"', html))
    assert pedidas
    assert pedidas <= set(datos)


# --- la barra de abajo del teléfono


def test_con_sesion_la_barra_de_abajo_tiene_cinco_pestanias(
    client, crear_usuario, login
):
    login(crear_usuario().id)
    abajo = _barra_de_abajo(_html(client.get("/blog/")))

    assert abajo.count('class="tabbar__tab') == 5
    for etiqueta in ("Inicio", "Explorar", "Favoritos", "Mensajes", "Perfil"):
        assert etiqueta in abajo


def test_sin_sesion_la_barra_de_abajo_tiene_tres(client):
    """Favoritos y Mensajes piden login: como pestañas solo rebotarían."""
    abajo = _barra_de_abajo(_html(client.get("/blog/")))

    assert abajo.count('class="tabbar__tab') == 3
    assert "Entrar" in abajo
    assert "Favoritos" not in abajo


def test_la_hamburguesa_se_fue(client):
    assert "navbar__toggle" not in _html(client.get("/blog/"))


def test_entrar_y_crear_cuenta_no_traen_la_barra_de_abajo(client):
    """Son a pantalla completa sobre una foto: ya apagan la barra de arriba."""
    for ruta in ("/auth/login", "/auth/register"):
        html = _html(client.get(ruta))
        assert 'class="tabbar"' not in html
        assert 'class="tabbar__hueco"' not in html


def test_explorar_se_marca_activa_en_las_tres_secciones(client):
    for ruta in ("/blog/", "/servicios/buscar", "/eventos/"):
        abajo = _barra_de_abajo(_html(client.get(ruta)))
        assert "tabbar__tab--activa" in abajo, ruta


def test_favoritos_no_deja_explorar_marcada(client, crear_usuario, login):
    """`blog.my_favorites` empieza con "blog." pero es su propia pestaña."""
    login(crear_usuario().id)
    abajo = _barra_de_abajo(_html(client.get("/blog/favoritos")))

    activas = re.findall(r'class="tabbar__tab[^"]*tabbar__tab--activa[^"]*"', abajo)
    assert len(activas) == 1
    assert 'href="/blog/favoritos"' in abajo


# --- las solapas de sección del teléfono


def test_las_solapas_solo_estan_en_las_tres_pantallas_que_agrupan(client):
    for ruta in ("/blog/", "/servicios/buscar", "/eventos/"):
        assert 'class="solapas-seccion"' in _html(client.get(ruta)), ruta

    assert 'class="solapas-seccion"' not in _html(client.get("/"))


# --- Mi cuenta


def test_mi_cuenta_pide_sesion(client):
    respuesta = client.get("/perfil/mi-cuenta")

    assert respuesta.status_code == 302
    assert "/auth/login" in respuesta.headers["Location"]


def test_mi_cuenta_lleva_a_las_mismas_rutas_que_el_menu_de_escritorio(
    client, crear_usuario, login
):
    """Mismos items y mismo orden: es la misma navegación en otra forma."""
    usuario = crear_usuario()
    login(usuario.id)

    menu = _menu_de_la_cuenta(_html(client.get("/blog/")))
    cuenta = _html(client.get("/perfil/mi-cuenta"))

    destinos_del_menu = re.findall(r'class="menu-cuenta__item[^"]*"', menu)
    assert destinos_del_menu  # que el recorte no haya quedado vacío

    for ruta in (
        "/blog/create",
        "/mensajes/",
        "/servicios/solicitudes",
        "/turnos/mios",
        "/blog/favoritos",
        "/blog/mis-emprendimientos",
        "/productos/mios",
        "/servicios/",
        "/turnos/agenda",
        "/perfil/edit",
        "/auth/logout",
        f"/perfil/{usuario.slug}/resenias",
    ):
        assert f'href="{ruta}"' in menu, f"falta {ruta} en el menú de escritorio"
        assert f'href="{ruta}"' in cuenta, f"falta {ruta} en Mi cuenta"
