from db import db, utcnow


class EstadosOportunidad:
    """Los tres estados por los que pasa una oportunidad.

    String con una clase de constantes y no un sa.Enum, que es como resuelve
    esto todo el proyecto (ver Roles, Categorias, Rubros, Modalidades y
    EstadosSolicitud): un Enum de verdad obliga a un ALTER TYPE para agregar un
    valor, y los estados de un flujo nuevo se mueven.

        abierta      recibe propuestas
        cerrada      acepto una propuesta, PERO puede volver a abrirse
        finalizada   se termino; sale del listado publico y no vuelve

    La diferencia entre cerrada y finalizada no es de grado: cerrada es "ya
    eligo a alguien, por ahora no busco mas", y se desanda; finalizada es
    definitiva y es la unica puerta de salida del flujo. Que sean dos estados y
    no un booleano "activa" es lo que permite decir las dos cosas.
    """

    ABIERTA = "abierta"
    CERRADA = "cerrada"
    FINALIZADA = "finalizada"

    TODOS = (ABIERTA, CERRADA, FINALIZADA)

    ETIQUETAS = {
        ABIERTA: "Abierta",
        CERRADA: "Cerrada",
        FINALIZADA: "Finalizada",
    }


class Oportunidad(db.Model):
    """Una necesidad publica: alguien que busca que le hagan un trabajo.

    Es el primer flujo del proyecto que NO cuelga de un emprendimiento. Las
    solicitudes de presupuesto (app/servicios/), los turnos (app/turnos/) y las
    busquedas de personal (app/personal/) arrancan todas en la ficha de un
    Post; esta arranca en un usuario cualquiera y la ve todo el mundo. Por eso
    el dueño es autor_id (un User) y no un post_id.

    SE LLAMA Oportunidad Y NO Solicitud A PROPOSITO. "Solicitud" ya esta
    ocupada por ServiceRequest (app/servicios/modelo_solicitud.py), que es un
    pedido PRIVADO sobre un servicio puntual de un emprendimiento. Dos cosas
    parecidas con el mismo nombre en el mismo codigo se confunden una sola vez
    y para siempre, y el que las confunde es el que llega despues.

    SIN "UNA SOLA ABIERTA POR USUARIO", al reves que BusquedaPersonal. Aca
    tener tres necesidades abiertas a la vez (el logo, el sitio, las tarjetas)
    es el caso normal y no un doble click, asi que no hay unique parcial sobre
    esta tabla. El unique parcial de esta tanda esta en propuestas, que es
    donde si hay una carrera que tapar.

    LOS TIMESTAMPS DESCRIBEN EL ESTADO ACTUAL, NO LA HISTORIA. cerrada_at se
    sella al aceptar una propuesta y vuelve a NULL al reabrir: una oportunidad
    abierta con cerrada_at cargado es una fila que se contradice, y el proximo
    que escriba un filtro le va a creer a la columna equivocada.
    finalizada_at se sella una vez y no se limpia nunca, porque de finalizada
    no se vuelve.

    No hay tabla de transiciones y hoy no hace falta: con tres estados, la fila
    contesta sola todo lo que el producto pregunta (si esta abierta, cuando
    eligio, cuando dio por terminado). Una tabla de log se gana el lugar cuando
    alguien necesite HISTORIA -- auditar quien cerro y reabrio cinco veces, o
    medir cuanto tarda en decidir --, y ese dia se agrega sin tocar estas
    columnas.
    """

    __tablename__ = "oportunidades"

    __table_args__ = (
        # Mismo criterio que ck_service_requests_respuesta_precio_positivo: el
        # texto lo valida services/precios.py y esto es la red de abajo para lo
        # que no entre por el formulario.
        #
        # NULL sigue siendo valido y no es un descuido: el presupuesto es
        # opcional porque "no se cuanto sale" es una respuesta legitima, y es
        # justamente por lo que alguien pregunta. Lo que no puede es ser cero o
        # negativo, porque eso ya es otra cosa.
        db.CheckConstraint(
            "presupuesto IS NULL OR presupuesto > 0",
            name="ck_oportunidades_presupuesto_positivo",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    # CASCADE y con nombre explicito, que desde b2b97d078fb2 es la regla del
    # proyecto: borrar un usuario se lleva sus oportunidades, y con ellas (por
    # la cascada de propuestas) las propuestas que recibio.
    autor_id = db.Column(
        db.Integer,
        db.ForeignKey(
            "users.id", ondelete="CASCADE",
            name="fk_oportunidades_autor_id_users",
        ),
        nullable=False, index=True,
    )

    titulo = db.Column(db.String(120), nullable=False)
    # String(800) y NO Text, aunque sean varios parrafos: largo_de() lee
    # columna.type.length, que en una columna Text vale None, y validar_largo
    # con ese tope revienta con un TypeError en el primer POST. Es H4, y se
    # evita eligiendo el tipo, no acordandose despues.
    descripcion = db.Column(db.String(800), nullable=False)

    # Opcional: mucha gente no tiene idea de cuanto sale lo que necesita, que
    # es parte de por que pregunta. Numeric(10, 2) y nunca float, como todos
    # los precios del proyecto; se lee con services/precios.parsear_precio.
    presupuesto = db.Column(db.Numeric(10, 2), nullable=True)
    # Opcional tambien: "para cuando lo necesito" a veces no existe. Date y no
    # DateTime porque nadie pide un logo para las 15:40.
    fecha_limite = db.Column(db.Date, nullable=True)

    estado = db.Column(
        db.String(20), nullable=False,
        default=EstadosOportunidad.ABIERTA,
        server_default=EstadosOportunidad.ABIERTA,
        index=True,
    )

    created_at = db.Column(db.DateTime, nullable=False, default=utcnow, index=True)
    # Ver "LOS TIMESTAMPS DESCRIBEN EL ESTADO ACTUAL" en el docstring.
    cerrada_at = db.Column(db.DateTime, nullable=True)
    finalizada_at = db.Column(db.DateTime, nullable=True)

    # Sin backref con cascada del lado del usuario: el borrado lo hace la base
    # con el ON DELETE CASCADE de la FK. Es lo mismo que hacen
    # ServiceRequest.cliente y Postulacion.postulante.
    autor = db.relationship("User", foreign_keys=[autor_id])

    def __repr__(self):
        return f"<Oportunidad autor_id={self.autor_id} {self.titulo!r} {self.estado}>"

    @property
    def estado_label(self):
        return EstadosOportunidad.ETIQUETAS.get(self.estado, self.estado)

    @property
    def esta_abierta(self):
        return self.estado == EstadosOportunidad.ABIERTA

    @property
    def esta_finalizada(self):
        return self.estado == EstadosOportunidad.FINALIZADA

    def serialize(self):
        return {
            "id": self.id,
            "autor_id": self.autor_id,
            "titulo": self.titulo,
            "descripcion": self.descripcion,
            # str y no float, por lo mismo que el resto de los precios: un
            # Decimal pasado por float vuelve con centavos de diferencia.
            "presupuesto": (
                str(self.presupuesto) if self.presupuesto is not None else None
            ),
            "fecha_limite": (
                self.fecha_limite.isoformat() if self.fecha_limite else None
            ),
            "estado": self.estado,
            "estado_label": self.estado_label,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "cerrada_at": self.cerrada_at.isoformat() if self.cerrada_at else None,
            "finalizada_at": (
                self.finalizada_at.isoformat() if self.finalizada_at else None
            ),
        }
