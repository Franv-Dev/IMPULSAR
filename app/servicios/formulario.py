"""Parseo y validacion de lo que manda el navegador.

Es la frontera entre el formulario HTML y el resto del dominio: de aca para
adentro nadie vuelve a tocar request.form. La validacion es a mano (una
variable `error` con el mensaje listo para mostrar) porque asi valida todo el
proyecto: Flask-WTF esta instalado pero solo se usa para el CSRF.
"""

from flask import request

from app.servicios.modelo import Rubros
from app.servicios.reglas import (
    MAX_DURACION_TURNO_MINUTOS,
    MIN_DURACION_TURNO_MINUTOS,
    duracion_de_turno_valida,
)
from services.precios import parsear_precio


def leer_servicio():
    """Los campos del servicio tal como los mando el usuario, ya parseados.

    Devuelve (datos, valores, error): `datos` es lo que hay que devolverle al
    template para repintar el formulario, `valores` lo que se guarda, y `error`
    el primer mensaje que corta, o None.
    """
    titulo = (request.form.get("titulo") or "").strip()
    rubro = (request.form.get("rubro") or "").strip()
    descripcion = (request.form.get("descripcion") or "").strip()
    zona = (request.form.get("zona_cobertura") or "").strip()
    precio_texto = (request.form.get("precio_estimado") or "").strip()
    # Un checkbox que no se marca directamente no viaja en el POST.
    disponible = request.form.get("disponible") is not None
    turnos_habilitados = request.form.get("turnos_habilitados") is not None
    duracion_texto = (request.form.get("duracion_turno_minutos") or "").strip()

    # obligatorio=False: un servicio sin precio es "a presupuestar", que es un
    # caso valido y no un formulario incompleto.
    precio, error_precio = parsear_precio(precio_texto, obligatorio=False)

    # int() a mano y no request.form.get(type=int), que devuelve None tanto
    # para "no vino" como para "vino 'tres'". Aca la diferencia importa: sin
    # turnos, vacio es lo normal; con turnos, hay que distinguir el campo en
    # blanco de un numero mal escrito para no decir "completá la duración"
    # cuando el usuario si la completo.
    duracion = None
    duracion_ilegible = False
    if duracion_texto:
        try:
            duracion = int(duracion_texto)
        except ValueError:
            duracion_ilegible = True

    error = None
    if not titulo:
        error = "Se requiere un título para el servicio."
    elif rubro not in Rubros.TODOS:
        # El rubro llega de un <select>, pero se valida igual: el POST se puede
        # mandar a mano con cualquier cosa, y un rubro invalido dejaria la fila
        # fuera de la busqueda por rubro sin que nadie se entere.
        error = "Elegí uno de los rubros de la lista."
    elif error_precio:
        error = error_precio
    elif turnos_habilitados and duracion_ilegible:
        error = "La duración del turno tiene que ser un número de minutos."
    elif not duracion_de_turno_valida(turnos_habilitados, duracion):
        # Un solo mensaje para "falta" y "esta fuera de rango": los dos se
        # arreglan escribiendo un numero del rango, asi que separarlos solo
        # agregaria una rama sin decirle nada nuevo al usuario.
        error = (
            "Si el servicio toma turnos, indicá cuánto dura cada uno "
            f"(entre {MIN_DURACION_TURNO_MINUTOS} y "
            f"{MAX_DURACION_TURNO_MINUTOS} minutos)."
        )

    # En `datos` va el texto crudo del precio y no el Decimal: si estaba mal
    # escrito, el formulario tiene que volver con lo que puso el usuario.
    datos = {
        "titulo": titulo, "rubro": rubro, "descripcion": descripcion,
        "zona_cobertura": zona, "precio_estimado": precio_texto,
        "disponible": disponible, "turnos_habilitados": turnos_habilitados,
        # Igual que el precio: el texto crudo, para que el formulario vuelva
        # con lo que el usuario escribio si estaba mal.
        "duracion_turno_minutos": duracion_texto,
    }
    valores = {
        "titulo": titulo, "rubro": rubro,
        "descripcion": descripcion or None, "zona_cobertura": zona or None,
        "precio_estimado": precio, "disponible": disponible,
        "turnos_habilitados": turnos_habilitados,
        # NULL cuando los turnos estan apagados, aunque el campo haya quedado
        # escrito: la columna solo significa algo con el flag prendido, y
        # dejarla con el valor viejo haria que apagar y volver a prender los
        # turnos reviva una duracion que el vendedor ya no eligio.
        "duracion_turno_minutos": duracion if turnos_habilitados else None,
    }
    return datos, valores, error


def leer_busqueda():
    """Los filtros de la busqueda publica, tal como vinieron en la URL.

    Devuelve (rubro, zona, solo_verificados, pagina). El rubro se devuelve
    aunque no exista: la consulta no filtra por el (eso lo decide
    reglas.rubro_valido), pero el formulario se repinta con lo que el usuario
    tenia, igual que hace el listado de emprendimientos con su categoria.

    solo_verificados se lee por presencia y no por valor, igual que el
    "disponible" de leer_servicio(): un checkbox destildado no manda nada, y
    tildado manda "on". Preguntar por el valor obligaria a decidir que hacer con
    "0", "false" y demas, que nadie manda desde este formulario.
    """
    return (
        (request.args.get("rubro") or "").strip(),
        (request.args.get("zona") or "").strip(),
        request.args.get("verificados") is not None,
        request.args.get("page", 1, type=int),
    )


def leer_solicitud():
    """Lo que el cliente escribe al pedir un presupuesto (sin la foto).

    La foto se lee aparte, en la vista: guardarla escribe en disco, y eso solo
    tiene sentido despues de que el resto haya validado bien.
    """
    descripcion = (request.form.get("descripcion") or "").strip()
    zona = (request.form.get("zona") or "").strip()

    error = None if descripcion else "Contale al prestador qué necesitás."
    return {"descripcion": descripcion, "zona": zona}, error


def leer_respuesta():
    """La respuesta del prestador: un mensaje obligatorio y un precio opcional."""
    mensaje = (request.form.get("respuesta_mensaje") or "").strip()
    # obligatorio=False: se puede contestar sin precio ("pasame una foto",
    # "no llego a esa zona"), pero no sin decir nada.
    precio, error = parsear_precio(
        request.form.get("respuesta_precio") or "", obligatorio=False
    )
    if error is None and not mensaje:
        error = "Escribí una respuesta para el cliente."
    return mensaje, precio, error
