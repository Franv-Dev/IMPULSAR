"""Todo lo que este dominio le pregunta a la base.

Es la unica capa que arma querys. Las vistas no tocan db.session: piden por
nombre lo que necesitan, y si mañana una consulta necesita otro joinedload o
otro orden, se cambia aca sin abrir ninguna ruta.

Los joinedload no son un detalle de performance suelto: sin ellos, pintar el
panel dispara un SELECT por fila para ir a buscar el emprendimiento (el problema
N+1). Van en la consulta y no en la vista justamente para que no se pierdan
cuando alguien reescriba la vista.
"""

from sqlalchemy.orm import joinedload

from app.servicios.modelo import Service
from app.servicios.modelo_solicitud import EstadosSolicitud, ServiceRequest
from db import db
from models.post import Post


def servicio_por_id_o_404(id):
    return Service.query.get_or_404(id)


def solicitud_por_id_o_404(id):
    return ServiceRequest.query.get_or_404(id)


def servicios_de(user_id):
    """Los servicios de todos los emprendimientos de ese usuario, para el panel."""
    return (
        Service.query
        .join(Post, Post.id == Service.post_id)
        .options(joinedload(Service.post))
        .filter(Post.author == user_id)
        .order_by(Post.title, Service.titulo)
        .all()
    )


def emprendimientos_de(user_id):
    return Post.query.filter_by(author=user_id).order_by(Post.title).all()


def cuantos_servicios_tiene(post_id):
    """Cuantos servicios tiene ya ese emprendimiento.

    Un COUNT y no len(post.servicios): trae un numero en vez de todas las
    filas solo para contarlas.
    """
    return Service.query.filter_by(post_id=post_id).count()


def solicitud_pendiente_de(service_id, cliente_id):
    """La solicitud pendiente de ese cliente sobre ese servicio, si la hay."""
    return ServiceRequest.query.filter_by(
        service_id=service_id,
        cliente_id=cliente_id,
        estado=EstadosSolicitud.PENDIENTE,
    ).first()


def solicitudes_recibidas_por(user_id):
    """Las que llegaron a los servicios de los emprendimientos de ese usuario."""
    return (
        ServiceRequest.query
        .join(Service, Service.id == ServiceRequest.service_id)
        .join(Post, Post.id == Service.post_id)
        .options(
            joinedload(ServiceRequest.servicio).joinedload(Service.post),
            joinedload(ServiceRequest.cliente),
        )
        .filter(Post.author == user_id)
        .order_by(ServiceRequest.created_at.desc())
        .all()
    )


def solicitudes_enviadas_por(user_id):
    """Las que ese usuario hizo como cliente."""
    return (
        ServiceRequest.query
        .options(joinedload(ServiceRequest.servicio).joinedload(Service.post))
        .filter(ServiceRequest.cliente_id == user_id)
        .order_by(ServiceRequest.created_at.desc())
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


def borrar(fila):
    db.session.delete(fila)
    db.session.commit()


def descartar():
    db.session.rollback()
