"""Tests de las cabeceras de seguridad (ver services/seguridad.py).

El escaneo dinamico no encontro NINGUNA en ninguna respuesta: ni CSP, ni
X-Frame-Options, ni X-Content-Type-Options, ni Referrer-Policy, y el Server
delataba la version de Werkzeug y de Python.

Hay dos clases de test aca. Los primeros miran una respuesta real; el ultimo
mira los templates, y es el que importa a futuro: con una CSP por nonce, un
<script> escrito en el HTML al que se le olvide el nonce no rompe ningun test
de vista (la pagina responde 200 igual), simplemente deja de ejecutarse en el
navegador. Ese silencio es lo que el test de abajo corta.
"""

import re

from services import seguridad


CABECERAS_ESPERADAS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
}


# ------------------------------------------------------ estan, y en todos lados

def test_una_pagina_normal_trae_todas_las_cabeceras(client):
    respuesta = client.get("/")

    for nombre, valor in CABECERAS_ESPERADAS.items():
        assert respuesta.headers[nombre] == valor
    assert respuesta.headers["Content-Security-Policy"]


def test_el_404_tambien_las_trae(client):
    """Una pagina de error se enmarca y se sniffea igual que cualquier otra."""
    respuesta = client.get("/no-existe-esta-ruta")
    assert respuesta.status_code == 404

    for nombre, valor in CABECERAS_ESPERADAS.items():
        assert respuesta.headers[nombre] == valor


def test_un_archivo_de_static_tambien_las_trae(client):
    """Es el que mas necesita el nosniff: ahi viven las imagenes que suben."""
    respuesta = client.get("/static/css/styles.css")
    assert respuesta.status_code == 200

    assert respuesta.headers["X-Content-Type-Options"] == "nosniff"


def test_el_login_las_trae_aun_cuando_rechaza(client):
    respuesta = client.post(
        "/auth/login", data={"username": "nadie", "password": "x"}
    )

    for nombre, valor in CABECERAS_ESPERADAS.items():
        assert respuesta.headers[nombre] == valor


def test_la_app_no_intenta_pisar_el_server(client):
    """El Server es del servidor HTTP, no de la app, y pisarlo desde aca duplica.

    Se probo contra el servidor real: con un "Server: Impulsar" en
    CABECERAS_FIJAS la respuesta sale con DOS lineas Server, y la que delata
    version (Werkzeug/Python) va primera igual. El test existe para que el
    intento no se repita; se apaga en nginx (server_tokens off), no aca.
    """
    assert "Server" not in seguridad.CABECERAS_FIJAS


# ------------------------------------------------------------------------ CSP

def test_la_csp_deja_pasar_el_mapa_y_las_tipografias(client):
    """Lo que el escaneo pidio mirar: la politica no puede romper lo que ya anda.

    maplibre viene de unpkg (script) y sus tiles, sprites y glyphs de maptiler
    (fetch + imagenes); las tipografias, de googleapis (css) y gstatic (woff2).
    """
    csp = client.get("/").headers["Content-Security-Policy"]
    directivas = dict(
        (d.strip().split(" ", 1) + [""])[:2] for d in csp.split(";") if d.strip()
    )

    assert seguridad.CDN_MAPA in directivas["script-src"]
    assert seguridad.CDN_MAPA in directivas["style-src"]
    assert seguridad.TILES_MAPA in directivas["connect-src"]
    assert seguridad.TILES_MAPA in directivas["img-src"]
    assert seguridad.CSS_TIPOGRAFIAS in directivas["style-src"]
    assert seguridad.ARCHIVOS_TIPOGRAFIAS in directivas["font-src"]
    # El worker y el canvas de maplibre salen de un blob:.
    assert "blob:" in directivas["worker-src"]
    assert "blob:" in directivas["img-src"]


