"""Reglas de validacion compartidas entre el registro por formulario y por API.

Antes el minimo de largo (o la ausencia de uno) vivia por separado en
views.auth.register() y en api_register(). Si se queria subir el minimo o
sumar una lista de contraseñas obvias, habia que acordarse de tocar los dos
lugares.
"""

MIN_PASSWORD_LENGTH = 8

# Contraseñas comunes que pasan el chequeo de largo pero siguen siendo
# triviales de adivinar.
CONTRASENIAS_OBVIAS = {
    "12345678", "123456789", "1234567890", "87654321",
    "password", "password1", "contraseña", "contrasena",
    "qwertyui", "asdfghjk", "11111111", "00000000",
    "admin123", "admin1234", "iloveyou1", "letmein12",
}


def validate_password(password):
    """Devuelve un mensaje de error si la contraseña no es valida, o None."""
    if not password or len(password) < MIN_PASSWORD_LENGTH:
        return f"La contraseña debe tener al menos {MIN_PASSWORD_LENGTH} caracteres."
    if password.lower() in CONTRASENIAS_OBVIAS:
        return "Esa contraseña es demasiado común, elegí una más segura."
    return None
