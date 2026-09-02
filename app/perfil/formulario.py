"""Parseo y validacion de lo que manda el navegador.

Es la frontera entre el formulario HTML y el resto del dominio: de aca para
adentro nadie vuelve a tocar request.form. La validacion es a mano (una
variable `error` con el mensaje listo para mostrar) porque asi valida todo el
proyecto: Flask-WTF esta instalado pero solo se usa para el CSRF.
"""

from flask import request

from app.perfil.reglas import DURACION_MINIMA_MINUTOS
from services.validation import validate_telefono
from services.horarios import (
    DIAS, duracion_minutos, formatear as formatear_hora, parsear_hora,
)


def leer_bio():
    """La biografia sola, del formulario corto de /perfil/create_bio."""
    biografia = request.form.get("body", "").strip()
    error = None if biografia else "Se requiere una biografía."
    return biografia, error


def leer_perfil():
    """Los campos del perfil completo, ya limpios: (datos, error).

    Ojo con dos que se parecen y no son lo mismo: `location` es texto libre que
    solo se muestra, y `address_street` es la direccion que se geocodifica.

    De los ocho campos, los dos telefonos son los unicos que se validan, y no
    por capricho: son datos de CONTACTO, o sea que existen para que alguien los
    marque. Un telefono con letras o con cuatro digitos no falla en ningun
    lado, se publica en el perfil y el cliente que lo intente no llega a
    nadie. Los tres links y los dos textos libres se guardan como vengan, que
    es como venia funcionando.
    """
    datos = {
        "biography": request.form.get("biography", "").strip(),
        "location": request.form.get("location", "").strip(),
        "address_street": request.form.get("address_street", "").strip(),
        "phone": request.form.get("phone", "").strip(),
        "whatsapp": request.form.get("whatsapp", "").strip(),
        "instagram_url": request.form.get("instagram_url", "").strip(),
        "facebook_url": request.form.get("facebook_url", "").strip(),
        "twitter_url": request.form.get("twitter_url", "").strip(),
    }

    error = (
        validate_telefono(datos["phone"])
        or validate_telefono(datos["whatsapp"], etiqueta="WhatsApp")
    )

    return datos, error


def campos_guardados(user):
    """Los ocho campos del perfil tal como estan guardados hoy.

    La contraparte de leer_perfil(), y la razon de que exista es la misma que
    la de filas_guardadas() en los horarios: el template se pinta SIEMPRE desde
    un dict con estas ocho claves, venga de la base (al entrar) o del POST (al
    volver por un error). Si el GET leyera user.* y el error leyera el POST,
    serian dos formas de armar la misma pantalla y una de las dos se iba a
    quedar atras.
    """
    return {
        "biography": user.biography or "",
        "location": user.location or "",
        "address_street": user.address_street or "",
        "phone": user.phone or "",
        "whatsapp": user.whatsapp or "",
        "instagram_url": user.instagram_url or "",
        "facebook_url": user.facebook_url or "",
        "twitter_url": user.twitter_url or "",
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

    Se reporta el PRIMER error y no el ultimo: antes cada dia pisaba el mensaje
    del anterior, asi que con dos dias mal cargados se veia el del ultimo y el
    usuario corregia ese, mandaba, y le aparecia el otro.
    """
    error = None
    pendientes = []
    for dia, etiqueta in DIAS:
        cerrado = request.form.get(f"cerrado_{dia}") == "on"
        abre = parsear_hora(request.form.get(f"abre_{dia}"))
        cierra = parsear_hora(request.form.get(f"cierra_{dia}"))

        if error is None and not cerrado:
            if (abre is None) != (cierra is None):
                error = (
                    f"{etiqueta}: cargá la hora de apertura y la de cierre, o "
                    "marcá el día como cerrado."
                )
            elif abre and cierra:
                error = _error_de_rango(etiqueta, abre, cierra)

        pendientes.append((dia, etiqueta, cerrado, abre, cierra))

    return pendientes, error


def _error_de_rango(etiqueta, abre, cierra):
    """El mensaje si ese rango de atencion no tiene sentido, o None.

    El rango se lee como lo lee services/horarios: si `cierra` es menor que
    `abre`, el cierre es del dia siguiente (un bar de 20:00 a 02:00). Por eso
    NO se pide que la apertura sea anterior al cierre: eso rechazaria todos los
    horarios nocturnos, que son validos y que el resto del proyecto ya
    contempla (esta_abierto y el filtro "Abierto ahora" del listado).

    Lo que si se puede pedir son las dos cosas que no dependen de si cruza
    medianoche:

    - que las dos horas no sean la misma, que es el caso ambiguo: nadie sabe si
      "de 09:00 a 09:00" es cerrado siempre o abierto las 24 horas, y hoy los
      dos lectores del horario lo toman como cerrado, sin avisar. El mensaje
      dice como escribir el dia completo, que es lo que casi siempre se quiso.
    - que el rango no sea absurdamente corto. Con el cruce de medianoche, un
      "de 18:00 a 09:00" es un rango largo y valido, pero un "de 09:00 a 09:05"
      son cinco minutos de atencion: es un error de tipeo en los minutos, y sin
      esto se guardaba y dejaba el negocio cerrado casi todo el dia sin que
      nadie se enterara.

    Lo que queda afuera, y no por olvido: el caso inverso, alguien que quiso
    poner "de 09:00 a 18:00" y escribio "de 18:00 a 09:00". Es indistinguible
    de un horario nocturno legitimo, asi que rechazarlo seria romper el caso
    real para atajar un typo.
    """
    if abre == cierra:
        return (
            f"{etiqueta}: la hora de apertura y la de cierre no pueden ser "
            "iguales. Si atendés todo el día, cargá de 00:00 a 23:59."
        )

    duracion = duracion_minutos(abre, cierra)
    if duracion < DURACION_MINIMA_MINUTOS:
        return (
            f"{etiqueta}: de {formatear_hora(abre)} a {formatear_hora(cierra)} "
            f"son {duracion} minutos de atención. Revisá las horas."
        )

    return None
