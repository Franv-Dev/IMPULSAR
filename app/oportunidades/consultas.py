"""Todo lo que este dominio le pregunta (y le escribe) a la base.

De aca para arriba nadie importa db.session: las vistas piden por nombre y las
reglas no tocan la base en absoluto.
"""

from sqlalchemy import func
from sqlalchemy.orm import joinedload

from app.blog.modelo_post import Post
from app.oportunidades.modelo_oportunidad import EstadosOportunidad, Oportunidad
from app.oportunidades.modelo_propuesta import Propuesta
from db import db


def oportunidad_por_id_o_404(id):
    return Oportunidad.query.get_or_404(id)


def propuesta_por_id_o_404(id):
    return Propuesta.query.get_or_404(id)


def abiertas():
    """El listado publico: las oportunidades que estan recibiendo propuestas.

    Sin filtro por rubro en esta version, a proposito: es una lista unica. El
    dia que haya suficientes como para que haga falta filtrar, el filtro se
    suma sin tocar el modelo.

    Las cerradas no aparecen (ya eligieron a alguien) y las finalizadas tampoco
    (se terminaron). Las dos siguen existiendo y las dos siguen siendo
    alcanzables por su URL para quien corresponda, ver reglas.puede_ver.

    joinedload del autor porque la tarjeta muestra quien publico: sin esto es
    un SELECT por fila, que es el N+1 de la pantalla mas visitada del dominio.
    """
    return (
        Oportunidad.query
        .options(joinedload(Oportunidad.autor))
        .filter(Oportunidad.estado == EstadosOportunidad.ABIERTA)
        # created_at Y DESPUES id, nunca created_at solo: en MySQL la columna es
        # DATETIME(0), sin microsegundos, asi que dos oportunidades publicadas
        # en el mismo segundo empatan y el orden lo decide el motor. En SQLite
        # no se ve nunca, porque ahi si hay microsegundos.
        .order_by(Oportunidad.created_at.desc(), Oportunidad.id.desc())
        .all()
    )


def de_usuario(user_id):
    """Las oportunidades que publico esa persona, incluidas las finalizadas.

    Es su historial: la finalizada salio del listado publico pero no se borro,
    y el que la publico la sigue viendo.

    Las abiertas primero, despues las cerradas, despues las finalizadas: es el
    orden en el que le importan, de lo que tiene que atender a lo que ya paso.
    """
    return (
        Oportunidad.query
        .filter(Oportunidad.autor_id == user_id)
        .order_by(
            # El CASE explicito y no el orden alfabetico del estado, que daria
            # abierta, cerrada, finalizada por casualidad y se rompería con el
            # primer estado nuevo.
            db.case(
                (Oportunidad.estado == EstadosOportunidad.ABIERTA, 0),
                (Oportunidad.estado == EstadosOportunidad.CERRADA, 1),
                else_=2,
            ),
            Oportunidad.created_at.desc(),
            Oportunidad.id.desc(),
        )
        .all()
    )


def propuestas_de(oportunidad_id):
    """Las propuestas de una oportunidad, agrupadas por emprendimiento.

    Devuelve una lista de grupos, cada uno:

        {"post": Post, "ultima": Propuesta, "anteriores": [Propuesta, ...]}

    AGRUPADAS Y NO UNA LISTA PLANA POR FECHA, que es la decision de esta
    pantalla. La pregunta que se esta contestando no es "que propuesta elijo"
    sino "a quien le doy el trabajo": en una lista plana, un emprendimiento que
    mando tres propuestas aparece tres veces intercalado entre los demas y se
    lee como tres candidatos distintos, o sea que insistir infla la presencia.
    Agrupado, cada emprendimiento ocupa un lugar y su historial de precios
    queda a la vista, que es informacion util y no ruido.

    UNA SOLA CONSULTA. La agrupacion se arma en Python sobre el resultado ya
    ordenado y no con un GROUP BY por grupo ni con un SELECT por emprendimiento,
    que seria el N+1 de esta pantalla. La lista es de decenas: el costo de
    agrupar en Python es nada y el de N+1 crece con cada propuesta.

    El grupo aceptado va primero mientras haya uno; dentro de cada grupo, la
    propuesta mas nueva es la que se muestra y las viejas quedan plegadas.
    """
    propuestas = (
        Propuesta.query
        .options(joinedload(Propuesta.post))
        .filter(Propuesta.oportunidad_id == oportunidad_id)
        # Igual que en abiertas(): el id desempata lo que DATETIME(0) empata.
        .order_by(Propuesta.created_at.desc(), Propuesta.id.desc())
        .all()
    )

    grupos = {}
    for propuesta in propuestas:
        grupo = grupos.get(propuesta.post_id)
        if grupo is None:
            # La primera que aparece de ese emprendimiento es la mas nueva,
            # porque la lista ya viene ordenada.
            grupos[propuesta.post_id] = {
                "post": propuesta.post,
                "ultima": propuesta,
                "anteriores": [],
                "aceptada": propuesta.aceptada,
            }
        else:
            grupo["anteriores"].append(propuesta)
            # Una propuesta vieja puede ser la aceptada: se acepta la que el
            # publicador quiera, no necesariamente la ultima que llego.
            grupo["aceptada"] = grupo["aceptada"] or propuesta.aceptada

    # dict conserva el orden de insercion, asi que los grupos ya vienen por su
    # propuesta mas nueva; lo unico que se mueve es el aceptado, que va arriba.
    return sorted(grupos.values(), key=lambda grupo: not grupo["aceptada"])


