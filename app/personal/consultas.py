"""Todo lo que este dominio le pregunta (y le escribe) a la base.

De aca para arriba nadie importa db.session: las vistas piden por nombre y las
reglas no tocan la base en absoluto.
"""

from sqlalchemy import func

from app.blog.modelo_post import Post
from app.personal.modelo_busqueda import BusquedaPersonal
from app.personal.modelo_postulacion import Postulacion
from db import db


def busqueda_por_id_o_404(id):
    return BusquedaPersonal.query.get_or_404(id)


def postulacion_por_id_o_404(id):
    return Postulacion.query.get_or_404(id)


def busqueda_activa_de(post_id):
    """La busqueda abierta de ese emprendimiento, o None.

    Devuelve una sola porque solo puede haber una: lo garantiza el UNIQUE
    (post_id, cupo_activa). Si alguna vez devolviera dos, el bug no esta aca.
    """
    return (
        BusquedaPersonal.query
        .filter_by(post_id=post_id, activa=True)
        .first()
    )


def busquedas_de(post_id):
    """Todas las busquedas de un emprendimiento, la abierta primero.

    Las cerradas siguen en la lista porque sus postulaciones siguen existiendo:
    apagar el toggle saca el aviso del perfil publico, no borra a quien ya se
    tomo el trabajo de escribir.
    """
    return (
        BusquedaPersonal.query
        .filter_by(post_id=post_id)
        .order_by(BusquedaPersonal.activa.desc(), BusquedaPersonal.created_at.desc())
        .all()
    )


def busquedas_de_usuario(user_id):
    """Las busquedas de todos los emprendimientos de esa persona."""
    return (
        BusquedaPersonal.query
        .join(Post, Post.id == BusquedaPersonal.post_id)
        .filter(Post.author == user_id)
        .order_by(BusquedaPersonal.activa.desc(), BusquedaPersonal.created_at.desc())
        .all()
    )


def postulaciones_de(busqueda_id):
    """Las postulaciones de una busqueda, la mas nueva primero."""
    return (
        Postulacion.query
        .filter_by(busqueda_id=busqueda_id)
        .order_by(Postulacion.created_at.desc())
        .all()
    )


def postulacion_de(busqueda_id, postulante_id):
    """La postulacion de esa persona a esa busqueda, o None."""
    return (
        Postulacion.query
        .filter_by(busqueda_id=busqueda_id, postulante_id=postulante_id)
        .first()
    )


def conteo_de_postulaciones(busqueda_ids):
    """Cuantas postulaciones tiene cada busqueda: {busqueda_id: total}.

    UN SOLO GROUP BY y no un COUNT por fila, que seria el N+1 de la bandeja.

    EL .order_by(None) ES PREVENTIVO, Y CONVIENE SABER QUE HOY NO HACE NADA.
    Tal como esta escrita, esta query se arma de cero y no hereda ningun ORDER
    BY, asi que sacarlo no rompe nada y el test de MySQL sigue pasando -- se
    comprobo. Esta igual porque el dia que alguien la derive de una consulta ya
    ordenada (que es como se escribe una bandeja: listar y de paso contar),
    MySQL con ONLY_FULL_GROUP_BY (default desde 5.7) rechaza con un error 1055
    el ORDER BY por una columna que no esta ni en el GROUP BY ni dentro de una
    agregacion, mientras SQLite lo acepta callado y la suite entera pasa. Es la
    regla que quedo anotada despues de H2.

    Que ese peligro es real y no folklore lo prueba
    test_en_mysql_un_group_by_que_hereda_el_order_by_explota, que arma la
    version "floja" y exige que MySQL la rechace.
    """
    if not busqueda_ids:
        # Sin esto seria un `IN ()`: una consulta que ya sabemos que no
        # devuelve nada. La bandeja vacia es un caso normal.
        return {}

    filas = (
        db.session.query(
            Postulacion.busqueda_id, func.count(Postulacion.id)
        )
        .filter(Postulacion.busqueda_id.in_(busqueda_ids))
        .group_by(Postulacion.busqueda_id)
        .order_by(None)
        .all()
    )
    return {busqueda_id: total for busqueda_id, total in filas}


def contar_vista_sin_postulacion(busqueda_id):
    """Suma uno a la señal debil de esa busqueda, atomicamente.

    UPDATE ... SET vistas_sin_postulacion = vistas_sin_postulacion + 1 en la
    BASE, y no leer el valor en Python, sumarle uno y guardarlo: dos personas
    que cierran el formulario a la vez leerian las dos el mismo numero y la
    segunda pisaria a la primera, con lo cual el contador perderia visitas
    justo cuando mas hay. Con la suma escrita como expresion SQL el que
    resuelve el +1 es el motor, fila bloqueada incluida.

    synchronize_session=False porque no hace falta que los objetos que ya estan
    en la sesion se enteren: quien lo llama no vuelve a leer el numero en ese
    request, y sincronizar obligaria a un SELECT extra.

    No guarda QUIEN. No hay tabla de vistas y no la va a haber por esta via: la
    señal es anonima a proposito, y el dia que haga falta saber quien, eso es
    otra decision y otra tabla.
    """
    actualizadas = (
        BusquedaPersonal.query
        .filter_by(id=busqueda_id)
        .update(
            {
                BusquedaPersonal.vistas_sin_postulacion:
                    BusquedaPersonal.vistas_sin_postulacion + 1
            },
            synchronize_session=False,
        )
    )
    db.session.commit()
    return actualizadas


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
