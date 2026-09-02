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
        # NO dice "abre < cierra", y no es un olvido: un bar de 20:00 a 02:00
        # cierra al dia siguiente, y ese cruce de medianoche lo contemplan tanto
        # services/horarios.esta_abierto como el filtro "Abierto ahora" del
        # listado. Pedir abre < cierra rechazaria todos los horarios nocturnos.
        #
        # Lo que si vale siempre, cruce o no, es que las dos horas no sean la
        # misma: "de 09:00 a 09:00" no se puede leer (¿cerrado siempre o
        # abierto las 24 horas?) y los dos lectores del horario lo toman como
        # cerrado, sin avisar. El formulario ya lo rechaza con un mensaje; esto
        # es la red de abajo, igual que ck_review_rating.
        #
        # Con una de las dos horas en NULL la comparacion da desconocido y el
        # CHECK pasa, que es lo correcto: ese es el dia cerrado, y de que las
        # dos esten cargadas o ninguna se ocupa el CHECK de abajo.
        db.CheckConstraint("abre <> cierra", name="ck_horarios_abre_distinto_de_cierra"),
        # Un dia abierto tiene las dos horas. Lo garantiza en cada escritura
        # reglas.horario_del_dia (un dia sin horas se guarda como cerrado), asi
        # que una fila con cerrado=0 y las horas en NULL no sale de la app: es
        # un dia a medio cargar, que esta_abierto() saltea en silencio y que la
        # pagina muestra como si no hubiera horario.
        #
        # Ojo que es un CHECK con condicion, y MySQL recien los valida desde
        # 8.0.16 (mismo limite que anota Service.duracion_turno_minutos).
        db.CheckConstraint(
            "cerrado <> 0 OR (abre IS NOT NULL AND cierra IS NOT NULL)",
            name="ck_horarios_dia_abierto_con_horas",
        ),
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
