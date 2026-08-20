"""Parseo y validacion de lo que manda el navegador.

Es la frontera entre el formulario HTML y el resto del dominio: de aca para
adentro nadie vuelve a tocar request.form. La validacion es a mano (una
variable `error` con el mensaje listo para mostrar) porque asi valida todo el
proyecto: Flask-WTF esta instalado pero solo se usa para el CSRF.
"""

from flask import request

from services.horarios import DIAS, formatear as formatear_hora, parsear_hora


def leer_bio():
    """La biografia sola, del formulario corto de /perfil/create_bio."""
    biografia = request.form.get("body", "").strip()
    error = None if biografia else "Se requiere una biografía."
    return biografia, error


def leer_perfil():
    """Los campos del perfil completo, ya limpios.

    Ojo con dos que se parecen y no son lo mismo: `location` es texto libre que
    solo se muestra, y `address_street` es la direccion que se geocodifica.
    """
    return {
        "biography": request.form.get("biography", "").strip(),
        "location": request.form.get("location", "").strip(),
        "address_street": request.form.get("address_street", "").strip(),
        "phone": request.form.get("phone", "").strip(),
        "whatsapp": request.form.get("whatsapp", "").strip(),
        "instagram_url": request.form.get("instagram_url", "").strip(),
        "facebook_url": request.form.get("facebook_url", "").strip(),
        "twitter_url": request.form.get("twitter_url", "").strip(),
    }


def fila_de_horario(dia, etiqueta, cerrado, abre, cierra):
    """Una linea del formulario de horarios, con las horas ya como texto "HH:MM"."""
    return {
        "dia": dia, "etiqueta": etiqueta, "cerrado": cerrado,
        "abre": formatear_hora(abre), "cierra": formatear_hora(cierra),
    }


def filas_guardadas(existentes):
    """Las siete filas del formulario tal como estan guardadas hoy."""
    return [
        fila_de_horario(
            dia, etiqueta,
            existentes[dia].cerrado if dia in existentes else False,
            existentes[dia].abre if dia in existentes else None,
            existentes[dia].cierra if dia in existentes else None,
        )
        for dia, etiqueta in DIAS
    ]


def leer_horarios():
    """Los siete dias del panel de horarios: (pendientes, error).

    `pendientes` son tuplas (dia, etiqueta, cerrado, abre, cierra) con lo que
    mando el usuario, y se devuelven aunque haya error: perder el formulario
    entero por un dia mal cargado obliga a rehacer los siete.
    """
    error = None
    pendientes = []
    for dia, etiqueta in DIAS:
        cerrado = request.form.get(f"cerrado_{dia}") == "on"
        abre = parsear_hora(request.form.get(f"abre_{dia}"))
        cierra = parsear_hora(request.form.get(f"cierra_{dia}"))

        if not cerrado and (abre is None) != (cierra is None):
            error = (
                f"{etiqueta}: cargá la hora de apertura y la de cierre, o marcá "
                "el día como cerrado."
            )
        elif not cerrado and abre and cierra and abre == cierra:
            error = (
                f"{etiqueta}: la hora de apertura y la de cierre no pueden ser "
                "iguales."
            )

        pendientes.append((dia, etiqueta, cerrado, abre, cierra))

    return pendientes, error
