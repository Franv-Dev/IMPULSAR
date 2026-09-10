"""Renderizado seguro y minimo de texto con formato (la bio del usuario).

No es Markdown completo, es a proposito muy chico: solo saltos de linea,
**negrita** y [texto](url). El texto se escapa PRIMERO y las etiquetas se
arman a mano despues sobre el resultado ya escapado, asi que no hay forma de
que el usuario inyecte HTML o JS via la bio (un <script> literal en el texto
queda como texto escapado, nunca como una etiqueta real).
"""

import re

from markupsafe import Markup, escape

from db import utcnow

# Solo linkea si el texto ya escapado arranca con http(s)://: bloquea
# esquemas como javascript: sin necesidad de una lista negra.
_LINK = re.compile(r"\[([^\]]+)\]\((https?://[^\s)]+)\)")
_BOLD = re.compile(r"\*\*(.+?)\*\*")


def render_biography(texto):
    """Convierte texto plano con **negrita**, [links](url) y saltos de linea
    a HTML seguro. Devuelve un Markup: se puede usar en el template sin
    pasar por |safe (que si dejaria pasar HTML crudo)."""
    if not texto:
        return Markup("")

    resultado = str(escape(texto))
    resultado = _LINK.sub(
        r'<a href="\2" target="_blank" rel="noopener noreferrer nofollow">\1</a>',
        resultado,
    )
    resultado = _BOLD.sub(r"<strong>\1</strong>", resultado)
    resultado = resultado.replace("\n", "<br>")

    return Markup(resultado)


def tiempo_relativo(momento, ahora=None):
    """"hace 2 semanas", "hace 3 meses", "recién". Para fechar una reseña.

    La ficha del emprendimiento fecha las reseñas así y no con la fecha exacta:
    lo que se quiere saber leyendo una reseña es si es de esta temporada o de
    hace dos años, no el día. La fecha completa sigue estando en el `title` del
    elemento, para quien la necesite.

    `momento` es un datetime naive en UTC, que es como db.utcnow() guarda todas
    las columnas DateTime del proyecto. `ahora` entra por parámetro para que un
    test pueda fijarlo; por defecto es utcnow(), la misma referencia con la que
    se escribió el dato.

    Los tramos son groseros a propósito: en cuanto pasa de un día, el número
    exacto de días deja de importar y sólo estorba. Un momento en el futuro
    (relojes desfasados entre el servidor y la base) cae en "recién" y no en un
    "hace -3 minutos".
    """
    if momento is None:
        return ""

    ahora = ahora or utcnow()
    segundos = (ahora - momento).total_seconds()

    if segundos < 60:
        return "recién"

    minutos = int(segundos // 60)
    if minutos < 60:
        return f"hace {minutos} minuto{'' if minutos == 1 else 's'}"

    horas = minutos // 60
    if horas < 24:
        return f"hace {horas} hora{'' if horas == 1 else 's'}"

    dias = horas // 24
    if dias == 1:
        return "ayer"
    if dias < 7:
        return f"hace {dias} días"

    semanas = dias // 7
    if semanas < 5:
        return f"hace {semanas} semana{'' if semanas == 1 else 's'}"

    meses = dias // 30
    if meses < 12:
        return f"hace {meses} mes{'' if meses == 1 else 'es'}"

    anios = dias // 365
    return f"hace {anios} año{'' if anios == 1 else 's'}"
