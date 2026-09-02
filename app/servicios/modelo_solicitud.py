from db import db, utcnow
from app.servicios import fotos_huerfanas


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
    app/servicios/reglas.py y vistas.py), que es donde se resuelve tambien la de las
    estadisticas del perfil.

    LA FOTO TAMBIEN ES PRIVADA, y no siempre lo fue: hasta que existio
    servicios.foto_de_solicitud, la imagen se servia por /static/uploads como
    todas las demas y Flask no chequeaba nada, con lo cual quien tuviera la URL
    la veia sin sesion. Hoy sale por una ruta del blueprint que aplica el mismo
    reglas.es_parte_de_la_solicitud que la pagina.

    Lo que sigue valiendo: el archivo esta en la misma carpeta que el resto de
    los uploads, que si son publicos. Lo unico que lo protege es que nadie
    publica su URL directa, asi que un template que arme
    url_for("static", filename="uploads/" ~ solicitud.foto) vuelve a abrirlo
    sin que falle nada.

    UNA SOLA PENDIENTE: un cliente no puede tener dos solicitudes pendientes
    sobre el mismo servicio. Eso lo garantiza la base y no la vista: chequear
    antes de insertar deja una ventana entre el SELECT y el INSERT, y dos
    requests que entran juntos (el doble click que manda dos POST, o dos
    pestañas) pasan los dos el chequeo y guardan los dos. La vista igual
    chequea antes, pero para dar un mensaje lindo, no para garantizar nada.

    La constraint es UNIQUE(service_id, cliente_id, cupo_pendiente), donde
    cupo_pendiente vale 1 mientras la solicitud esta pendiente y NULL cuando no
    lo esta. En los dos motores (MySQL y SQLite) un UNIQUE ignora las filas con
    NULL, asi que la regla termina aplicando solo a las pendientes: las
    respondidas y las cerradas pueden repetirse todas las veces que haga falta.
    Es la forma portable de escribir el "unique parcial" que MySQL no tiene.
    """

    __tablename__ = "service_requests"

    __table_args__ = (
        # Ver "UNA SOLA PENDIENTE" en el docstring: el que cierra de verdad la
        # ventana entre el chequeo y el INSERT.
        db.UniqueConstraint(
            "service_id", "cliente_id", "cupo_pendiente",
            name="uq_service_requests_pendiente",
        ),
        # Mismo criterio que ck_services_precio_estimado_positivo: el precio
        # que contesta el prestador se valida en services/precios.py, y esto es
        # la red de abajo para lo que no entra por el formulario.
        #
        # NULL sigue siendo valido y no es un descuido: la respuesta puede no
        # traer precio ("pasame una foto", "no llego a esa zona"), que es lo
        # que dice el comentario de la columna. Lo que no puede es traer un
        # cero o un negativo, porque eso ya es un presupuesto de cero pesos.
        db.CheckConstraint(
            "respuesta_precio IS NULL OR respuesta_precio > 0",
            name="ck_service_requests_respuesta_precio_positivo",
        ),
    )

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
    # CASCADE tambien aca: borrar un usuario se lleva sus solicitudes. Cuando
    # se escribio esta tabla era la excepcion -- las cinco FK viejas a users
    # (favorites.user_id, messages.client_id, messages.sender_id,
    # reports.reporter_id y reviews.user_id) estaban en NO ACTION y por eso no
    # se podia borrar un usuario con actividad ajena. Desde b2b97d078fb2 es la
    # regla y esta tabla ya no es un caso aparte.
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
    # Vale 1 si estado == pendiente, y NULL si no. No se toca a mano en ningun
    # lado: lo mantiene el listener de abajo, para que no pueda quedar
    # desincronizado de `estado` (que es de donde sale su valor).
    cupo_pendiente = db.Column(db.Integer, nullable=True)
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


@db.event.listens_for(ServiceRequest, "before_insert")
@db.event.listens_for(ServiceRequest, "before_update")
def _sincronizar_cupo_pendiente(mapper, connection, target):
    """Deriva cupo_pendiente de estado antes de cada INSERT y cada UPDATE.

    Va aca y no en cada vista que cambia el estado: la columna solo existe para
    sostener el UNIQUE, y si alguien agrega mañana otro lugar donde una
    solicitud cambia de estado y se olvida de actualizarla, el freno de la
    pendiente unica se cae en silencio.

    OJO, cubre los cambios que pasan por el ORM, que hoy son todos: los eventos
    de mapper corren en el flush de una instancia, asi que un UPDATE masivo
    (Query.update(), un DELETE en bloque, SQL crudo) no los dispara y dejaria
    cupo_pendiente diciendo cualquier cosa. Hoy nadie hace eso sobre esta tabla;
    quien vaya a hacerlo tiene que escribir cupo_pendiente en el mismo UPDATE.
    Lo que no cambia es la garantia: la da el UNIQUE de la base, no este
    listener, y un bulk update que deje la columna mal seria rechazado por la
    base si genera un duplicado.

    El `or PENDIENTE` es porque los defaults de columna se aplican despues de
    este evento: una solicitud creada sin pasar `estado` todavia lo tiene en
    None aca, y su default es justamente "pendiente".
    """
    estado = target.estado or EstadosSolicitud.PENDIENTE
    target.estado = estado
    target.cupo_pendiente = 1 if estado == EstadosSolicitud.PENDIENTE else None


# El archivo de la foto se va con la fila, por cualquier camino del ORM:
# borrado directo, cascada desde Service, desde Post o desde User. El detalle,
# y el limite conocido (no cubre SQL crudo), estan en fotos_huerfanas.py.
fotos_huerfanas.registrar(ServiceRequest)
