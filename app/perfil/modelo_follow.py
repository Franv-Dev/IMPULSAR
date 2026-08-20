from db import db, utcnow


class Follow(db.Model):
    """Un usuario que sigue a un emprendedor.

    Igual que Favorite, pero apuntando a una persona y no a un emprendimiento:
    seguir es "quiero saber de este emprendedor", marcar favorito es "me
    interesa esta publicacion".
    """

    __tablename__ = "follows"

    __table_args__ = (
        # No se puede seguir dos veces a la misma persona: sin esto, dos clicks
        # casi simultaneos en el boton insertan dos filas.
        db.UniqueConstraint("follower_id", "followed_id", name="uq_follow_par"),
        # Nadie se sigue a si mismo. Va tambien en la base y no solo en la
        # vista: es una regla del dato, y asi no depende de que todos los
        # caminos que inserten un Follow se acuerden de chequearla.
        db.CheckConstraint("follower_id <> followed_id", name="ck_follow_no_a_si_mismo"),
    )

    id = db.Column(db.Integer, primary_key=True)
    # Las dos FK con ondelete="CASCADE": borrar una cuenta tiene que llevarse
    # lo que seguia y lo que le seguian. En MySQL el default es RESTRICT y el
    # borrado fallaria con IntegrityError (el bug de reports/favorites/messages).
    follower_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    followed_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    created = db.Column(db.DateTime, nullable=False, default=utcnow)

    # foreign_keys explicito: hay dos FK a la misma tabla y SQLAlchemy no puede
    # adivinar cual corresponde a cada relacion.
    follower = db.relationship("User", foreign_keys=[follower_id])
    followed = db.relationship("User", foreign_keys=[followed_id])

    def __repr__(self):
        return f"<Follow {self.follower_id} -> {self.followed_id}>"

    def serialize(self):
        return {
            "follower_id": self.follower_id,
            "followed_id": self.followed_id,
            "created": self.created.isoformat() if self.created else None,
        }
