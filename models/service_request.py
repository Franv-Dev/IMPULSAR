from db import db, utcnow


class EstadosSolicitud:
    """Estados por los que pasa una solicitud de presupuesto.

    String con una clase de constantes y no un sa.Enum, que es como resuelve
    esto todo el proyecto (ver Roles y Categorias): un Enum de verdad obliga a
    un ALTER TYPE para agregar un estado, y aca los estados van a moverse.

    No hay aceptacion ni rechazo a proposito. Como no hay pago ni compromiso
    de por medio, "cerrada" es archivar, no acordar: sirve para sacarla de la
    lista de lo que falta contestar.
    """

    PENDIENTE = "pendiente"
    RESPONDIDA = "respondida"
    CERRADA = "cerrada"

    TODOS = (PENDIENTE, RESPONDIDA, CERRADA)

    ETIQUETAS = {
        PENDIENTE: "Pendiente",
        RESPONDIDA: "Respondida",
        CERRADA: "Cerrada",
    }


class ServiceRequest(db.Model):
    """Un pedido de presupuesto de un cliente sobre un servicio.

    El flujo es corto: el cliente describe lo que necesita (pendiente), el
    prestador contesta con un precio y un mensaje (respondida), y cualquiera
    de los dos la cierra cuando ya no hace falta (cerrada). Quien cierra es
    cualquiera de las dos partes porque los dos tienen motivos distintos y
    reales: el cliente resolvio el problema y no vuelve, y el prestador
    necesita poder limpiar su lista de pendientes cuando el cliente nunca
    contesta.

    PRIVACIDAD: una solicitud la ven dos personas, el cliente que la hizo y el
    dueño del emprendimiento del que cuelga el servicio. Nadie mas, ni otro
    emprendedor ni un admin. Eso se hace cumplir en las vistas (ver
    views/servicios.py), que es donde se resuelve tambien la de las
    estadisticas del perfil.

    OJO con la foto: la privacidad es de la PAGINA, no del archivo. La imagen
    se guarda en static/uploads como todas las demas y Flask la sirve sin
    ningun chequeo de permiso, asi que quien tenga la URL la ve sin sesion. No
    es enumerable (el nombre lleva un uuid, ver services/uploads.py), pero si
    alguna vez hace falta que el archivo tambien sea privado hay que servirlo
    por una ruta propia con el mismo chequeo que la pagina.
    """

    __tablename__ = "service_requests"

    id = db.Column(db.Integer, primary_key=True)
    # ondelete="CASCADE" y con nombre explicito, igual que el resto de las FK
    # nuevas: si se borra el servicio, las solicitudes sobre el no pueden
    # quedar apuntando a nada.
    service_id = db.Column(
        db.Integer,
        db.ForeignKey(
            "services.id", ondelete="CASCADE",
            name="fk_service_requests_service_id_services",
        ),
        nullable=False, index=True,
    )
    # CASCADE tambien aca, y esto si es una diferencia con lo que hay: las
    # cinco FK viejas que apuntan a users (favorites.user_id, messages.client_id,
    # messages.sender_id, reports.reporter_id y reviews.user_id) no lo tienen, y
    # por eso hoy no se puede borrar un usuario que dejo actividad en un
    # emprendimiento ajeno (ver el comentario largo de models/post.py). Esta
    # tabla no repite esa deuda: borrar un usuario se lleva sus solicitudes.
    cliente_id = db.Column(
        db.Integer,
        db.ForeignKey(
            "users.id", ondelete="CASCADE",
            name="fk_service_requests_cliente_id_users",
        ),
        nullable=False, index=True,
    )

    # Que necesita el cliente. Text y no String(300) como la descripcion del
    # servicio: aca el largo lo pone el problema que tenga, no una tarjeta.
    descripcion = db.Column(db.Text, nullable=False)
    # Solo si difiere de la zona del servicio; si no, se muestra la del
    # servicio y esto queda en NULL.
    zona = db.Column(db.String(120), nullable=True)
    # Nombre de archivo, igual que Post.image, PostImage.filename y
    # Product.foto. Ver la advertencia de privacidad del docstring.
    foto = db.Column(db.String(100), nullable=True)

    estado = db.Column(
        db.String(20), nullable=False,
        default=EstadosSolicitud.PENDIENTE,
        server_default=EstadosSolicitud.PENDIENTE,
        index=True,
    )
    # La respuesta del prestador. Las dos columnas son nullable porque hasta
    # que conteste no existen; el precio ademas puede seguir siendo NULL
    # despues, si contesta "pasame una foto" o "no llego a esa zona".
    respuesta_precio = db.Column(db.Numeric(10, 2), nullable=True)
    respuesta_mensaje = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, default=utcnow, index=True)
    responded_at = db.Column(db.DateTime, nullable=True)

    # cascade="all, delete-orphan" en el lado del servicio: la FK ya borra en
    # la base, pero sin esto el ORM intenta dejar las filas huerfanas poniendo
    # service_id en NULL cuando se borra un Service desde la sesion, y la
    # columna es NOT NULL. Mismo caso que imagenes, eventos y productos.
    servicio = db.relationship(
        "Service",
        backref=db.backref("solicitudes", cascade="all, delete-orphan"),
    )
    # Sin backref con cascada del lado del usuario, al reves que el servicio:
    # aca el borrado lo hace la base con el ON DELETE CASCADE de la FK. Es lo
    # mismo que hace Message con client/sender, solo que alla la FK no cascadea
    # y por eso el borrado de usuarios sigue trabado.
    cliente = db.relationship("User", foreign_keys=[cliente_id])

    def __repr__(self):
        return (
            f"<ServiceRequest service_id={self.service_id} "
            f"cliente_id={self.cliente_id} {self.estado}>"
        )

    @property
    def estado_label(self):
        return EstadosSolicitud.ETIQUETAS.get(self.estado, self.estado)

    def serialize(self):
        return {
            "id": self.id,
            "service_id": self.service_id,
            "cliente_id": self.cliente_id,
            "descripcion": self.descripcion,
            "zona": self.zona,
            "foto": self.foto,
            "estado": self.estado,
            "estado_label": self.estado_label,
            # str y no float, por lo mismo que el resto de los precios.
            "respuesta_precio": (
                str(self.respuesta_precio) if self.respuesta_precio is not None else None
            ),
            "respuesta_mensaje": self.respuesta_mensaje,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "responded_at": self.responded_at.isoformat() if self.responded_at else None,
        }
