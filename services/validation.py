"""Reglas de validacion compartidas entre el registro por formulario y por API.

Antes el minimo de largo (o la ausencia de uno) vivia por separado en
views.auth.register() y en api_register(). Si se queria subir el minimo o
sumar una lista de contraseñas obvias, habia que acordarse de tocar los dos
lugares.
"""

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
