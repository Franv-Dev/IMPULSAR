"""Parseo y validacion de lo que manda el navegador.

Es la frontera entre el formulario HTML y el resto del dominio: de aca para
adentro nadie vuelve a tocar request.form. La validacion es a mano (una
variable `error` con el mensaje listo para mostrar) porque asi valida todo el
proyecto: Flask-WTF esta instalado pero solo se usa para el CSRF.
"""

from flask import request

from app.personal.reglas import (
    MAX_CONTACTO,
    MAX_DESCRIPCION,
    MAX_DISPONIBILIDAD,
    MAX_EXPERIENCIA,
    MAX_NOMBRE,
    MAX_PUESTO,
    modalidad_valida,
)
from services.validation import validar_largo


def leer_busqueda():
    """Los campos del aviso de busqueda, tal como los mando el emprendedor.

    Devuelve (datos, error): `datos` es lo que hay que devolverle al template
    para repintar el formulario, y `error` el primer mensaje que corta, o None.
    """
    puesto = (request.form.get("puesto") or "").strip()
    modalidad = (request.form.get("modalidad") or "").strip()
    descripcion = (request.form.get("descripcion") or "").strip()

    # El primero de los dos textos que no entra en su columna, si hay alguno.
    # HACE FALTA ANTES DEL INSERT: MySQL trunca o falla segun el sql_mode, asi
    # que sin esto el aviso o se guarda cortado a la mitad sin avisar, o muere
    # con un DataError que el usuario ve como un 500. SQLite guarda el texto
    # entero se pase o no, que es por lo que esto se cuela sin que los tests
    # digan nada si no se escriben a proposito (B1).
    muy_largo = (
        validar_largo(puesto, MAX_PUESTO, "El puesto")
        or validar_largo(descripcion, MAX_DESCRIPCION, "La descripción")
    )

    error = None
    if not puesto:
        error = "Decí qué puesto estás buscando."
    elif not descripcion:
        error = "Contá brevemente qué implica el puesto."
    elif muy_largo:
        error = muy_largo
    elif not modalidad_valida(modalidad):
        # La modalidad llega de un <select>, pero se valida igual: el POST se
        # puede mandar a mano con cualquier cosa.
        error = "Elegí una de las modalidades de la lista."

    datos = {"puesto": puesto, "modalidad": modalidad, "descripcion": descripcion}
    return datos, error


def leer_postulacion():
    """Lo que escribe quien se postula.

    Los cuatro campos son obligatorios: es un formulario corto y cada uno es
    una de las cuatro cosas que el emprendedor necesita para decidir si abre el
    chat. Uno vacio no es "menos informacion", es una postulacion que no se
    puede leer.
    """
    nombre = (request.form.get("nombre") or "").strip()
    contacto = (request.form.get("contacto") or "").strip()
    experiencia = (request.form.get("experiencia") or "").strip()
    disponibilidad = (request.form.get("disponibilidad") or "").strip()

    muy_largo = (
        validar_largo(nombre, MAX_NOMBRE, "El nombre")
        or validar_largo(contacto, MAX_CONTACTO, "El contacto")
        or validar_largo(experiencia, MAX_EXPERIENCIA, "La experiencia")
        or validar_largo(disponibilidad, MAX_DISPONIBILIDAD, "La disponibilidad")
    )

    error = None
    if not nombre:
        error = "Escribí tu nombre."
    elif not contacto:
        error = "Dejá un contacto para que te puedan responder."
    elif not experiencia:
        error = "Contá brevemente tu experiencia."
    elif not disponibilidad:
        error = "Indicá tu disponibilidad."
    elif muy_largo:
        error = muy_largo

    datos = {
        "nombre": nombre, "contacto": contacto,
        "experiencia": experiencia, "disponibilidad": disponibilidad,
    }
    return datos, error
