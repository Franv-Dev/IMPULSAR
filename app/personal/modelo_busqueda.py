from db import db, utcnow


class Modalidades:
    """Como se trabaja en el puesto.

    Catalogo fijo y no texto libre, por lo mismo que Rubros en
    app/servicios/modelo.py: sobre la modalidad se va a filtrar, y con texto
    libre "remoto", "Remoto" y "a distancia" son tres modalidades distintas.

    Mismo formato que Rubros, Categorias y Roles: los strings viven en un solo
    lugar y las etiquetas para mostrar tambien. String con una clase de
    constantes y no un sa.Enum, igual que todo el proyecto: un Enum de verdad
    obliga a un ALTER TYPE para agregar un valor.
    """

    PRESENCIAL = "presencial"
    REMOTO = "remoto"
    MIXTO = "mixto"

    TODAS = (PRESENCIAL, REMOTO, MIXTO)

    ETIQUETAS = {
        PRESENCIAL: "Presencial",
        REMOTO: "Remoto",
        MIXTO: "Mixto",
    }


class BusquedaPersonal(db.Model):
    """Un aviso de "busco personal" de un emprendimiento.

    El emprendedor lo prende desde su panel, completa puesto, modalidad y una
    descripcion corta, y desde ese momento la seccion aparece en la ficha
    publica del emprendimiento. Lo apaga cuando quiere: la seccion deja de
    mostrarse y las postulaciones YA RECIBIDAS NO SE BORRAN, que es todo el
    motivo de que esto sea una tabla y no cuatro columnas en posts.

    UNA SOLA ACTIVA POR EMPRENDIMIENTO, y lo garantiza la base y no la vista:
    chequear antes de insertar deja una ventana entre el SELECT y el INSERT por
    la que pasan dos requests simultaneos (el doble click que manda dos POST, o
    dos pestañas). La constraint es UNIQUE(post_id, cupo_activa), donde
    cupo_activa vale 1 mientras la busqueda esta activa y NULL cuando no lo
    esta: en los dos motores un UNIQUE ignora las filas con NULL, asi que la
    regla aplica solo a las activas y las cerradas pueden repetirse todas las
    veces que haga falta. Es el mismo unique parcial portable que
    service_requests.cupo_pendiente, reusado y no reinventado.

    REABRIR ES UNA FILA NUEVA, NUNCA activa=True sobre la vieja. Parece un
    detalle de implementacion y no lo es: el unique de postulaciones es
    (busqueda_id, postulante_id), asi que si se reactivara la fila cerrada,
    todo el que se habia postulado a la busqueda anterior quedaria bloqueado
    de postularse a la nueva -- con un IntegrityError que ademas se leeria
    como "ya te postulaste" cuando la persona nunca vio este aviso. Cerrar
    sella cerrada_at y ahi termina la vida de esa fila; lo que sigue es otra
    busqueda, con su propia lista de postulantes.

    vistas_sin_postulacion es una señal DEBIL Y ANONIMA: cuenta cuantas veces
    alguien abrio el formulario y lo cerro sin mandarlo, y no guarda quien.
    No hay tabla de "quien vio esto", a proposito. Se incrementa con un UPDATE
    atomico (ver consultas.contar_vista_sin_postulacion) y nunca leyendo en
    Python y guardando, que perderia una de dos visitas simultaneas.
    """

    __tablename__ = "busquedas_personal"

    __table_args__ = (
        # Ver "UNA SOLA ACTIVA" en el docstring: es el que cierra de verdad la
        # ventana entre el chequeo y el INSERT.
        db.UniqueConstraint(
            "post_id", "cupo_activa", name="uq_busquedas_personal_activa",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    # ondelete="CASCADE" y con nombre explicito, igual que el resto de las FK
    # nuevas: si se borra el emprendimiento, sus busquedas no pueden quedar
    # apuntando a nada.
    post_id = db.Column(
        db.Integer,
        db.ForeignKey(
            "posts.id", ondelete="CASCADE",
            name="fk_busquedas_personal_post_id_posts",
        ),
        nullable=False, index=True,
    )

    puesto = db.Column(db.String(120), nullable=False)
    modalidad = db.Column(db.String(20), nullable=False)
    # String(500) y NO Text, aunque sea un parrafo: largo_de() lee
    # columna.type.length, que en una columna Text vale None, y validar_largo
    # con ese tope revienta con un TypeError en el primer POST. Es H4, y se
    # evita eligiendo el tipo, no acordandose despues.
    #
    # Obligatoria, al reves que Service.descripcion: es lo unico que el
    # postulante lee antes de decidir si le interesa el puesto.
    descripcion = db.Column(db.String(500), nullable=False)

    activa = db.Column(
        db.Boolean, nullable=False, default=True, server_default="1", index=True,
    )
    # Vale 1 si activa, y NULL si no. No se toca a mano en ningun lado: lo
    # mantiene el listener de abajo, igual que cupo_pendiente en
    # service_requests, para que no pueda quedar desincronizado de `activa`.
    cupo_activa = db.Column(db.Integer, nullable=True)

    # La señal debil. NOT NULL con server_default para que ninguna fila quede
    # en NULL y rompa el +1.
    vistas_sin_postulacion = db.Column(
        db.Integer, nullable=False, default=0, server_default="0",
    )

    created_at = db.Column(db.DateTime, nullable=False, default=utcnow, index=True)
    # Se sella al apagar el toggle. Ordena las busquedas pasadas en la bandeja
    # y deja leer en la fila misma si sigue abierta o no.
    cerrada_at = db.Column(db.DateTime, nullable=True)

    # cascade="all, delete-orphan" del lado del post: la FK ya borra en la
    # base, pero sin esto el ORM intenta dejar las filas huerfanas poniendo
    # post_id en NULL cuando se borra un Post desde la sesion, y la columna es
    # NOT NULL. Mismo caso que imagenes, eventos, productos y servicios.
    post = db.relationship(
        "Post",
        backref=db.backref("busquedas_personal", cascade="all, delete-orphan"),
    )

    def __repr__(self):
        estado = "activa" if self.activa else "cerrada"
        return f"<BusquedaPersonal post_id={self.post_id} {self.puesto!r} {estado}>"

    @property
    def modalidad_label(self):
        return Modalidades.ETIQUETAS.get(self.modalidad, self.modalidad)

    def serialize(self):
        return {
            "id": self.id,
            "post_id": self.post_id,
            "puesto": self.puesto,
            "modalidad": self.modalidad,
            "modalidad_label": self.modalidad_label,
            "descripcion": self.descripcion,
            "activa": self.activa,
            "vistas_sin_postulacion": self.vistas_sin_postulacion,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "cerrada_at": self.cerrada_at.isoformat() if self.cerrada_at else None,
        }


@db.event.listens_for(BusquedaPersonal, "before_insert")
@db.event.listens_for(BusquedaPersonal, "before_update")
def _sincronizar_cupo_activa(mapper, connection, target):
    """Deriva cupo_activa de activa antes de cada INSERT y cada UPDATE.

    Va aca y no en cada vista que prende o apaga el toggle: la columna solo
    existe para sostener el UNIQUE, y si mañana aparece otro lugar donde una
    busqueda cambia de estado y se olvida de actualizarla, el freno de la
    unica activa se cae en silencio. Es el mismo listener, y por el mismo
    motivo, que _sincronizar_cupo_pendiente en app/servicios/modelo_solicitud.py.

    Cubre los cambios que pasan por el ORM, que hoy son todos: los eventos de
    mapper corren en el flush de una instancia, asi que un UPDATE masivo
    (Query.update(), SQL crudo) no los dispara. Lo que no cambia es la
    garantia: la da el UNIQUE de la base, no este listener.

    El `is None` es porque los defaults de columna se aplican DESPUES de este
    evento: una busqueda creada sin pasar `activa` todavia la tiene en None
    aca, y su default es True.
    """
    if target.activa is None:
        target.activa = True
    target.cupo_activa = 1 if target.activa else None
