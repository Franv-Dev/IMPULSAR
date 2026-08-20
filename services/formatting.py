"""Renderizado seguro y minimo de texto con formato (la bio del usuario).

No es Markdown completo, es a proposito muy chico: solo saltos de linea,
**negrita** y [texto](url). El texto se escapa PRIMERO y las etiquetas se
arman a mano despues sobre el resultado ya escapado, asi que no hay forma de
que el usuario inyecte HTML o JS via la bio (un <script> literal en el texto
queda como texto escapado, nunca como una etiqueta real).
"""

import re

from markupsafe import Markup, escape

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
