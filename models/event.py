from db import db, utcnow


class Event(db.Model):
    """Un evento o feria que un emprendimiento anuncia.

    Es informacion con fecha, no una reserva: no hay cupo, ni inscripcion, ni
    disponibilidad. Un cartel que dice "el sabado estamos en la feria de la
    plaza".

    La fecha es hora local de Argentina, igual que los horarios de atencion y
    por la misma razon: una feria es "el sabado a las 10" en el reloj de la
    puerta del local, no un instante en UTC (ver services/eventos.py). Por eso
    `fecha` es Date y no DateTime, y la hora va aparte.
    """

    __tablename__ = "events"

    id = db.Column(db.Integer, primary_key=True)
    # ondelete="CASCADE" a nivel de base y no solo en el ORM: en MySQL el
    # default es RESTRICT y borrar un emprendimiento con eventos cargados
    # fallaria con IntegrityError. Es el mismo bug que ya aparecio en reports,
    # favorites, messages y post_images (ver migraciones d09128dd029c,
    # b30b4ba8d199 y c8a4f1e07d36).
    post_id = db.Column(
        db.Integer, db.ForeignKey("posts.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    titulo = db.Column(db.String(120), nullable=False)
    # Corta a proposito: es lo que entra en una tarjeta de la cartelera, no la
    # descripcion larga del emprendimiento.
    descripcion = db.Column(db.String(300), nullable=True)
    # Indexada porque todas las consultas filtran y ordenan por fecha (los
    # proximos del perfil y la cartelera de /eventos).
    fecha = db.Column(db.Date, nullable=False, index=True)
    # Opcional: "la feria es el sabado" es un evento valido sin hora.
    hora = db.Column(db.Time, nullable=True)
    created = db.Column(db.DateTime, nullable=False, default=utcnow)

    def __repr__(self):
        return f"<Event post_id={self.post_id} {self.fecha} {self.titulo}>"

    def serialize(self):
        return {
            "id": self.id,
            "post_id": self.post_id,
            "titulo": self.titulo,
            "descripcion": self.descripcion,
            "fecha": self.fecha.isoformat() if self.fecha else None,
            "hora": self.hora.strftime("%H:%M") if self.hora else None,
        }
