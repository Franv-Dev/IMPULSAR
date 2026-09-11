"""Parseo y validacion de lo que manda el navegador.

Es la frontera entre el formulario HTML y el resto del dominio: de aca para
adentro nadie vuelve a tocar request.form. La validacion es a mano (una
variable `error` con el mensaje listo para mostrar) porque asi valida todo el
proyecto: Flask-WTF esta instalado pero solo se usa para el CSRF.
"""

from datetime import date

from flask import request

from app.oportunidades.reglas import (
    MAX_DESCRIPCION,
    MAX_MENSAJE,
    MAX_PLAZO,
    MAX_TITULO,
)
from services.precios import parsear_precio
from services.validation import validar_largo


def _leer_fecha(texto):
    """Un <input type=date> a date, o (None, error).

    Llega en ISO (aaaa-mm-dd) porque asi lo manda el navegador, pero se parsea
    con cuidado igual: el POST se escribe a mano y una fecha invalida no puede
    terminar en un ValueError sin atajar.
    """
    texto = (texto or "").strip()
    if not texto:
        return None, None
    try:
        return date.fromisoformat(texto), None
    except ValueError:
        return None, "Esa fecha no es válida."


def leer_oportunidad(hoy):
    """Los campos de la oportunidad, tal como los mando quien la publica.

    Devuelve (datos, error): `datos` es lo que hay que devolverle al template
    para repintar el formulario, y `error` el primer mensaje que corta, o None.

    `hoy` se recibe y no se calcula acá: la fecha del proyecto es la de
    Argentina (services/eventos.hoy_en_argentina) y la decide la vista, que es
    la que sabe en que zona vive el usuario. Ademas lo hace testeable sin
    tocar el reloj.
    """
    titulo = (request.form.get("titulo") or "").strip()
    descripcion = (request.form.get("descripcion") or "").strip()
    presupuesto_texto = (request.form.get("presupuesto") or "").strip()
    fecha_texto = (request.form.get("fecha_limite") or "").strip()

    # El presupuesto es opcional: obligatorio=False hace que el vacio devuelva
    # (None, None) en vez de un error. "No se cuanto sale" es justamente por lo
    # que alguien pregunta.
    presupuesto, error_precio = parsear_precio(presupuesto_texto, obligatorio=False)
    fecha_limite, error_fecha = _leer_fecha(fecha_texto)

    # El primero de los dos textos que no entra en su columna, si hay alguno.
    # HACE FALTA ANTES DEL INSERT: MySQL trunca o falla segun el sql_mode, asi
    # que sin esto la oportunidad o se guarda cortada a la mitad sin avisar, o
    # muere con un DataError que el usuario ve como un 500. SQLite guarda el
    # texto entero se pase o no, que es por lo que esto se cuela sin que los
    # tests digan nada si no se escriben a proposito (B1).
    muy_largo = (
        validar_largo(titulo, MAX_TITULO, "El título")
        or validar_largo(descripcion, MAX_DESCRIPCION, "La descripción")
    )

    error = None
    if not titulo:
        error = "Decí en una línea qué necesitás."
    elif not descripcion:
        error = "Contá un poco más para que te puedan presupuestar."
    elif muy_largo:
        error = muy_largo
    elif error_precio:
        error = error_precio
    elif error_fecha:
        error = error_fecha
    elif fecha_limite is not None and fecha_limite < hoy:
        # Una fecha limite ya pasada no es un dato, es un error de tipeo: nadie
        # publica hoy algo que necesitaba la semana pasada.
        error = "Esa fecha ya pasó. Poné para cuándo lo necesitás."

    datos = {
        "titulo": titulo,
        "descripcion": descripcion,
        # Se devuelve el TEXTO y no el Decimal para repintar: si escribio
        # "1.500,50" tiene que volver a ver eso, no "1500.50".
        "presupuesto": presupuesto_texto,
        "fecha_limite": fecha_texto,
    }
    return datos, error, presupuesto, fecha_limite


def leer_propuesta():
    """Lo que ofrece el emprendedor: precio, plazo y mensaje.

    Los tres son obligatorios. El precio y el plazo porque sin ellos la
    propuesta no se puede comparar con las otras, que es lo unico que la
    pantalla del publicador tiene que hacer; el mensaje porque dos numeros
    sueltos no dicen por que elegir a este y no al otro.

    Devuelve (datos, error, precio, plazo_dias).
    """
    precio_texto = (request.form.get("precio") or "").strip()
    plazo_texto = (request.form.get("plazo_dias") or "").strip()
    mensaje = (request.form.get("mensaje") or "").strip()

    precio, error_precio = parsear_precio(precio_texto, obligatorio=True)

    plazo_dias = None
    error_plazo = None
    if not plazo_texto:
        error_plazo = "Decí en cuántos días lo podés entregar."
    else:
        try:
            plazo_dias = int(plazo_texto)
        except ValueError:
            # El input es type=number, pero el POST se manda a mano.
            error_plazo = "El plazo tiene que ser un número de días."
        else:
            if plazo_dias <= 0:
                error_plazo = "El plazo tiene que ser de al menos un día."
            elif plazo_dias > MAX_PLAZO:
                error_plazo = (
                    f"El plazo no puede ser mayor a {MAX_PLAZO} días."
                )

    muy_largo = validar_largo(mensaje, MAX_MENSAJE, "El mensaje")

    error = None
    if error_precio:
        error = error_precio
    elif error_plazo:
        error = error_plazo
    elif not mensaje:
        error = "Contá brevemente cómo lo harías."
    elif muy_largo:
        error = muy_largo

    datos = {
        "precio": precio_texto,
        "plazo_dias": plazo_texto,
        "mensaje": mensaje,
    }
    return datos, error, precio, plazo_dias
