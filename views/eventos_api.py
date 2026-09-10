"""API JSON de eventos, para el calendario del home.

Va en su propio blueprint y su propio archivo, igual que posts_api: el ABM y la
cartelera HTML viven en views/eventos.py y hablan HTML, y esto habla JSON. Son
dos consumidores distintos de los mismos datos.

POR QUE UN ENDPOINT Y NO CONTEXTO EN EL HOME: el calendario tiene navegacion de
meses, asi que necesita traer un mes distinto sin recargar la pagina. Pasarle el
mes actual desde una vista serviria para el primer render y nada mas; el resto
igual tendria que salir por fetch. Ademas el home ya carga sus emprendimientos
destacados asi (ver /api/posts/ y static/js/main.js), con lo cual esto sigue el
camino que el home ya tiene armado en vez de abrirle uno nuevo.

TODO LO QUE SALE DE ACA ES PUBLICO, y no es un descuido: Event no tiene ningun
campo de visibilidad ni de borrador. Un evento es un cartel que el emprendedor
publica para que lo vean, y hoy ya se muestra entero en la cartelera de
/eventos/ y en el perfil del autor, las dos sin login. Por eso este endpoint no
mira g.user ni filtra por sesion: no hay nada que filtrar. Si alguna vez Event
gana un estado (borrador, cancelado, privado), este es uno de los tres lugares
que hay que tocar.
"""

from flask import Blueprint, jsonify, request, url_for
from sqlalchemy.orm import joinedload

from models.event import Event
from services.eventos import en_rango, hoy_en_argentina, parsear_mes, rango_del_mes

eventos_api = Blueprint("eventos_api", __name__, url_prefix="/api/eventos")

# Tope duro de eventos por mes. No hay paginado porque un calendario mensual no
# se pagina: o entra el mes o no es un mes. El tope existe igual por lo mismo
# que MAX_POR_PAGINA en posts_api -- que una respuesta no pueda crecer sin
# limite -- y la respuesta avisa con `truncado` en vez de mentir por omision.
MAX_EVENTOS_POR_MES = 300


def _serializar(evento):
    """El evento como lo consume el calendario.

    Se arma aca y no en Event.serialize() para no cambiar lo que ya devuelve ese
    metodo, que usan otros. Lo que suma son los dos datos del emprendimiento que
    el panel necesita para mostrar de quien es el evento y linkear: los dos son
    publicos, es la misma informacion que muestra la cartelera.
    """
    return {
        **evento.serialize(),
        "emprendimiento": evento.post.title,
        "url": url_for("blog.detail", id=evento.post_id),
    }


@eventos_api.get("/")
def list_eventos():
    """Los eventos publicos de un mes.

    Parametros de query:
        mes   "AAAA-MM". Si falta o no se entiende, se usa el mes en curso.

    El mes en curso es el de Argentina y no el del reloj del visitante: la
    fecha de un evento es hora local (ver services/eventos.py), asi que un
    usuario con el navegador en otro huso tiene que ver el mismo mes que todos.
    Por eso `hoy` viaja en la respuesta: el JS marca "hoy" con eso y no con su
    propio Date, que a partir de cierta diferencia horaria caeria en otro dia.
    """
    hoy = hoy_en_argentina()
    anio_y_mes = parsear_mes(request.args.get("mes")) or (hoy.year, hoy.month)
    desde, hasta = rango_del_mes(*anio_y_mes)

    # joinedload por lo mismo que en eventos.index: sin esto el .post de cada
    # evento dispara su propio SELECT al serializar (problema N+1).
    query = en_rango(Event.query.options(joinedload(Event.post)), desde, hasta)

    # Se pide uno de mas que el tope para saber si habia mas sin tener que
    # contar aparte con un COUNT(*).
    eventos = query.limit(MAX_EVENTOS_POR_MES + 1).all()
    truncado = len(eventos) > MAX_EVENTOS_POR_MES
    eventos = eventos[:MAX_EVENTOS_POR_MES]

    return jsonify({
        "mes": f"{desde.year:04d}-{desde.month:02d}",
        "desde": desde.isoformat(),
        "hasta": hasta.isoformat(),
        "hoy": hoy.isoformat(),
        "items": [_serializar(evento) for evento in eventos],
        "total": len(eventos),
        "truncado": truncado,
    }), 200
