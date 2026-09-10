from db import db, utcnow


class EstadosTurno:
    """Estados por los que pasa un turno.

    String con una clase de constantes y no un sa.Enum ni un bool, igual que
    EstadosSolicitud y EstadosVerificacion. Contra el bool `cancelado`, que
    alcanzaria para los dos estados de hoy, gana esto por dos motivos: el
    primero es que ya hay tres modelos del proyecto que resuelven "el estado de
    una fila" asi, y el segundo es que los estados que faltan estan a la vista
    (ausente, cumplido, reprogramado) y agregarlos a un bool es cambiar la
    columna, no agregar una constante.

    No hay confirmado ni rechazado: en v1 el vendedor no confirma nada a mano.
    Reservar un slot libre YA es el turno; si no le sirve, lo cancela.
    """

    ACTIVO = "activo"
    CANCELADO = "cancelado"

    TODOS = (ACTIVO, CANCELADO)

    ETIQUETAS = {
        ACTIVO: "Activo",
        CANCELADO: "Cancelado",
    }


class QuienCancela:
    """De que lado del mostrador salio la cancelacion.

    Un string corto y no una FK a users, aunque "quien" suene a persona: las
    dos personas posibles ya estan en la fila (cliente_id de un lado, el dueño
    del emprendimiento del servicio del otro), asi que una FK no agregaria
    ningun dato y en cambio dejaria representable un tercero cancelando un
    turno ajeno, que no es un estado valido de nada.

    Lo que el panel necesita mostrar es justamente el lado ("lo cancelaste vos"
    contra "te lo cancelo el prestador"), y eso es lo que guarda.
    """

    CLIENTE = "cliente"
    VENDEDOR = "vendedor"

    TODOS = (CLIENTE, VENDEDOR)

    ETIQUETAS = {
        CLIENTE: "el cliente",
        VENDEDOR: "el prestador",
    }


