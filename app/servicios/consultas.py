"""Todo lo que este dominio le pregunta a la base.

Es la unica capa que arma querys. Las vistas no tocan db.session: piden por
nombre lo que necesitan, y si mañana una consulta necesita otro joinedload o
otro orden, se cambia aca sin abrir ninguna ruta.

Los joinedload no son un detalle de performance suelto: sin ellos, pintar el
panel dispara un SELECT por fila para ir a buscar el emprendimiento (el problema
N+1). Van en la consulta y no en la vista justamente para que no se pierdan
cuando alguien reescriba la vista.
"""

from sqlalchemy import func
from sqlalchemy.orm import joinedload

from app.servicios.modelo import Service
from app.servicios.modelo_solicitud import EstadosSolicitud, ServiceRequest
from app.servicios.modelo_verificacion import EstadosVerificacion, VerificationRequest
from app.servicios.reglas import Ordenes, Precios
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


def _filtrar_busqueda(consulta, rubro, zona, solo_verificados, precio):
    """Los filtros de la busqueda publica, en un solo lugar.

    Lo usan buscar_servicios() y conteos_por_rubro(): el numerito que va al
    lado de cada rubro tiene que contar EXACTAMENTE lo que ese rubro va a
    devolver si lo tocan. Con los filtros escritos dos veces, cualquier cambio
    en uno deja al contador mintiendo, que es peor que no tenerlo.
    """
    if rubro:
        consulta = consulta.filter(Service.rubro == rubro)

    if zona:
        consulta = consulta.filter(
            Service.zona_cobertura.ilike(f"%{_escapar_like(zona)}%", escape="\\")
        )

    if solo_verificados:
        consulta = consulta.filter(Service.verificado.is_(True))

    # IS NULL / IS NOT NULL y no una comparacion contra cero: "a presupuestar"
    # es la ausencia de precio, no un precio de cero pesos (ver el CHECK de
    # Service.precio_estimado, que ademas prohibe el cero).
    if precio == Precios.CERRADO:
        consulta = consulta.filter(Service.precio_estimado.isnot(None))
    elif precio == Precios.PRESUPUESTAR:
        consulta = consulta.filter(Service.precio_estimado.is_(None))

    return consulta


def conteos_por_rubro(zona, solo_verificados, precio):
    """Cuantos servicios devolveria cada rubro con los OTROS filtros puestos.

    Es el numero que la columna de filtros muestra al lado de cada rubro, y por
    eso no filtra por rubro: el contador tiene que decir cuantos hay en
    "Electricidad" mientras estas parado en "Plomería", que es justamente lo
    que hace que sirva para elegir a donde ir.

    Un GROUP BY y no trece COUNT: es una sola pasada por la tabla, y la columna
    rubro ya esta indexada.
    """
    filas = _filtrar_busqueda(
        db.session.query(Service.rubro, func.count(Service.id))
        .filter(Service.disponible.is_(True)),
        rubro=None, zona=zona, solo_verificados=solo_verificados, precio=precio,
    ).group_by(Service.rubro).all()

    return {rubro: cuantos for rubro, cuantos in filas}


def buscar_servicios(rubro, zona, solo_verificados, precio, orden, pagina, por_pagina):
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

    `precio` separa los que tienen precio publicado de los que se cotizan (ver
    reglas.Precios), y `orden` es uno de reglas.Ordenes. Service no tiene
    coordenadas, asi que no hay distancia real que calcular como en
    buscar_posts() del blog.

    El desempate por id no es decorativo: sin el, dos servicios cargados en el
    mismo segundo (o con el mismo titulo) pueden salir en distinto orden en
    cada consulta, y eso en una lista paginada significa que una fila aparece
    dos veces o no aparece nunca. Es el mismo problema que ya se habia
    resuelto en "Mis favoritos" al desempatar por fecha.
    """
    consulta = _filtrar_busqueda(
        Service.query
        .join(Post, Post.id == Service.post_id)
        # Sin esto, pintar el nombre del emprendimiento en cada tarjeta dispara
        # un SELECT por fila (problema N+1).
        .options(joinedload(Service.post))
        .filter(Service.disponible.is_(True)),
        rubro=rubro, zona=zona, solo_verificados=solo_verificados, precio=precio,
    )

    if orden == Ordenes.NOMBRE:
        consulta = consulta.order_by(Post.title, Service.titulo, Service.id)
    else:
        consulta = consulta.order_by(Service.created_at.desc(), Service.id.desc())

    return consulta.paginate(page=pagina, per_page=por_pagina, error_out=False)


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


def estados_de_verificacion(service_ids):
    """El estado del ULTIMO pedido de cada servicio: {service_id: estado}.

    Es lo que el panel del dueño necesita para decir, en la misma fila, si ese
    servicio esta en revision o si se lo rechazaron. Hasta ahora eso solo se
    veia entrando de a uno a /servicios/<id>/verificar: la fila sabia decir
    "verificado" (que es una columna de Service) y nada mas, asi que un pedido
    rechazado hace tres semanas no se enteraba nadie.

    Dos consultas y no una por servicio (problema N+1): primero el id del
    ultimo pedido de cada servicio, despues esas filas. El maximo se toma sobre
    el id y no sobre created_at porque dos pedidos del mismo servicio pueden
    compartir segundo —en MySQL la columna no guarda microsegundos— y ahi el
    MAX no desempata; el id es unico y crece con el tiempo, que es lo mismo que
    hace ultima_verificacion_de() al desempatar por id.

    Sin ids no consulta nada: un `IN ()` vacio es SQL invalido en algunos
    motores y una pasada al pedo en el resto.
    """
    if not service_ids:
        return {}

    ultimos = (
        db.session.query(func.max(VerificationRequest.id))
        .filter(VerificationRequest.service_id.in_(service_ids))
        .group_by(VerificationRequest.service_id)
        .scalar_subquery()
    )
    filas = (
        VerificationRequest.query
        .filter(VerificationRequest.id.in_(ultimos))
        .all()
    )
    return {fila.service_id: fila.estado for fila in filas}


def cuantas_solicitudes_pendientes_para(user_id):
    """Cuantos presupuestos esperan respuesta de ese usuario, como prestador.

    Un COUNT y no len(solicitudes_recibidas_por(user_id)): el panel de
    servicios solo quiere el numero para el aviso de arriba, y traer todas las
    solicitudes con sus joinedload para contarlas seria pagar la pantalla de
    Presupuestos entera en cada visita a Mis servicios.
    """
    return (
        db.session.query(func.count(ServiceRequest.id))
        .join(Service, Service.id == ServiceRequest.service_id)
        .join(Post, Post.id == Service.post_id)
        .filter(
            Post.author == user_id,
            ServiceRequest.estado == EstadosSolicitud.PENDIENTE,
        )
        .scalar()
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
