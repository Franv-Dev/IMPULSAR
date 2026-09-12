from db import db, utcnow


class Postulacion(db.Model):
    """Lo que manda alguien que se postula a una busqueda de personal.

    Texto estructurado y nada mas: no hay CV adjunto en esta version, a
    proposito. Un PDF traeria subida de archivos, control de acceso propio y
    borrado de huerfanos, que es una tanda entera; los cuatro campos de aca
    alcanzan para que el emprendedor decida si abre la conversacion.

    CUELGA DE UNA BUSQUEDA PUNTUAL, no del emprendimiento ni del usuario. No
    es un CV reusable: la misma persona puede postularse a la busqueda de
    marzo y a la de septiembre del mismo emprendimiento, y son dos
    postulaciones distintas con textos distintos. Por eso el unique es
    (busqueda_id, postulante_id) y no (post_id, postulante_id).

    NOMBRE Y CONTACTO SON UN SNAPSHOT, no una lectura en vivo del User. El
    formulario los prellena desde el perfil, pero lo que se guarda es lo que la
    persona mando ese dia: si mañana cambia su telefono, la postulacion que el
    emprendedor ya leyo no puede cambiar sola debajo suyo. El que quiera el
    dato de hoy tiene el enlace al perfil y el chat.

    PRIVACIDAD: una postulacion la ven dos personas, quien la mando y el dueño
    del emprendimiento del que cuelga la busqueda. Nadie mas, ni otro
    emprendedor ni un admin. Eso se hace cumplir en las vistas, del lado del
    servidor (ver reglas.es_dueño_de_la_busqueda), nunca escondiendo el HTML.
    """

    __tablename__ = "postulaciones"

    __table_args__ = (
        # Una postulacion por persona y por busqueda. Unique entero y no
        # parcial como el de busquedas_personal: aca no hay ningun estado que
        # libere el cupo, postularse dos veces a la misma busqueda es
        # duplicado y punto. La vista igual chequea antes, pero para dar un
        # mensaje lindo, no para garantizar nada: entre el SELECT y el INSERT
        # hay una ventana y esto es lo que la cierra.
        db.UniqueConstraint(
            "busqueda_id", "postulante_id", name="uq_postulaciones_una_por_busqueda",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    busqueda_id = db.Column(
        db.Integer,
        db.ForeignKey(
            "busquedas_personal.id", ondelete="CASCADE",
            name="fk_postulaciones_busqueda_id_busquedas_personal",
        ),
        nullable=False, index=True,
    )
    # CASCADE tambien aca, que desde b2b97d078fb2 es la regla del proyecto y no
    # la excepcion: borrar un usuario se lleva sus postulaciones.
    postulante_id = db.Column(
        db.Integer,
        db.ForeignKey(
            "users.id", ondelete="CASCADE",
            name="fk_postulaciones_postulante_id_users",
        ),
        nullable=False, index=True,
    )

    # Los cuatro campos del formulario. Todos String(n) y NINGUNO Text: sobre
    # los cuatro corre validar_largo, y largo_de() sobre una columna Text
    # devuelve None (H4). El tipo es parte de la validacion, no un detalle.
    nombre = db.Column(db.String(100), nullable=False)
    contacto = db.Column(db.String(120), nullable=False)
    experiencia = db.Column(db.String(600), nullable=False)
    disponibilidad = db.Column(db.String(120), nullable=False)

    created_at = db.Column(db.DateTime, nullable=False, default=utcnow, index=True)

    # Del lado de la busqueda si va cascada en el ORM, por lo mismo que el
    # resto: la FK ya borra en la base, pero sin esto el ORM intentaria dejar
    # las filas huerfanas poniendo busqueda_id en NULL, y la columna es NOT NULL.
    busqueda = db.relationship(
        "BusquedaPersonal",
        backref=db.backref("postulaciones", cascade="all, delete-orphan"),
    )
    # Sin backref del lado del usuario, al reves que la busqueda: aca el
    # borrado lo hace la base con el ON DELETE CASCADE de la FK. Es lo mismo
    # que hace ServiceRequest.cliente.
    postulante = db.relationship("User", foreign_keys=[postulante_id])

    def __repr__(self):
        return (
            f"<Postulacion busqueda_id={self.busqueda_id} "
            f"postulante_id={self.postulante_id}>"
        )

    def serialize(self):
        return {
            "id": self.id,
            "busqueda_id": self.busqueda_id,
            "postulante_id": self.postulante_id,
            "nombre": self.nombre,
            "contacto": self.contacto,
            "experiencia": self.experiencia,
            "disponibilidad": self.disponibilidad,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
