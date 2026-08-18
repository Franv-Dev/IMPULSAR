from db import db, utcnow


class EstadosVerificacion:
    """Estados por los que pasa un pedido de verificacion.

    String con una clase de constantes y no un sa.Enum, igual que
    EstadosSolicitud, Roles y Categorias: un Enum de verdad obliga a un ALTER
    TYPE para agregar un estado.

    Aca si hay aprobada y rechazada, al reves que en EstadosSolicitud, y la
    diferencia es real: una solicitud de presupuesto se archiva sin que nadie
    haya decidido nada, mientras que una verificacion es exactamente una
    decision del admin, y cual fue cambia lo que ve el visitante.
    """

    PENDIENTE = "pendiente"
    APROBADA = "aprobada"
    RECHAZADA = "rechazada"

    TODOS = (PENDIENTE, APROBADA, RECHAZADA)

    ETIQUETAS = {
        PENDIENTE: "Pendiente",
        APROBADA: "Aprobada",
        RECHAZADA: "Rechazada",
    }


class VerificationRequest(db.Model):
    """El prestador sube su matricula o certificado y un admin la revisa.

    Nombre de clase en ingles y columnas en español, que es como esta escrito
    el resto del paquete (Service, ServiceRequest): no se cambia el criterio en
    el medio.

    POR SERVICIO Y NO POR USUARIO: cuelga de Service, igual que
    Service.verificado. La habilitacion es por oficio, y un electricista puede
    tener matricula de electricidad y no de gas. Un pedido por usuario le daria
    el sello a los dos.

    QUIEN ESCRIBE QUE: el prestador crea la fila con la foto y nada mas; el
    estado, resuelto_at, motivo_rechazo y el Service.verificado del otro lado
    los escribe unicamente el admin (ver views/admin.py). Si el dueño pudiera
    tocar cualquiera de esas cosas, la verificacion no significaria nada.

    OJO con la foto, mismo caso que ServiceRequest y con mas motivo: la
    privacidad es de la PAGINA, no del archivo. La imagen se guarda en
    static/uploads como todas las demas y Flask la sirve sin ningun chequeo de
    permiso, asi que quien tenga la URL la ve sin sesion. No es enumerable (el
    nombre lleva un uuid, ver services/uploads.py), pero aca lo que se sube es
    un documento con nombre y numero de matricula, que es mas sensible que la
    foto de una canilla rota. Si alguna vez se sirven los uploads por una ruta
    propia con chequeo de permiso, esta es la primera que hay que mudar.

    UNA SOLA PENDIENTE por servicio: una sin resolver ya alcanza para que el
    admin la vea, y sin el freno un doble click deja dos filas identicas en la
    cola. Lo garantiza la base y no la vista: chequear antes de insertar deja
    una ventana entre el SELECT y el INSERT, y dos requests que entran juntos
    (el doble click que manda dos POST, o dos pestañas) pasan los dos el
    chequeo y guardan los dos. La vista igual chequea antes, pero para dar un
    mensaje lindo, no para garantizar nada.

    POR QUE LA COLUMNA CENTINELA TAMBIEN ACA. A diferencia de Report, el
    objetivo es una sola FK (service_id) y no un XOR de dos, asi que no hay
    nada que colapsar: cupo_pendiente vale siempre 1 o NULL, sin la vuelta de
    la letra mas el id que necesita clave_pendiente. Pero la columna sigue
    haciendo falta, y no por consistencia: sin ella no hay constraint posible.
    El UNIQUE natural seria UNIQUE(service_id) a secas, y eso prohibiria para
    siempre un segundo pedido, incluso despues de que el admin rechazo el
    primero porque la foto no se leia. El unique parcial de verdad ("WHERE
    estado = pendiente") existe en Postgres pero no en MySQL, asi que la regla
    se escribe con la columna auxiliar: vale 1 mientras el pedido esta
    pendiente y NULL cuando se resolvio, y los dos motores eximen del UNIQUE a
    las filas con NULL. Queda el mismo mecanismo que cupo_pendiente en
    ServiceRequest y clave_pendiente en Report, que es el tercer lugar del
    proyecto donde se resuelve esto.
    """

    __tablename__ = "verification_requests"

    __table_args__ = (
        # Ver "UNA SOLA PENDIENTE" en el docstring: el que cierra de verdad la
        # ventana entre el chequeo y el INSERT.
        db.UniqueConstraint(
            "service_id", "cupo_pendiente",
            name="uq_verification_requests_pendiente",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    # ondelete="CASCADE" y con nombre explicito, igual que el resto de las FK
    # nuevas: si se borra el servicio, el pedido de verificacion sobre el no
    # puede quedar apuntando a nada.
    service_id = db.Column(
        db.Integer,
        db.ForeignKey(
            "services.id", ondelete="CASCADE",
            name="fk_verification_requests_service_id_services",
        ),
        nullable=False, index=True,
    )

    # Nombre de archivo, igual que ServiceRequest.foto y Post.image. Nullable
    # en la base por lo mismo que alla (la fila se puede querer conservar
    # aunque el archivo se limpie), pero la vista no deja crear un pedido sin
    # foto: sin el documento no hay nada que revisar.
    foto = db.Column(db.String(100), nullable=True)

    estado = db.Column(
        db.String(20), nullable=False,
        default=EstadosVerificacion.PENDIENTE,
        server_default=EstadosVerificacion.PENDIENTE,
        index=True,
    )
    # Vale 1 si estado == pendiente, y NULL si no. No se toca a mano en ningun
    # lado: lo mantiene el listener de abajo, para que no pueda quedar
    # desincronizado de `estado` (que es de donde sale su valor).
    cupo_pendiente = db.Column(db.Integer, nullable=True)

    # Por que no paso, para que el prestador sepa que corregir ("la foto no se
    # lee", "esa matricula esta vencida"). Nullable porque solo existe cuando
    # el admin rechaza y ademas quiso explicarlo. Mismo espiritu que
    # Report.resolved_at: lo llena el admin al decidir, no el que abrio el caso.
    motivo_rechazo = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, default=utcnow, index=True)
    resuelto_at = db.Column(db.DateTime, nullable=True)

    # cascade="all, delete-orphan" en el lado del servicio: la FK ya borra en
    # la base, pero sin esto el ORM intenta dejar las filas huerfanas poniendo
    # service_id en NULL cuando se borra un Service desde la sesion, y la
    # columna es NOT NULL. Mismo caso que solicitudes, imagenes y productos.
    servicio = db.relationship(
        "Service",
        backref=db.backref("verificaciones", cascade="all, delete-orphan"),
    )

    def __repr__(self):
        return f"<VerificationRequest service_id={self.service_id} {self.estado}>"

    @property
    def estado_label(self):
        return EstadosVerificacion.ETIQUETAS.get(self.estado, self.estado)

    def serialize(self):
        return {
            "id": self.id,
            "service_id": self.service_id,
            "foto": self.foto,
            "estado": self.estado,
            "estado_label": self.estado_label,
            "motivo_rechazo": self.motivo_rechazo,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "resuelto_at": self.resuelto_at.isoformat() if self.resuelto_at else None,
        }


@db.event.listens_for(VerificationRequest, "before_insert")
@db.event.listens_for(VerificationRequest, "before_update")
def _sincronizar_cupo_pendiente(mapper, connection, target):
    """Deriva cupo_pendiente de estado antes de cada INSERT y cada UPDATE.

    Va aca y no en cada vista que cambia el estado, por lo mismo que en
    ServiceRequest y en Report: la columna solo existe para sostener el UNIQUE,
    y si alguien agrega mañana otro lugar donde un pedido se resuelve y se
    olvida de actualizarla, el freno de la pendiente unica se cae en silencio.

    OJO, cubre los cambios que pasan por el ORM, que hoy son todos: los eventos
    de mapper corren en el flush de una instancia, asi que un UPDATE masivo
    (Query.update(), SQL crudo) no los dispara y dejaria cupo_pendiente
    diciendo cualquier cosa. Lo que no cambia es la garantia: la da el UNIQUE
    de la base, no este listener.

    El `or PENDIENTE` es porque los defaults de columna se aplican despues de
    este evento: un pedido creado sin pasar `estado` todavia lo tiene en None
    aca, y su default es justamente "pendiente".
    """
    estado = target.estado or EstadosVerificacion.PENDIENTE
    target.estado = estado
    target.cupo_pendiente = 1 if estado == EstadosVerificacion.PENDIENTE else None
