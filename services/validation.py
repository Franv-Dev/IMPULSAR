"""Reglas de validacion compartidas entre el registro por formulario y por API.

Antes el minimo de largo (o la ausencia de uno) vivia por separado en
views.auth.register() y en api_register(). Si se queria subir el minimo o
sumar una lista de contraseñas obvias, habia que acordarse de tocar los dos
lugares.
"""

import re
import unicodedata

MIN_PASSWORD_LENGTH = 8

# Tiene que coincidir con el largo de User.username (models/user.py). Sin este
# chequeo el nombre largo llegaba al INSERT y MySQL cortaba con un DataError
# que nadie atrapaba: el usuario veia un 500 en vez de un error del formulario.
MAX_USERNAME_LENGTH = 50

# Tiene que coincidir con el largo de User.email. Mismo caso que el username:
# sin el chequeo, una direccion larga llega al INSERT y MySQL corta o falla
# segun el sql_mode, y el usuario ve un 500 en vez de un error del formulario.
# Se repite el numero en vez de leerlo de la columna porque models/user.py
# importa este modulo, y al reves seria un import circular.
MAX_EMAIL_LENGTH = 120

# Un email con la forma minima: algo, una arroba, un dominio con al menos un
# punto y una extension.
#
# A proposito NO es una validacion exhaustiva del RFC 5322, que acepta cosas
# que ningun formulario ve nunca (comentarios entre parentesis, comillas,
# direcciones IP literales) y que en la practica siempre se escribe mal. La
# unica forma de saber que un email existe es mandarle un mail; esto filtra la
# basura obvia ("tomy", "tomy@", "a@b") y deja pasar todo lo demas.
_EMAIL = re.compile(r"[^@\s]+@[^@\s.]+(?:\.[^@\s.]+)+")

# Los separadores que se escriben de verdad en un telefono: el prefijo
# internacional, parentesis del codigo de area, guiones, puntos, barras y
# espacios. Cualquier otra cosa es basura o un intento de meter texto.
_TELEFONO = re.compile(r"\+?[0-9()\-./ ]+")

# Cuantos digitos tiene que tener para ser un numero y no un tipeo. El minimo
# es un fijo local sin codigo de area (en Mendoza, 4xx-xxxx son 7, y hay
# lugares con 6); el maximo es el de E.164, el estandar internacional, asi que
# nada real lo pasa.
MIN_TELEFONO_DIGITOS = 6
MAX_TELEFONO_DIGITOS = 15

# Tiene que coincidir con el largo de User.phone y User.whatsapp, por lo mismo
# que MAX_EMAIL_LENGTH. Un numero de 15 digitos con separadores entra comodo.
MAX_TELEFONO_LENGTH = 30

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


def validate_email(email):
    """Devuelve un mensaje de error si el email no es valido, o None.

    Se valida la FORMA, no la existencia: la unica manera de saber que una
    direccion existe es mandarle un mail y esperar que la abran, y este
    proyecto no manda mails. Con esto alcanza para que no se registre alguien
    con "tomy" o "tomy@" y despues no haya como contactarlo.
    """
    email = (email or "").strip()
    if not email:
        return "Se requiere un email"
    if len(email) > MAX_EMAIL_LENGTH:
        return f"El email no puede tener más de {MAX_EMAIL_LENGTH} caracteres."
    if not _EMAIL.fullmatch(email):
        return "Ese email no parece válido. Revisá que tenga la forma nombre@dominio.com."
    return None


def validate_telefono(telefono, etiqueta="teléfono"):
    """Devuelve un mensaje de error si el telefono no es valido, o None.

    Vale para phone y para whatsapp, que son la misma clase de dato; `etiqueta`
    es solo para que el mensaje nombre el campo que el usuario esta mirando.

    Vacio NO es un error: los dos campos son opcionales (no todo el mundo
    quiere publicar su telefono), y quien los borra los esta dejando en blanco
    a proposito. Quien quiera exigirlos que lo haga en su formulario.

    Se acepta el numero como se escribe de verdad, con separadores ("+54 9 261
    123-4567"), y se cuentan solo los digitos para el largo. No se normaliza a
    E.164 ni se guarda distinto de como se escribio: el telefono se muestra tal
    cual y todavia no hay nada que lo consuma como dato.
    """
    telefono = (telefono or "").strip()
    if not telefono:
        return None
    if len(telefono) > MAX_TELEFONO_LENGTH:
        return (
            f"El {etiqueta} no puede tener más de {MAX_TELEFONO_LENGTH} "
            "caracteres."
        )
    if not _TELEFONO.fullmatch(telefono):
        return (
            f"El {etiqueta} solo puede tener números y los separadores "
            "habituales (+, espacios, guiones y paréntesis)."
        )

    digitos = sum(1 for caracter in telefono if caracter.isdigit())
    if not MIN_TELEFONO_DIGITOS <= digitos <= MAX_TELEFONO_DIGITOS:
        return (
            f"Ese {etiqueta} no parece un número: tiene que tener entre "
            f"{MIN_TELEFONO_DIGITOS} y {MAX_TELEFONO_DIGITOS} dígitos."
        )
    return None