def test_la_csp_no_permite_scripts_inline_sueltos(client):
    """Con 'unsafe-inline' en script-src la politica no defiende de nada."""
    csp = client.get("/").headers["Content-Security-Policy"]
    script_src = next(d for d in csp.split(";") if d.strip().startswith("script-src"))

    assert "'unsafe-inline'" not in script_src
    assert "'nonce-" in script_src


def test_la_csp_cierra_el_marco_y_el_formulario(client):
    csp = client.get("/").headers["Content-Security-Policy"]

    assert "frame-ancestors 'none'" in csp
    assert "form-action 'self'" in csp
    assert "base-uri 'self'" in csp
    assert "object-src 'none'" in csp


def test_el_nonce_de_la_cabecera_es_el_del_html(client):
    """Si no coinciden, el navegador tira el script y la pagina queda muda."""
    respuesta = client.get("/")
    html = respuesta.get_data(as_text=True)

    del_html = re.search(r'<script nonce="([^"]+)"', html)
    assert del_html, "la home dejo de tener el <script> con nonce de base.html"
    assert f"'nonce-{del_html.group(1)}'" in respuesta.headers["Content-Security-Policy"]


def test_cada_respuesta_trae_un_nonce_distinto(client):
    """Un nonce fijo es lo mismo que 'unsafe-inline': el atacante lo copia."""
    primero = client.get("/").headers["Content-Security-Policy"]
    segundo = client.get("/").headers["Content-Security-Policy"]

    assert primero != segundo


# --------------------------------------------- los templates, no las respuestas

def _templates_html():
    from pathlib import Path

    raiz = Path(__file__).resolve().parent.parent
    for carpeta in (raiz / "templates", raiz / "app"):
        yield from carpeta.rglob("*.html")


# <script ...> que no es una etiqueta de cierre. Lo que interesa de cada uno es
# si trae src (lo carga de afuera y la CSP lo mira por origen), si es un bloque
# de datos (type="application/json", que el navegador no ejecuta) o si es codigo
# escrito ahi, que sin nonce no corre.
_ETIQUETA_SCRIPT = re.compile(r"<script\b[^>]*>", re.IGNORECASE)

# Los comentarios se sacan ANTES de buscar. No es un detalle: estos templates
# se explican a si mismos y nombran etiquetas en prosa ("un <script src> seria
# una request mas"), asi que sin esto el test acusa cuatro comentarios. Se
# hace con regex y no con html.parser porque el problema son los comentarios
# de Jinja, que para html.parser son texto comun.
_COMENTARIOS = re.compile(r"\{#.*?#\}|<!--.*?-->", re.DOTALL)


def _sin_comentarios(template):
    return _COMENTARIOS.sub("", template.read_text(encoding="utf-8"))


def test_todo_script_escrito_en_el_html_lleva_su_nonce():
    sin_nonce = []
    for template in _templates_html():
        for etiqueta in _ETIQUETA_SCRIPT.findall(_sin_comentarios(template)):
            if "src=" in etiqueta or "application/json" in etiqueta:
                continue
            if "nonce=" not in etiqueta:
                sin_nonce.append(f"{template.name}: {etiqueta}")

    assert not sin_nonce, (
        "estos <script> no van a ejecutarse con la CSP puesta; agregales "
        'nonce="{{ csp_nonce() }}": ' + ", ".join(sin_nonce)
    )


def test_ningun_template_usa_un_manejador_inline():
    """onclick, onchange y companiia: un nonce no los habilita, solo 'unsafe-inline'.

    Los cuatro que habia (<select onchange="this.form.submit()">) pasaron a
    data-autoenviar, con un listener delegado en main.js.
    """
    inline = re.compile(r"\son[a-z]+\s*=\s*\"", re.IGNORECASE)
    culpables = [t.name for t in _templates_html() if inline.search(_sin_comentarios(t))]

    assert not culpables, (
        "manejadores inline en " + ", ".join(culpables) + "; movelos a un "
        "listener (ver data-autoenviar en static/js/main.js)"
    )
