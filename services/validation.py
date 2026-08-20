"""Reglas de validacion compartidas entre el registro por formulario y por API.

Antes el minimo de largo (o la ausencia de uno) vivia por separado en
views.auth.register() y en api_register(). Si se queria subir el minimo o
sumar una lista de contraseñas obvias, habia que acordarse de tocar los dos
lugares.
"""

import unicodedata

MIN_PASSWORD_LENGTH = 8

# Tiene que coincidir con el largo de User.username (models/user.py). Sin este
# chequeo el nombre largo llegaba al INSERT y MySQL cortaba con un DataError
# que nadie atrapaba: el usuario veia un 500 en vez de un error del formulario.
MAX_USERNAME_LENGTH = 50

# Contraseñas comunes que pasan el chequeo de largo pero siguen siendo
# triviales de adivinar.
CONTRASENIAS_OBVIAS = {
    "12345678", "123456789", "1234567890", "87654321",
    "password", "password1", "contraseña", "contrasena",
    "qwertyui", "asdfghjk", "11111111", "00000000",
    "admin123", "admin1234", "iloveyou1", "letmein12",
}


def normalizar_username(username):
    """Forma canonica para comparar dos usernames como los compara la base.

    El unique de users.username vive en MySQL con utf8mb4_unicode_ci, que
    ignora mayusculas y tildes: para la base "Panadería" y "panaderia" son el
    mismo nombre. Sin normalizar antes de chequear disponibilidad, el registro
    creia que estaba libre y el choque recien saltaba como IntegrityError.

    Se replica lo que hace esa collation y nada mas:
      - casefold primero (ademas de las mayusculas resuelve "ß" -> "ss")
      - despues se sacan los acentos descomponiendo y tirando las marcas

    Se descartan solo las marcas de acento y no todo lo no-ASCII: con
    encode("ascii") dos nombres en cirilico quedarian los dos vacios y se
    tomarian por iguales, cuando para MySQL son distintos.

    Los espacios internos y la puntuacion se dejan como estan, porque la
    collation tampoco los ignora ("a b" != "a  b" y "a-b" != "a b").
    """
    texto = (username or "").strip().casefold()
    descompuesto = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in descompuesto if not unicodedata.combining(c))


def validate_username(username):
    """Devuelve un mensaje de error si el username no es valido, o None."""
    username = (username or "").strip()
    if not username:
        return "Se requiere nombre de usuario"
    # Un username 100% numerico generaria un slug numerico, y /perfil/123 ya
    # significa "el usuario con id 123": no habria forma de saber a cual de
    # los dos apunta la URL.
    if username.isdigit():
        return "El nombre de usuario no puede ser solo números."
    if len(username) > MAX_USERNAME_LENGTH:
        return (
            f"El nombre de usuario no puede tener más de {MAX_USERNAME_LENGTH} "
            "caracteres."
        )
    return None


def validate_password(password):
    """Devuelve un mensaje de error si la contraseña no es valida, o None."""
    if not password or len(password) < MIN_PASSWORD_LENGTH:
        return f"La contraseña debe tener al menos {MIN_PASSWORD_LENGTH} caracteres."
    if password.lower() in CONTRASENIAS_OBVIAS:
        return "Esa contraseña es demasiado común, elegí una más segura."
    return None
