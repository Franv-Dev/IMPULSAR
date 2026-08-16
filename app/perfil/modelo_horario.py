from db import db


class Horario(db.Model):
    """Horario de atencion de un emprendedor para un dia de la semana.

    Un solo rango por dia (no hay turno mañana/tarde por separado todavia). Las
    horas son hora local de Argentina, no UTC: son una hora de reloj de la
    puerta del local, no un instante en el tiempo (ver services/horarios.py).
    """

    __tablename__ = "horarios"

    # Un dia no puede tener dos filas para el mismo usuario: sin esto, dos
    # envios del formulario casi simultaneos dejarian horarios duplicados y
    # cual gana dependeria del orden en que los devuelva la base.
    __table_args__ = (
        db.UniqueConstraint("user_id", "dia_semana", name="uq_horario_user_dia"),
    )

    id = db.Column(db.Integer, primary_key=True)
    # ondelete="CASCADE": borrar un usuario tiene que llevarse sus horarios, y
    # en MySQL el default es RESTRICT (el bug de reports/favorites/messages).
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    # 0 = lunes, igual que datetime.weekday() (ver services/horarios.DIAS).
    dia_semana = db.Column(db.Integer, nullable=False)
    abre = db.Column(db.Time, nullable=True)
    cierra = db.Column(db.Time, nullable=True)
    # Explicito y no "abre/cierra en NULL": distingue "ese dia no abrimos" de
    # "todavia no cargamos el horario".
    cerrado = db.Column(db.Boolean, nullable=False, default=False, server_default="0")

    user = db.relationship("User", backref=db.backref("horarios", cascade="all, delete-orphan"))

    def __repr__(self):
        return f"<Horario user_id={self.user_id} dia={self.dia_semana}>"

    def serialize(self):
        return {
            "dia_semana": self.dia_semana,
            "abre": self.abre.strftime("%H:%M") if self.abre else None,
            "cierra": self.cierra.strftime("%H:%M") if self.cierra else None,
            "cerrado": self.cerrado,
        }
