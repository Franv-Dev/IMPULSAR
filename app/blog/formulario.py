"""Parseo y validacion de lo que manda el navegador.

Es la frontera entre el formulario HTML y el resto del dominio: de aca para
adentro nadie vuelve a tocar request.form. La validacion es a mano (una
variable `error` con el mensaje listo para mostrar) porque asi valida todo el
proyecto: Flask-WTF esta instalado pero solo se usa para el CSRF.

Los archivos se leen aca pero no se tocan: se devuelven tal como vinieron.
Guardarlos escribe en disco, y eso solo tiene sentido despues de que el resto
haya validado bien, asi que lo hace la vista.
"""

from flask import request

from app.blog.reglas import RATING_MAXIMO, RATING_MINIMO


def leer_post(pedir_descripcion=True):
    """Los campos de un emprendimiento tal como los mando el usuario.

    Devuelve (valores, archivos, error). `valores` es lo que se guarda,
    `archivos` la foto principal y la galeria sin tocar, y `error` el primer
    mensaje que corta, o None.

    pedir_descripcion es la unica diferencia entre alta y edicion, y viene tal
    cual estaba: al crear, un emprendimiento sin descripcion se rechaza; al
    editar, no se valida. Ojo que no validarla no significa conservarla, la
    edicion guarda lo que haya llegado aunque sea vacio.
    """
    valores = {
        "title": (request.form.get("title") or "").strip(),
        "body": (request.form.get("body") or "").strip(),
        "category": (request.form.get("category") or "").strip(),
        "address_street": (request.form.get("address_street") or "").strip(),
    }
    archivos = {
        "imagen": request.files.get("image"),
        "galeria": request.files.getlist("galeria"),
    }

    error = None
    if not valores["title"]:
        error = "Se requiere un título."
    elif pedir_descripcion and not valores["body"]:
        error = "Se requiere una descripción."

    return valores, archivos, error


def contar_fotos(archivos):
    """Cuantas fotos trae el formulario, contando la principal si viene.

    Un <input type="file"> vacio igual viaja en el POST, con filename en "";
    por eso no alcanza con mirar si la lista tiene elementos.
    """
    galeria = [f for f in archivos["galeria"] if f and f.filename]
    principal = archivos["imagen"]
    return len(galeria) + (1 if principal and principal.filename else 0)


def leer_resenia():
    """Las estrellas y el comentario de una resenia.

    Un rating que no es un numero se trata igual que uno fuera de rango: el
    formulario manda un radio button, asi que llegar con basura es alguien
    mandando el POST a mano.
    """
    try:
        rating = int(request.form.get("rating", 0))
    except ValueError:
        rating = 0

    comentario = (request.form.get("comment") or "").strip()

    error = None
    if not RATING_MINIMO <= rating <= RATING_MAXIMO:
        error = (
            f"Seleccioná una calificación entre {RATING_MINIMO} y "
            f"{RATING_MAXIMO} estrellas."
        )

    return rating, comentario, error


def leer_respuesta_a_resenia():
    """La respuesta publica del dueño a una resenia."""
    texto = (request.form.get("reply") or "").strip()
    error = None if texto else "Escribí una respuesta antes de enviarla."
    return texto, error


def leer_motivo_de_reporte():
    motivo = (request.form.get("reason") or "").strip()
    error = None if motivo else "Contanos el motivo del reporte."
    return motivo, error


def leer_categoria_de_filtro():
    """La categoria por la que filtra el listado, tal como vino.

    No se descarta la que no existe: el listado no filtra por ella (eso lo
    decide reglas.categoria_valida), pero el formulario se repinta con lo que
    el usuario tenia en la URL, que es como venia funcionando.
    """
    return (request.args.get("category") or "").strip()


def leer_busqueda():
    return (request.args.get("q") or "").strip()


def leer_cercania():
    """Los tres campos de la busqueda por cercania, sin resolver nada.

    Se puede pasar lat/lon directamente (por ejemplo desde la geolocalizacion
    del navegador) o una direccion en texto para geocodificar. Traducir el texto
    a coordenadas es una llamada a MapTiler, o sea trabajo con red de por medio,
    y eso lo hace la vista: aca solo se lee lo que vino.
    """
    return (
        (request.args.get("near") or "").strip(),
        request.args.get("lat", type=float),
        request.args.get("lon", type=float),
    )


def leer_pagina():
    return request.args.get("page", 1, type=int)
