"""Cabeceras de seguridad que lleva toda respuesta de la app.

El escaneo dinamico encontro que no salia ninguna: ni CSP, ni X-Frame-Options,
ni X-Content-Type-Options, ni Referrer-Policy. Nada de esto arregla un agujero
que exista (el escaneo no encontro XSS: los templates escapan todo y el unico
HTML crudo, render_biography, escapa antes de linkear); son la segunda capa,
la que limita el dano el dia que se escape uno.

Se arma a mano y no con Flask-Talisman por dos motivos. Uno, Talisman hace
bastante mas que esto (fuerza HTTPS, reescribe cookies, HSTS) y esas decisiones
ya estan tomadas en otro lado del proyecto: las cookies se configuran en
config.py y el HTTPS lo resuelve el proxy del deploy, asi que la libreria
vendria a pelear con lo que ya hay. Dos, la CSP de esta app tiene que enumerar
los origenes del mapa y de las tipografias igual, o sea que la parte que
cuesta se escribe a mano en los dos casos; con Talisman ademas quedaria
escrita en un diccionario de kwargs en vez de aca, con el comentario al lado
que explica por que cada origen esta en la lista.
"""

import secrets

# Origenes de terceros que la app carga de verdad. Cada uno esta en la CSP
# porque hay una linea de HTML que lo pide; si se saca de los templates, sale
# tambien de aca.
CDN_MAPA = "https://unpkg.com"                  # maplibre-gl (js + css)
TILES_MAPA = "https://api.maptiler.com"         # estilo, tiles, sprites, glyphs
CSS_TIPOGRAFIAS = "https://fonts.googleapis.com"
ARCHIVOS_TIPOGRAFIAS = "https://fonts.gstatic.com"


def nonce_nuevo():
    """Un nonce por respuesta, para los <script> que van escritos en el HTML."""
    return secrets.token_urlsafe(16)


def politica_csp(nonce):
    """La CSP entera, como string.

    Las decisiones que no son obvias:

    - script-src va con NONCE y no con 'unsafe-inline'. Con 'unsafe-inline' la
      CSP no defiende de nada contra XSS, que es justo para lo que se pone: un
      <script> inyectado se ejecutaria igual. Los tres scripts escritos en el
      HTML (el que elige el tema en base.html y los dos que arman el mapa)
      llevan el nonce; los <select> que se auto-enviaban con onchange pasaron a
      un listener en main.js, porque un nonce no alcanza para un atributo
      onXXX, solo 'unsafe-inline' lo permitiria y volveriamos al principio.

    - style-src SI lleva 'unsafe-inline', y es la concesion de esta politica.
      Hay una docena de style="" en los templates (barras de progreso y colores
      calculados en el servidor) y ademas maplibre inyecta estilos propios en
      tiempo de ejecucion. Se acepta: un CSS inyectado puede afear la pagina o
      exfiltrar algo con mucho esfuerzo, no ejecutar codigo. Sacar los style=""
      es trabajo de otra tanda, y recien ahi el 'unsafe-inline' se puede ir.

    - blob: en worker-src e img-src es maplibre: crea su worker desde un Blob
      y dibuja los tiles en canvas. Sin esto el mapa no carga.

    - frame-ancestors 'none' repite lo que dice X-Frame-Options: DENY. Se
      escriben las dos porque no es la misma cabecera para el mismo navegador:
      frame-ancestors es la que vale hoy, X-Frame-Options la que entienden los
      viejos. La app no se muestra dentro de ningun iframe (chequeado: no hay
      un solo <iframe> en los templates), asi que DENY y no SAMEORIGIN.

    - form-action 'self' es la que evita que un XSS te mueva el <form> del
      login a otro dominio; base-uri 'self', que te cambie a donde resuelven
      todas las rutas relativas con un <base> inyectado.
    """
    directivas = [
        # Todo lo que no tenga su propia linea sale de la app y de nadie mas.
        "default-src 'self'",
        f"script-src 'self' 'nonce-{nonce}' {CDN_MAPA}",
        f"style-src 'self' 'unsafe-inline' {CSS_TIPOGRAFIAS} {CDN_MAPA}",
        f"font-src 'self' {ARCHIVOS_TIPOGRAFIAS} data:",
        # data: son los placeholders inline; blob:, el canvas del mapa.
        f"img-src 'self' data: blob: {TILES_MAPA}",
        f"connect-src 'self' {TILES_MAPA}",
        "worker-src blob:",
        "object-src 'none'",
        "base-uri 'self'",
        "form-action 'self'",
        "frame-ancestors 'none'",
    ]
    return "; ".join(directivas)


# Las que no dependen del request y siempre valen lo mismo.
CABECERAS_FIJAS = {
    # Sin esto el navegador adivina el tipo de un archivo por su contenido:
    # una imagen subida que "parece" HTML o JavaScript se termina ejecutando
    # como tal. La app sirve archivos que suben los usuarios, asi que aplica.
    "X-Content-Type-Options": "nosniff",
    # Clickjacking: nadie mete la app en un iframe para robarse un click.
    "X-Frame-Options": "DENY",
    # Al salir a otro dominio se manda el origen y no la URL entera: los
    # perfiles y las fichas llevan slug y a veces id en la ruta, y hoy eso
    # viaja en el Referer de cada link a Instagram o WhatsApp.
    "Referrer-Policy": "strict-origin-when-cross-origin",
}

# EL Server NO SE TOCA DESDE ACA, Y SE PROBO. El escaneo lo anoto como
# cosmetico (delata "Werkzeug/3.1.3 Python/3.14.4"), asi que se intento pisarlo
# con un `"Server": "Impulsar"` en el diccionario de arriba. No funciona: el
# que arma esa linea no es Flask sino el servidor HTTP, y el de desarrollo la
# escribe SIEMPRE, con lo cual la respuesta salia con las dos, la que delata
# primero. Peor que antes.
#
# Es una cabecera de la capa que habla HTTP, no de la app, y ahi es donde se
# apaga: `server_tokens off` en nginx, o el flag equivalente del WSGI que se
# use. Queda anotado en el backlog de docs/CONTEXTO.md.