def propuesta_aceptada_de(oportunidad_id):
    """La propuesta aceptada de esa oportunidad, o None.

    Devuelve una sola porque solo puede haber una: lo garantiza el UNIQUE
    (oportunidad_id, cupo_aceptada). Si alguna vez devolviera dos, el bug no
    esta aca.
    """
    return (
        Propuesta.query
        .filter_by(oportunidad_id=oportunidad_id, aceptada=True)
        .first()
    )


def propuestas_de_usuario(user_id):
    """Las propuestas que mandaron los emprendimientos de esa persona.

    Es la otra mitad del dominio: lo que ofrecio y en que quedo cada una.
    """
    return (
        Propuesta.query
        .options(
            joinedload(Propuesta.post),
            joinedload(Propuesta.oportunidad),
        )
        .join(Post, Post.id == Propuesta.post_id)
        .filter(Post.author == user_id)
        .order_by(Propuesta.created_at.desc(), Propuesta.id.desc())
        .all()
    )


def propuesta_de_post(oportunidad_id, post_id):
    """La ultima propuesta de ese emprendimiento a esa oportunidad, o None.

    "La ultima" y no "la propuesta": pueden ser varias, a proposito (ver el
    docstring de Propuesta). Sirve para mostrarle al emprendedor lo que ya
    ofrecio antes de que escriba otra.
    """
    return (
        Propuesta.query
        .filter_by(oportunidad_id=oportunidad_id, post_id=post_id)
        .order_by(Propuesta.created_at.desc(), Propuesta.id.desc())
        .first()
    )


def conteo_de_propuestas(oportunidad_ids):
    """Cuantas propuestas tiene cada oportunidad: {oportunidad_id: total}.

    UN SOLO GROUP BY y no un COUNT por fila, que seria el N+1 del listado
    publico y del historial.

    EL .order_by(None) ES PREVENTIVO Y HOY NO HACE NADA, igual que en
    app/personal/consultas.conteo_de_postulaciones: tal como esta escrita, esta
    query se arma de cero y no hereda ningun ORDER BY. Esta para el dia que
    alguien la derive de una consulta ya ordenada (que es como se escribe un
    listado: listar y de paso contar), porque ahi MySQL con ONLY_FULL_GROUP_BY
    (default desde 5.7) la rechaza con un error 1055 por ordenar por una
    columna que no esta ni en el GROUP BY ni dentro de una agregacion, mientras
    SQLite lo acepta callado y la suite entera pasa.

    Que el peligro es real lo prueba, en tests/test_oportunidades_mysql.py,
    test_en_mysql_un_group_by_que_hereda_el_order_by_explota, que arma la
    version floja y exige el error.
    """
    if not oportunidad_ids:
        # Sin esto seria un `IN ()`: una consulta que ya sabemos que no
        # devuelve nada. El listado vacio es un caso normal.
        return {}

    filas = (
        db.session.query(Propuesta.oportunidad_id, func.count(Propuesta.id))
        .filter(Propuesta.oportunidad_id.in_(oportunidad_ids))
        .group_by(Propuesta.oportunidad_id)
        .order_by(None)
        .all()
    )
    return {oportunidad_id: total for oportunidad_id, total in filas}


def posts_de(user_id):
    """Los emprendimientos de esa persona, para elegir desde cual proponer.

    Vacio significa que no es emprendedor y no puede proponer: es la mitad
    asimetrica del dominio (ver el docstring de reglas.py).
    """
    return (
        Post.query
        .filter(Post.author == user_id)
        .order_by(Post.created.desc(), Post.id.desc())
        .all()
    )


def guardar(fila=None):
    """Confirma la transaccion, agregando la fila nueva si se pasa una.

    Existe para que las vistas no importen db solo para escribir dos lineas de
    sesion; el manejo del IntegrityError se queda arriba, que es donde se sabe
    que significa el choque.
    """
    if fila is not None:
        db.session.add(fila)
    db.session.commit()


def descartar():
    db.session.rollback()
