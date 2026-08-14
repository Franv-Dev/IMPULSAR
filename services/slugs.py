"""Generacion de slugs de usuario para las URLs de perfil.

El slug es lo que viaja en /perfil/<slug>, separado del username: el username
sigue siendo libre (mayusculas, tildes, espacios) y el slug es su version
segura para una URL. Tenerlos separados evita tener que restringir como se
llama la gente para que la ruta funcione.
"""

import re
import unicodedata

# Fallback para un username que no deja ningun caracter usable (por ejemplo
# uno escrito entero en un alfabeto que se pierde al normalizar).
SLUG_POR_DEFECTO = "usuario"


def generar_slug(texto):
    """Convierte un username en un slug URL-safe: minusculas, sin tildes, con guiones."""
    texto = (texto or "").strip()
    # NFKD separa la letra de su acento y el encode a ASCII descarta el acento
    # suelto: "Panadería" -> "Panaderia".
    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    texto = texto.lower()
    texto = re.sub(r"[^a-z0-9]+", "-", texto).strip("-")
    return texto or SLUG_POR_DEFECTO


def slug_disponible(base, esta_tomado):
    """Devuelve el primer slug libre a partir de `base`, agregando -2, -3, etc.

    `esta_tomado` es una funcion que recibe un slug y dice si ya existe. Se
    pasa como parametro para poder usar esto tanto desde la app (consultando
    la base) como desde la migracion (que trabaja con SQL crudo).
    """
    # Un slug 100% numerico chocaria con /perfil/<id>: "123" no se sabria si es
    # el usuario con id 123 o el que se llama "123". El registro ya rechaza
    # esos usernames, pero la migracion normaliza datos viejos que no pasaron
    # por esa validacion.
    if base.isdigit():
        base = f"{SLUG_POR_DEFECTO}-{base}"

    if not esta_tomado(base):
        return base

    sufijo = 2
    while esta_tomado(f"{base}-{sufijo}"):
        sufijo += 1
    return f"{base}-{sufijo}"
