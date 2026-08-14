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

# Tiene que coincidir con el largo de User.slug (models/user.py): si un slug se
# pasa, MySQL lo trunca en silencio y dos usuarios distintos pueden terminar
# con el mismo valor, justo lo que el unique intenta evitar.
LARGO_MAXIMO_SLUG = 60

# Slugs que no se le pueden dar a nadie.
#
# Los que importan de verdad hoy son "edit" y "create_bio": son rutas estaticas
# bajo /perfil/, y Werkzeug les da prioridad sobre /perfil/<slug>, asi que un
# usuario con ese slug quedaria con el perfil inaccesible (y peor: entrando a
# su propia URL veria el formulario de edicion).
#
# El resto no colisiona hoy porque el perfil vive bajo /perfil/, pero se
# reservan igual: son nombres que una cuenta no deberia poder ocupar por si el
# dia de mañana el perfil pasa a colgar de la raiz, y ademas evitan que alguien
# se registre como "admin" o "soporte" para hacerse pasar por el sitio.
SLUGS_RESERVADOS = frozenset({
    # rutas reales bajo /perfil/ (ver views/profile.py). Cada vez que se suma
    # una ruta estatica ahi hay que sumarla aca: Werkzeug le da prioridad sobre
    # /perfil/<slug>, asi que el usuario que se llame igual queda sin perfil.
    "edit", "create_bio", "horarios",
    # sub-rutas de /perfil/<slug>/: no tapan un slug, se reservan por prolijidad
    "resenias", "seguir",
    # prefijos de blueprint y rutas de primer nivel de la app
    "admin", "api", "static", "auth", "blog", "mensajes", "perfil",
    "login", "logout", "register", "registro", "me",
    "sobre", "contacto", "terminos", "privacidad",
    "favoritos", "mis-emprendimientos", "eventos",
    # nombres institucionales, para que no se los pueda usurpar
    "impulsar", "soporte", "ayuda", "root", "administrador",
})


def generar_slug(texto):
    """Convierte un username en un slug URL-safe: minusculas, sin tildes, con guiones."""
    texto = (texto or "").strip()
    # NFKD separa la letra de su acento y el encode a ASCII descarta el acento
    # suelto: "Panadería" -> "Panaderia".
    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    texto = texto.lower()
    texto = re.sub(r"[^a-z0-9]+", "-", texto).strip("-")
    return _recortar(texto) or SLUG_POR_DEFECTO


def _recortar(texto, largo=LARGO_MAXIMO_SLUG):
    """Corta a `largo` sin dejar un guion colgando al final."""
    return texto[:largo].rstrip("-")


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
        base = _recortar(f"{SLUG_POR_DEFECTO}-{base}")

    # Un slug reservado se trata igual que uno ya ocupado: se cae al sufijo
    # numerico ("edit" -> "edit-2"), que no choca con ninguna ruta.
    if base in SLUGS_RESERVADOS:
        return _con_sufijo_libre(base, esta_tomado)

    if not esta_tomado(base):
        return base

    return _con_sufijo_libre(base, esta_tomado)


def _con_sufijo_libre(base, esta_tomado):
    """Primer "base-N" (N desde 2) que no este ni ocupado ni reservado.

    La base se recorta dejandole lugar al sufijo ANTES de concatenar, y no
    despues: cortar el resultado ya armado se come justamente el "-N", que es
    lo unico que distingue un slug del otro, y devolveria un valor repetido.
    """
    sufijo = 2
    while True:
        # El hueco se recalcula en cada vuelta porque el sufijo crece de largo
        # al pasar de -9 a -10.
        cola = f"-{sufijo}"
        candidato = _recortar(base, LARGO_MAXIMO_SLUG - len(cola)) + cola
        if candidato not in SLUGS_RESERVADOS and not esta_tomado(candidato):
            return candidato
        sufijo += 1
