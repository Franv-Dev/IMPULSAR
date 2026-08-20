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
from app.servicios.modelo_verificacion import EstadosVerificacion, VerificationRequest
from db import db
from app.blog.modelo_post import Post


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


def _escapar_like(texto):
    """Neutraliza los comodines de LIKE que vengan escritos en la busqueda.

    En un patron LIKE/ILIKE, % es "cualquier cosa" y _ es "cualquier caracter":
    buscar la zona "Maipu_centro" traia tambien "Maipu centro" y "MaipuXcentro",
    y buscar "%" traia todo. No es un agujero de seguridad (el valor viaja como
    parametro, no concatenado al SQL), pero devuelve de mas.

    La barra invertida se escapa primero, si no se duplicaria la que agregan
    los dos reemplazos de abajo. El caracter de escape se pasa aparte, en el
    argumento escape= del ilike().
    """
    return texto.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def buscar_servicios(rubro, zona, solo_verificados, pagina, por_pagina):
    """La busqueda publica de servicios, ya paginada.

    Filtra siempre disponible=True, que es el mismo criterio con el que
    servicios_de(post_id, solo_disponibles) arma el catalogo publico de un
    emprendimiento y con el que vistas.solicitar() rechaza pedir presupuesto
    sobre uno apagado: un servicio apagado no esta tomando trabajos, asi que no
    tiene por que aparecer en una busqueda.

    El rubro filtra exacto porque es catalogo fijo (ver Rubros en modelo.py) y
    esta indexado justamente para esta consulta; la zona filtra con ilike
    porque es texto libre a proposito ("Maipu y alrededores", "toda la ciudad")
    y no hay catalogo contra el cual comparar.

    solo_verificados es opt-in y filtra exacto por Service.verificado, que lo
    pone un admin despues de mirar la matricula y nunca el dueño del servicio.
    Va como filtro y no como orden a proposito: quien lo tilda esta diciendo que
    no le sirve un prestador sin credencial revisada, no que prefiere verlos
    primero. Sin tildar, la busqueda devuelve verificados y no verificados
    mezclados, que es lo que hacia antes de que existiera este filtro.

    Ordena por emprendimiento y titulo, igual que servicios_de(user_id): Service
    no tiene coordenadas, asi que no hay distancia real que calcular como en
    buscar_posts() del blog.
    """
    consulta = (
        Service.query
        .join(Post, Post.id == Service.post_id)
        # Sin esto, pintar el nombre del emprendimiento en cada tarjeta dispara
        # un SELECT por fila (problema N+1).
        .options(joinedload(Service.post))
        .filter(Service.disponible.is_(True))
    )

    if rubro:
        consulta = consulta.filter(Service.rubro == rubro)

    if zona:
        consulta = consulta.filter(
            Service.zona_cobertura.ilike(f"%{_escapar_like(zona)}%", escape="\\")
        )

    if solo_verificados:
        consulta = consulta.filter(Service.verificado.is_(True))

    return (
        consulta
        .order_by(Post.title, Service.titulo)
        .paginate(page=pagina, per_page=por_pagina, error_out=False)
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


# ------------------------------------------------- verificacion de credenciales

def verificacion_por_id_o_404(id):
    return VerificationRequest.query.get_or_404(id)


def verificacion_pendiente_de(service_id):
    """El pedido de verificacion sin resolver de ese servicio, si lo hay."""
    return VerificationRequest.query.filter_by(
        service_id=service_id,
        estado=EstadosVerificacion.PENDIENTE,
    ).first()


def ultima_verificacion_de(service_id):
    """El ultimo pedido de ese servicio, resuelto o no, para mostrarle al dueño.

    Mas nuevo primero: lo que le interesa al prestador es en que quedo el
    ultimo intento (y el motivo, si se lo rechazaron), no el historial.
    """
    return (
        VerificationRequest.query
        .filter_by(service_id=service_id)
        .order_by(VerificationRequest.created_at.desc(), VerificationRequest.id.desc())
        .first()
    )


def verificaciones_pendientes():
    """La cola del admin, mas viejas primero: se atiende por orden de llegada.

    Al reves que reportes(), que ordena por fecha descendente. Un reporte lo que
    necesita es que el admin vea rapido lo ultimo que se denuncio; aca del otro
    lado hay alguien esperando una respuesta desde que la mando, y dejar las
    viejas al final es lo que hace que una se quede sin atender para siempre.

    Los joinedload traen el servicio y su emprendimiento en la misma consulta:
    la tabla del panel muestra los dos por fila, y sin ellos eso es un SELECT
    por pedido (problema N+1).
    """
    return (
        VerificationRequest.query
        .options(joinedload(VerificationRequest.servicio).joinedload(Service.post))
        .filter(VerificationRequest.estado == EstadosVerificacion.PENDIENTE)
        .order_by(VerificationRequest.created_at.asc())
        .all()
    )


def cuantas_verificaciones_pendientes():
    """Para el contador del dashboard. Un COUNT y no len() del listado."""
    return (
        VerificationRequest.query
        .filter(VerificationRequest.estado == EstadosVerificacion.PENDIENTE)
        .count()
    )


# ------------------------------------------------------------------ escritura

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
