from db import db, utcnow


class Report(db.Model):
    """Reporte de contenido inapropiado: apunta a un emprendimiento o a una
    reseña, nunca a los dos ni a ninguno (ver el CheckConstraint).

    UN SOLO REPORTE PENDIENTE por usuario y objetivo: uno sin resolver ya
    alcanza para que el admin lo vea. Eso lo garantiza la base y no la vista:
    chequear antes de insertar deja una ventana entre el SELECT y el INSERT, y
    dos requests que entran juntos (el doble click que manda dos POST, o dos
    pestañas) pasan los dos el chequeo y guardan los dos. La vista igual chequea
    antes, pero para dar un mensaje lindo, no para garantizar nada.

    POR QUE HACE FALTA LA COLUMNA CENTINELA. El UNIQUE natural seria
    (reporter_id, post_id, review_id, <lo que marque pendiente>), y no sirve:
    post_id y review_id son excluyentes, asi que cualquier tupla que los incluya
    lleva siempre un NULL, y tanto MySQL como SQLite eximen del UNIQUE a las
    filas con NULL. La constraint existiria y no frenaria nada.

    clave_pendiente colapsa las dos FK en un valor solo: "p<post_id>" o
    "r<review_id>" mientras el reporte esta sin resolver, y NULL cuando se
    resuelve. El UNIQUE es (reporter_id, clave_pendiente), y ahi el NULL pasa a
    ser deliberado: exime justamente a los resueltos, que si pueden repetirse
    (que el admin resuelva un reporte no le prohibe al usuario volver a
    reportar el mismo contenido si reincide). Es el mismo "unique parcial" que
    en app/servicios escribe cupo_pendiente, con una vuelta de mas porque aca
    el objetivo esta partido en dos columnas.
    """

    __tablename__ = "reports"

    __table_args__ = (
        db.CheckConstraint(
            "(post_id IS NOT NULL) != (review_id IS NOT NULL)",
            name="ck_report_target_xor",
        ),
        # Ver "UN SOLO REPORTE PENDIENTE" en el docstring: el que cierra de
        # verdad la ventana entre el chequeo y el INSERT.
        db.UniqueConstraint(
            "reporter_id", "clave_pendiente",
            name="uq_reports_pendiente",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    # ondelete="CASCADE": la denuncia se va con quien la hizo (ver b2b97d078fb2).
    # Si estaba pendiente, desaparece de la cola del admin sin resolver.
    reporter_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE", name="fk_reports_reporter_id_users"),
        nullable=False, index=True,
    )
    # ondelete="CASCADE": sin esto, MySQL usa RESTRICT por default y borrar un
    # post o resenia que alguna vez se reporto (aunque el reporte ya este
    # resuelto) falla con IntegrityError. El reporte no tiene sentido sin su
    # objetivo, asi que lo correcto es que se borre junto con el.
    post_id = db.Column(db.Integer, db.ForeignKey("posts.id", ondelete="CASCADE"), nullable=True, index=True)
    review_id = db.Column(db.Integer, db.ForeignKey("reviews.id", ondelete="CASCADE"), nullable=True, index=True)

    reason = db.Column(db.Text, nullable=False)
    created = db.Column(db.DateTime, nullable=False, default=utcnow)

    # Lo marca el admin desde el panel cuando ya tomo una decision (ver
    # views/admin.py resolve_report). No implica que se haya borrado nada:
    # puede resolverse dejando el contenido tal cual.
    resolved = db.Column(db.Boolean, nullable=False, default=False, server_default="0")
    resolved_at = db.Column(db.DateTime, nullable=True)

    # Derivada, no se escribe a mano en ningun lado: la mantiene el listener de
    # abajo. 32 caracteres sobran para una letra mas un id.
    clave_pendiente = db.Column(db.String(32), nullable=True)

    reporter = db.relationship("User")
    post = db.relationship("Post")
    review = db.relationship("Review")

    def __repr__(self):
        objetivo = f"post_id={self.post_id}" if self.post_id else f"review_id={self.review_id}"
        return f"<Report {objetivo} reporter_id={self.reporter_id}>"

    def serialize(self):
        return {
            "id": self.id,
            "reporter_id": self.reporter_id,
            "post_id": self.post_id,
            "review_id": self.review_id,
            "reason": self.reason,
            "created": self.created.isoformat() if self.created else None,
            "resolved": self.resolved,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
        }


@db.event.listens_for(Report, "before_insert")
@db.event.listens_for(Report, "before_update")
def _sincronizar_clave_pendiente(mapper, connection, target):
    """Deriva clave_pendiente del objetivo y del estado, antes de cada escritura.

    Va aca y no en cada vista que resuelve un reporte: la columna solo existe
    para sostener el UNIQUE, y si alguien agrega mañana otro lugar donde un
    reporte se resuelve y se olvida de actualizarla, el freno del reporte unico
    se cae en silencio.

    OJO, cubre los cambios que pasan por el ORM, que hoy son todos: los eventos
    de mapper corren en el flush de una instancia, asi que un UPDATE masivo
    (Query.update(), SQL crudo) no los dispara y dejaria clave_pendiente
    diciendo cualquier cosa. Hoy nadie hace eso sobre esta tabla; quien vaya a
    hacerlo tiene que escribir clave_pendiente en el mismo UPDATE. Lo que no
    cambia es la garantia: la da el UNIQUE de la base, no este listener.

    El `or False` es porque los defaults de columna se aplican despues de este
    evento: un reporte creado sin pasar `resolved` todavia lo tiene en None aca,
    y su default es justamente False.
    """
    resolved = target.resolved or False
    target.resolved = resolved

    if resolved:
        target.clave_pendiente = None
    elif target.post_id is not None:
        target.clave_pendiente = f"p{target.post_id}"
    elif target.review_id is not None:
        target.clave_pendiente = f"r{target.review_id}"
    else:
        # Sin objetivo no hay clave posible. No deberia llegar aca: el
        # CheckConstraint del XOR rechaza la fila igual, y con mejor mensaje.
        target.clave_pendiente = None