class Turno(db.Model):
    """Una hora reservada por un cliente sobre un servicio puntual.

    Contra un Service y no contra un User: la duracion, y si se toman turnos o
    no, son del servicio (ver Service.turnos_habilitados). Alguien que corta
    pelo y ademas alquila un salon no atiende las dos cosas en tramos iguales.

    FECHA Y HORA LOCALES, SEPARADAS. `fecha` es Date y `hora_inicio`/`hora_fin`
    son Time, nunca un DateTime, por lo mismo que Event.fecha y que Horario.abre
    (ver services/horarios.py): un turno es "el martes a las 15:00" en el reloj
    de la puerta del local, no un instante en UTC. Las columnas DateTime del
    proyecto guardan UTC, y mezclar las dos cosas hace que un turno de las 15
    figure a las 18.

    HORA_FIN SE CONGELA AL CREAR. Sale de hora_inicio mas la duracion que el
    Service tenia EN ESE MOMENTO, y se guarda; no se recalcula despues. Si el
    vendedor pasa sus turnos de 30 a 45 minutos, los que ya estaban reservados
    mantienen el rango con el que el cliente los saco. Derivarlo en vivo de
    Service.duracion_turno_minutos haria que cambiar la duracion le mueva la
    hora de salida a gente que ya tiene el turno agendado.

    NO SE PUEDE RESERVAR DOS VECES EL MISMO SLOT, y lo garantiza la base. Es la
    misma mecanica que la pendiente unica de ServiceRequest y
    VerificationRequest, y aca importa mas que en las dos: chequear "esta
    libre?" antes de insertar deja una ventana entre el SELECT y el INSERT, y
    dos clientes que entran juntos al ultimo slot del viernes pasan los dos el
    chequeo y se llevan los dos el mismo horario. La vista igual va a chequear
    antes, pero para dar un mensaje lindo, no para garantizar nada.

    La constraint es UNIQUE(service_id, fecha, hora_inicio, cupo_activo), donde
    cupo_activo vale 1 mientras el turno esta activo y NULL cuando se cancela.
    En los dos motores (MySQL y SQLite) un UNIQUE ignora las filas con NULL, asi
    que la regla aplica solo a los turnos vivos: un slot cancelado vuelve a
    quedar libre, y el mismo horario se puede reservar y cancelar todas las
    veces que haga falta. Es la forma portable de escribir el "unique parcial"
    que MySQL no tiene, y es el cuarto lugar del proyecto donde se resuelve asi
    (cupo_pendiente en ServiceRequest y VerificationRequest, clave_pendiente en
    Report).

    La columna se llama cupo_activo y no cupo_pendiente por una sola razon: lo
    que la prende aca es el estado "activo", y "pendiente" seria mentira, porque
    un turno no espera que nadie lo apruebe (ver EstadosTurno). La mecanica es
    identica.

    EL UNIQUE COMPARA hora_inicio EXACTA, no rangos superpuestos. Alcanza porque
    todos los slots de un servicio se cortan del mismo horario con la misma
    duracion, asi que dos turnos del mismo servicio y dia o arrancan a la misma
    hora o no se tocan. Lo que NO cubre, y es a proposito, es el solapamiento
    entre servicios distintos del mismo vendedor: si tiene "corte" de 30 y
    "color" de 90, la base lo deja tomar los dos a las 15:00. Queda anotado como
    limite conocido de v1; resolverlo pide comparar rangos, y eso ya no lo hace
    un UNIQUE.
    """

    __tablename__ = "turnos"

    __table_args__ = (
        # Ver "NO SE PUEDE RESERVAR DOS VECES EL MISMO SLOT" en el docstring:
        # el que cierra de verdad la ventana entre el chequeo y el INSERT.
        db.UniqueConstraint(
            "service_id", "fecha", "hora_inicio", "cupo_activo",
            name="uq_turnos_slot_activo",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    # ondelete="CASCADE" y con nombre explicito, igual que el resto de las FK
    # nuevas: si se borra el servicio, los turnos sobre el no pueden quedar
    # apuntando a nada. Sin el CASCADE, MySQL usa RESTRICT y borrar el servicio
    # falla con IntegrityError.
    service_id = db.Column(
        db.Integer,
        db.ForeignKey(
            "services.id", ondelete="CASCADE",
            name="fk_turnos_service_id_services",
        ),
        nullable=False, index=True,
    )
    # CASCADE tambien aca: borrar un usuario se lleva sus turnos, que es la
    # regla del proyecto desde b2b97d078fb2.
    cliente_id = db.Column(
        db.Integer,
        db.ForeignKey(
            "users.id", ondelete="CASCADE",
            name="fk_turnos_cliente_id_users",
        ),
        nullable=False, index=True,
    )

    # Indexada porque toda consulta de turnos filtra por dia: la agenda del
    # vendedor, "mis turnos" del cliente y el corte de slots de una fecha.
    fecha = db.Column(db.Date, nullable=False, index=True)
    hora_inicio = db.Column(db.Time, nullable=False)
    # Congelada al crear, ver el docstring. NOT NULL: un turno sin hora de fin
    # no se puede pintar en ninguna agenda.
    hora_fin = db.Column(db.Time, nullable=False)

    estado = db.Column(
        db.String(20), nullable=False,
        default=EstadosTurno.ACTIVO,
        server_default=EstadosTurno.ACTIVO,
        index=True,
    )
    # Vale 1 si estado == activo, y NULL si no. No se toca a mano en ningun
    # lado: lo mantiene el listener de abajo, para que no pueda quedar
    # desincronizado de `estado` (que es de donde sale su valor).
    cupo_activo = db.Column(db.Integer, nullable=True)
    # De que lado salio la cancelacion. NULL mientras el turno esta activo, que
    # es lo correcto: todavia no lo cancelo nadie. Lo escribe quien cancela.
    cancelado_por = db.Column(db.String(20), nullable=True)

    created = db.Column(db.DateTime, nullable=False, default=utcnow)

    # cascade="all, delete-orphan" en el lado del servicio: la FK ya borra en la
    # base, pero sin esto el ORM intenta dejar las filas huerfanas poniendo
    # service_id en NULL cuando se borra un Service desde la sesion, y la
    # columna es NOT NULL. Mismo caso que solicitudes y verificaciones.
    servicio = db.relationship(
        "Service",
        backref=db.backref("turnos", cascade="all, delete-orphan"),
    )
    # Sin backref con cascada del lado del usuario, al reves que el servicio:
    # aca el borrado lo hace la base con el ON DELETE CASCADE de la FK. Es lo
    # mismo que hace ServiceRequest.cliente.
    cliente = db.relationship("User", foreign_keys=[cliente_id])

    def __repr__(self):
        return (
            f"<Turno service_id={self.service_id} {self.fecha} "
            f"{self.hora_inicio} {self.estado}>"
        )

    @property
    def estado_label(self):
        return EstadosTurno.ETIQUETAS.get(self.estado, self.estado)

    @property
    def cancelado_por_label(self):
        """"el cliente" / "el prestador", o cadena vacia si sigue activo."""
        return QuienCancela.ETIQUETAS.get(self.cancelado_por, "")

    @property
    def esta_activo(self):
        return self.estado == EstadosTurno.ACTIVO

    def serialize(self):
        return {
            "id": self.id,
            "service_id": self.service_id,
            "cliente_id": self.cliente_id,
            "fecha": self.fecha.isoformat() if self.fecha else None,
            # %H:%M y no isoformat(), igual que Event.hora y Horario.abre: los
            # segundos no significan nada en un turno y ensucian la pantalla.
            "hora_inicio": (
                self.hora_inicio.strftime("%H:%M") if self.hora_inicio else None
            ),
            "hora_fin": self.hora_fin.strftime("%H:%M") if self.hora_fin else None,
            "estado": self.estado,
            "estado_label": self.estado_label,
            "cancelado_por": self.cancelado_por,
            "created": self.created.isoformat() if self.created else None,
        }


@db.event.listens_for(Turno, "before_insert")
@db.event.listens_for(Turno, "before_update")
def _sincronizar_cupo_activo(mapper, connection, target):
    """Deriva cupo_activo de estado antes de cada INSERT y cada UPDATE.

    Va aca y no en cada vista que cancela un turno, por lo mismo que en
    ServiceRequest, VerificationRequest y Report: la columna solo existe para
    sostener el UNIQUE, y si alguien agrega mañana otro lugar donde un turno se
    cancela y se olvida de actualizarla, el freno de la doble reserva se cae en
    silencio. Y se caeria del peor lado: cupo_activo quedaria en 1 sobre un
    turno cancelado, dejando ese slot ocupado para siempre.

    OJO, cubre los cambios que pasan por el ORM, que hoy son todos: los eventos
    de mapper corren en el flush de una instancia, asi que un UPDATE masivo
    (Query.update(), SQL crudo) no los dispara y dejaria cupo_activo diciendo
    cualquier cosa. Quien vaya a hacer uno tiene que escribir cupo_activo en el
    mismo UPDATE. Lo que no cambia es la garantia: la da el UNIQUE de la base,
    no este listener.

    El `or ACTIVO` es porque los defaults de columna se aplican despues de este
    evento: un turno creado sin pasar `estado` todavia lo tiene en None aca, y
    su default es justamente "activo".
    """
    estado = target.estado or EstadosTurno.ACTIVO
    target.estado = estado
    target.cupo_activo = 1 if estado == EstadosTurno.ACTIVO else None
